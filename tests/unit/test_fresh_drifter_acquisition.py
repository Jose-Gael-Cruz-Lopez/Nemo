"""Acquisition uses invented metadata/positions only; never hits NOAA or fits models."""

from __future__ import annotations

import json
import shutil
from urllib.parse import unquote

import httpx
import pytest

from apps.ocean.reeftrace_ocean import fresh_drifter_protocol as protocol
from scripts.fetch_fresh_drifter_study import acquire_study


def directory(tmp_path):
    d = tmp_path / "study"
    d.mkdir()
    for name in ("protocol.json", "protocol.sha256", "exclusions.json", "exclusions.sha256"):
        shutil.copyfile(protocol.DIRECTORY / name, d / name)
    return d


def info():
    return json.dumps(
        {
            "table": {
                "rows": [
                    [
                        "attribute",
                        "NC_GLOBAL",
                        "license",
                        "String",
                        "Creative Commons Attribution 4.0 https://creativecommons.org/licenses/by/4.0/",
                    ],
                    ["attribute", "NC_GLOBAL", "doi", "String", "10.25921/x46c-3620"],
                ]
            }
        }
    ).encode()


def identity(exclusions):
    rows = ["ID,WMO", ","]
    rows.extend(
        f"{identifier},{1000000 + i}" for i, identifier in enumerate(exclusions["reserved_gdp_ids"])
    )
    rows.extend(f"{900000000000001 + i},{8000001 + i}" for i in range(6))
    return ("\n".join(rows) + "\n").encode()


def snapshot(block, index):
    rows = [
        "ID,time,latitude,longitude,WMO,expno,location_type",
        ",UTC,degrees_north,degrees_east,,count,",
    ]
    lat = (block["latitude_min"] + block["latitude_max"]) / 2
    lon = (block["longitude_min"] + block["longitude_max"]) / 2
    for i in reversed(range(2)):
        k = index * 2 + i
        rows.append(f"{900000000000001 + k},{block['start_utc']},{lat},{lon},{8000001 + k},1,GPS")
    return ("\n".join(rows) + "\n").encode()


def handler(d, p, e, seen):
    def send(request):
        value = unquote(str(request.url))
        seen.append(value)
        if "/info/" in value:
            return httpx.Response(200, content=info())
        if "?ID,WMO&distinct()" in value:
            return httpx.Response(200, content=identity(e))
        if "?ID,time,latitude,longitude,WMO" in value:
            assert (d / "identity-receipt.json").is_file()
            assert (d / "raw/identity-aliases.sha256").is_file()
            for index, block in enumerate(p["selection"]["blocks"]):
                if f"longitude>={block['longitude_min']}" in value:
                    return httpx.Response(200, content=snapshot(block, index))
            raise AssertionError("Unexpected snapshot URL")
        assert (d / "selection.json").is_file() and (d / "selection.sha256").is_file()
        s = json.loads((d / "selection.json").read_text())
        assert not s["trajectory_payloads_fetched"]
        return httpx.Response(
            200, content=b"Invented raw fixture; acquisition never parses or models it.\n"
        )

    return send


def test_selection_is_frozen_before_six_raw_trajectory_requests_and_alias_receipt_precedes_blocks(
    tmp_path,
):
    d = directory(tmp_path)
    p, e, _ = protocol.load_design(d)
    seen = []
    with httpx.Client(transport=httpx.MockTransport(handler(d, p, e, seen))) as client:
        result = acquire_study(d, client=client)
    assert result["selected_groups"] == result["downloaded_groups"] == 6
    assert result["evaluation_outcomes_computed"] is False
    assert len(seen) == 11
    selection, _ = protocol.pinned_json(d, "selection")
    assert [g["drifter_id"] for g in selection["groups"]] == [
        str(900000000000001 + i) for i in range(6)
    ]
    assert selection["aliases"]["unresolved_reserved_alias_count"] == 0
    assert all((d / r["raw_path"]).is_file() for r in selection["source_receipts"])
    with pytest.raises(ValueError, match="already attempted"):
        acquire_study(d, client=object())


def test_first_metadata_timeout_is_retained_no_retry_no_fallback_and_no_false_download(tmp_path):
    d = directory(tmp_path)
    requests = []

    def send(request):
        requests.append(request)
        raise httpx.ConnectTimeout("Invented unavailable upstream")

    with httpx.Client(transport=httpx.MockTransport(send)) as client:
        result = acquire_study(d, client=client)
    assert len(requests) == 1 and result["selected_groups"] == result["downloaded_groups"] == 0
    manifest, _ = protocol.pinned_json(d, "manifest")
    assert manifest["requests_attempted"] == 1 and manifest["trajectories"] == []
    assert manifest["source_receipts"][0]["reason"] == "ConnectTimeout"
    assert (
        manifest["source_receipts"][0]["started_at_utc"]
        <= manifest["source_receipts"][0]["finished_at_utc"]
    )


def test_alias_exclusions_missing_and_ambiguous_old_ids_remain_visible_without_blocking_new_candidates():
    p = {
        "selection": {
            "blocks": [
                {
                    "id": "x",
                    "start_utc": "2021-01-01T00:00:00Z",
                    "end_utc": "2021-01-01T23:00:00Z",
                    "latitude_min": 0,
                    "latitude_max": 1,
                    "longitude_min": 0,
                    "longitude_max": 1,
                }
            ],
            "metadata_columns": [
                "ID",
                "time",
                "latitude",
                "longitude",
                "WMO",
                "expno",
                "location_type",
            ],
            "target_per_block": 2,
        }
    }
    e = {"reserved_gdp_ids": ["1", "99", "100"]}
    aliases = b"ID,WMO\n,\n1,70\n99,80\n101,80\n2,72\n10,73\n3,-999999\n4,70\n5,74\n6,74\n"
    rows = b"ID,time,latitude,longitude,WMO,expno,location_type\n,UTC,degrees_north,degrees_east,,count,\n"
    rows += (
        b"\n".join(
            f"{i},2021-01-01T00:00:00Z,.5,.5,{w},1,GPS".encode()
            for i, w in [("10", 73), ("1", 70), ("3", -999999), ("4", 70), ("5", 74), ("2", 72)]
        )
        + b"\n"
    )
    groups, _, summary = protocol.derive_groups(p, e, aliases, {"x": rows})
    assert [g["drifter_id"] for g in groups] == ["2", "10"]
    assert summary["unresolved_reserved_alias_ids"] == ["1", "99", "100"]
    assert summary["physical_alias_resolution_verified"] is False
    assert summary["statistical_independence"] is False


def test_duplicate_snapshot_identity_and_candidate_alias_mismatch_fail_or_exclude():
    p, e, _ = protocol.load_design()
    block = p["selection"]["blocks"][0]
    bad = snapshot(block, 0).decode().splitlines()
    bad.append(bad[2])
    with pytest.raises(ValueError, match="unique"):
        protocol.metadata_rows(("\n".join(bad) + "\n").encode(), p, block)
    values = snapshot(block, 0).replace(b"8000001", b"8000999")
    groups, _, _ = protocol.derive_groups(p, e, identity(e), {block["id"]: values})
    assert [g["drifter_id"] for g in groups] == ["900000000000002"]
