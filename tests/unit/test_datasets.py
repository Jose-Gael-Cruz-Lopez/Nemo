import json
from pathlib import Path

import cv2
import httpx
import numpy as np
import pytest
from pydantic import ValidationError

from apps.core.reeftrace_core.store import Store
from apps.datasets.reeftrace_datasets.common import download, safe_relative
from apps.datasets.reeftrace_datasets.copernicus import (
    MarineQuery,
    subset_arguments,
    summarize_netcdf,
)
from apps.datasets.reeftrace_datasets.noaa import DrifterQuery, query_url, read_tracks
from apps.datasets.reeftrace_datasets.taco import export_yolo, import_taco


def coco():
    return {
        "categories": [{"id": 5, "name": "Plastic bottle"}],
        "images": [
            {
                "id": 1,
                "file_name": "batch_1/a.jpg",
                "width": 20,
                "height": 10,
                "flickr_url": "https://live.staticflickr.com/test.jpg",
            },
            {"id": 2, "file_name": "batch_2/b.jpg", "width": 20, "height": 10},
        ],
        "annotations": [{"id": 1, "image_id": 1, "category_id": 5, "bbox": [2, 2, 4, 4]}],
    }


def test_download_bounded_atomic_and_paths(tmp_path):
    with (
        httpx.Client(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, content=b"123456"))
        ) as client,
        pytest.raises(ValueError),
    ):
        download("https://example.org/data", tmp_path / "file", max_bytes=3, client=client)
    assert not (tmp_path / "file").exists()
    assert not list(tmp_path.glob("*.part"))
    for name in ["../secret", "/absolute", "C:\\escape", "a/../../escape"]:
        with pytest.raises(ValueError):
            safe_relative(name)


def test_taco_import_records_provenance_without_training_or_profile(tmp_path, monkeypatch):
    monkeypatch.setenv("REEFTRACE_DATASET_DIR", str(tmp_path / "cache"))
    client = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=coco())))
    result = import_taco(0, client=client, store=Store(tmp_path / "store.db"))
    assert result["summary"]["images"] == 2
    assert result["summary"]["downloaded_images"] == 0
    assert result["summary"]["detector_trained"] is False
    assert result["tank_profile_compatible"] is False
    assert len(result["artifacts"][0]["sha256"]) == 64
    client.close()


def test_yolo_keeps_batches_separate_and_boxes_normalized(tmp_path):
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    (snapshot / "annotations.json").write_text(json.dumps(coco()))
    for image in coco()["images"]:
        path = snapshot / "images" / image["file_name"]
        path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(path), np.zeros((10, 20, 3), np.uint8))
    output = tmp_path / "yolo"
    report = export_yolo(snapshot, output)
    assert report["train"] == report["val"] == 1
    label = next(p for p in (output / "labels").rglob("1.txt")).read_text().split()
    assert list(map(float, label)) == pytest.approx([0, 0.2, 0.4, 0.2, 0.4])
    assert "Plastic bottle" in (output / "dataset.yaml").read_text()
    with pytest.raises(ValueError):
        export_yolo(snapshot, output)


def test_noaa_handles_units_bad_rows_and_time_order(tmp_path):
    path = tmp_path / "sample.csv"
    path.write_text(
        "ID,time,latitude,longitude\n,UTC,degrees_north,degrees_east\n7,2020-01-01T06:00:00Z,20,-60\n7,2020-01-01T00:00:00Z,19,-61\n7,2020-01-01T12:00:00Z,NaN,-60\n"
    )
    tracks = read_tracks(path)
    assert tracks["valid_rows"] == 2
    assert tracks["rejected_rows"] == 1
    assert tracks["trajectories"][0]["points"][0]["latitude"] == 19
    assert tracks["units"]["latitude"] == "degrees_north"
    config = json.loads(Path("config/noaa.example.json").read_text())
    query = DrifterQuery.model_validate(config)
    assert "ID,time,latitude,longitude" in query_url(query)
    config["end"] = "2021-01-01T00:00:00Z"
    with pytest.raises(ValidationError):
        DrifterQuery.model_validate(config)


def test_copernicus_request_and_masked_units(tmp_path):
    xr = pytest.importorskip("xarray")
    query = MarineQuery.model_validate_json(Path("config/copernicus.example.json").read_text())
    args = subset_arguments(query, tmp_path)
    assert args["variables"] == ["uo", "vo"] and args["overwrite"] is False
    data = xr.Dataset(
        {
            "uo": (
                ("time", "depth", "latitude", "longitude"),
                np.array([[[[1.0, np.nan], [2.0, 3.0]]]]),
            ),
            "vo": (("time", "depth", "latitude", "longitude"), np.zeros((1, 1, 2, 2))),
        },
        coords={
            "time": [np.datetime64("2020-01-01")],
            "depth": [0.5],
            "latitude": [39, 40],
            "longitude": [-72, -71],
        },
    )
    data.depth.attrs["units"] = "m"
    for name in ["uo", "vo"]:
        data[name].attrs["units"] = "m s-1"
    path = tmp_path / "currents.nc"
    data.to_netcdf(path, engine="scipy")
    report = summarize_netcdf(path)
    assert report["valid_sampled_vectors"] == 3
    assert report["missing_sampled_vectors"] == 1
    assert report["vectors"][0]["eastward_m_s"] == 1.0
    data.uo.attrs["units"] = "cm/s"
    data.to_netcdf(path, engine="scipy")
    with pytest.raises(ValueError):
        summarize_netcdf(path)


def test_noaa_snapshots_survive_provider_revisions(tmp_path, monkeypatch):
    from apps.datasets.reeftrace_datasets.noaa import import_noaa

    monkeypatch.setenv("REEFTRACE_DATASET_DIR", str(tmp_path / "cache"))
    config = json.loads(Path("config/noaa.example.json").read_text())
    revision = [19]

    def handler(request):
        if request.url.path.endswith("index.json"):
            return httpx.Response(200, json={"table": {"rows": []}})
        return httpx.Response(
            200,
            text=f"ID,time,latitude,longitude\n,UTC,degrees_north,degrees_east\n7,2020-01-01T00:00:00Z,{revision[0]},-60\n",
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        store = Store(tmp_path / "registry.db")
        first = import_noaa(config, client=client, store=store)
        old_path = Path(first["artifacts"][1]["file"])
        old_bytes = old_path.read_bytes()
        revision[0] = 20
        second = import_noaa(config, client=client, store=store)
    assert old_path.read_bytes() == old_bytes
    assert first["artifacts"][1]["sha256"] != second["artifacts"][1]["sha256"]
    assert store.list("profile") == []
