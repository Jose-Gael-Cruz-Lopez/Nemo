"""Download official COCO annotations and optionally a bounded image sample."""

import json
import random
from collections import Counter, defaultdict
from urllib.parse import urlparse

import cv2
import httpx

from .common import cache_root, download, safe_relative, save_import, sha256, write_json

ANNOTATIONS_URL = "https://raw.githubusercontent.com/pedropro/TACO/master/data/annotations.json"


def summarize_coco(coco):
    for key in ["images", "annotations", "categories"]:
        if not isinstance(coco.get(key), list):
            raise TypeError("Expected COCO images, annotations and categories arrays")
    categories = {c["id"]: c["name"] for c in coco["categories"]}
    if len(categories) != len(coco["categories"]):
        raise ValueError("Duplicate category IDs")
    images = {image["id"]: image for image in coco["images"]}
    if len(images) != len(coco["images"]):
        raise ValueError("Duplicate image IDs")
    counts = Counter()
    for annotation in coco["annotations"]:
        if annotation["image_id"] not in images or annotation["category_id"] not in categories:
            raise ValueError("Annotation references missing image/category")
        counts[categories[annotation["category_id"]]] += 1
    return {
        "images": len(images),
        "annotations": len(coco["annotations"]),
        "categories": [
            {"id": k, "name": v, "annotations": counts[v]} for k, v in categories.items()
        ],
        "downloaded_images": 0,
        "failed_images": [],
        "licenses": coco.get("licenses", []),
        "detector_trained": False,
    }


def import_taco(image_limit=0, client=None, store=None):
    if not 0 <= image_limit <= 2000:
        raise ValueError("Image limit must be between 0 and 2000")
    staging = cache_root() / "taco"
    annotation_path = download(
        ANNOTATIONS_URL, staging / "annotations.download.json", client=client
    )
    coco = json.loads(annotation_path.read_text())
    summary = summarize_coco(coco)
    snapshot = staging / sha256(annotation_path)[:16]
    snapshot.mkdir(parents=True, exist_ok=True)
    frozen = snapshot / "annotations.json"
    if not frozen.exists():
        frozen.write_bytes(annotation_path.read_bytes())
    artifacts = [frozen]
    batches = defaultdict(list)
    for image in sorted(coco["images"], key=lambda image: image["id"]):
        batches[str(safe_relative(image["file_name"]).parent)].append(image)
    selected = []
    # Spread small samples across batches, so development splits can stay grouped.
    for index in range(max((len(batch) for batch in batches.values()), default=0)):
        for batch in batches.values():
            if index < len(batch) and len(selected) < image_limit:
                selected.append(batch[index])
        if len(selected) >= image_limit:
            break
    for image in selected:
        try:
            path = snapshot / "images" / safe_relative(image["file_name"])
            url = image["flickr_url"]
            host = urlparse(url).hostname or ""
            if not (host.endswith(".staticflickr.com") or host == "live.staticflickr.com"):
                raise ValueError("Image is not on the documented Flickr image host")
            if not path.exists():
                download(url, path, max_bytes=25_000_000, client=client)
            decoded = cv2.imread(str(path))
            if (
                decoded is None
                or decoded.shape[1] != image["width"]
                or decoded.shape[0] != image["height"]
            ):
                raise ValueError(
                    "Image invalid or dimensions differ from COCO; do not rescale labels silently"
                )
            summary["downloaded_images"] += 1
            artifacts.append(path)
        except (KeyError, ValueError, OSError) as error:
            summary["failed_images"].append({"image_id": image["id"], "error": str(error)})
        except httpx.HTTPError as error:
            summary["failed_images"].append(
                {"image_id": image["id"], "error": type(error).__name__}
            )
    import hashlib

    summary_hash = hashlib.sha256(json.dumps(summary, sort_keys=True).encode()).hexdigest()[:12]
    manifest = snapshot / f"images-{image_limit}-{summary_hash}.json"
    write_json(manifest, {"requested": image_limit, "summary": summary})
    artifacts.append(manifest)
    summary["snapshot_directory"] = str(snapshot)
    return save_import(
        "taco",
        {"annotation_url": ANNOTATIONS_URL, "image_limit": image_limit},
        summary,
        artifacts,
        "https://github.com/pedropro/TACO",
        store,
    )


def export_yolo(snapshot, output, seed=7):
    """Export downloaded images only, preserving all categories and grouped splits.

    Consecutive filenames in one TACO batch are kept in the same split to reduce
    adjacent-image leakage. This is a development split, not a frozen test set.
    """
    import shutil
    from pathlib import Path

    snapshot, output = Path(snapshot), Path(output)
    if output.exists():
        raise ValueError("Choose a new output directory to keep exports immutable")
    coco = json.loads((snapshot / "annotations.json").read_text())
    summarize_coco(coco)
    categories = sorted(coco["categories"], key=lambda c: c["id"])
    mapping = {c["id"]: i for i, c in enumerate(categories)}
    annotations = defaultdict(list)
    for annotation in coco["annotations"]:
        annotations[annotation["image_id"]].append(annotation)
    selected = [
        i for i in coco["images"] if (snapshot / "images" / safe_relative(i["file_name"])).is_file()
    ]
    groups = sorted({str(safe_relative(i["file_name"]).parent) for i in selected})
    if len(groups) < 2:
        raise ValueError(
            "At least two downloaded image batches are needed for separate train/validation groups"
        )
    random.Random(seed).shuffle(groups)
    validation = set(groups[: max(1, round(len(groups) * 0.2))])
    report = {
        "train": 0,
        "val": 0,
        "seed": seed,
        "class_mapping": mapping,
        "development_only": True,
    }
    for image in selected:
        name = safe_relative(image["file_name"])
        source = snapshot / "images" / name
        decoded = cv2.imread(str(source))
        if decoded is None or (decoded.shape[1], decoded.shape[0]) != (
            image["width"],
            image["height"],
        ):
            raise ValueError("Invalid downloaded image dimensions")
        split = "val" if str(name.parent) in validation else "train"
        labels = []
        for annotation in annotations[image["id"]]:
            if annotation.get("iscrowd", 0):
                continue
            x, y, w, h = map(float, annotation["bbox"])
            width, height = image["width"], image["height"]
            if not (
                w > 0 and h > 0 and x >= 0 and y >= 0 and x + w <= width + 1 and y + h <= height + 1
            ):
                raise ValueError("Invalid COCO bounding box")
            labels.append(
                f"{mapping[annotation['category_id']]} {(x + w / 2) / width:.8f} {(y + h / 2) / height:.8f} {w / width:.8f} {h / height:.8f}"
            )
        destination = output / "images" / split / f"{image['id']}{source.suffix}"
        destination.parent.mkdir(parents=True, exist_ok=True)
        label_path = output / "labels" / split / f"{image['id']}.txt"
        label_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        label_path.write_text("\n".join(labels) + "\n")
        report[split] += 1
    # JSON values are valid YAML scalars; preserves class spelling and path quoting.
    text = (
        f"path: {json.dumps(str(output.resolve()))}\ntrain: images/train\nval: images/val\nnames:\n"
    )
    text += "".join(f"  {i}: {json.dumps(c['name'])}\n" for i, c in enumerate(categories))
    (output / "dataset.yaml").write_text(text)
    write_json(output / "export.json", report)
    write_json(
        output / "source-attribution.json",
        {
            "source": "https://github.com/pedropro/TACO",
            "images": selected,
            "licenses": coco.get("licenses", []),
            "source_annotation_sha256": sha256(snapshot / "annotations.json"),
        },
    )
    return report
