import hashlib
import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx

from apps.core.reeftrace_core.service import get_store


def cache_root():
    root = Path(os.environ.get("REEFTRACE_DATASET_DIR", "data/external"))
    root.mkdir(parents=True, exist_ok=True)
    return root


def safe_relative(name):
    # COCO paths may be nested, but can never escape the download directory.
    if not isinstance(name, str) or not name or "\\" in name or ":" in name:
        raise ValueError("Invalid dataset filename")
    path = Path(name)
    if path.is_absolute() or any(p in {".", ".."} for p in path.parts):
        raise ValueError("Dataset filename must be a safe relative path")
    return path


def download(url, path, max_bytes=20_000_000, client=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".part")
    owned = client is None
    client = client or httpx.Client(timeout=60, follow_redirects=True)
    try:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.username or parsed.password:
            raise ValueError("Dataset download requires a public HTTPS URL")
        size = 0
        with client.stream("GET", url) as response:
            response.raise_for_status()
            if response.url.scheme != "https":
                raise ValueError("Insecure download redirect rejected")
            with temporary.open("wb") as output:
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > max_bytes:
                        raise ValueError(
                            "Download exceeds configured byte limit; choose a smaller subset"
                        )
                    output.write(chunk)
        temporary.replace(path)
        return path
    finally:
        temporary.unlink(missing_ok=True)
        if owned:
            client.close()


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def save_import(dataset_id, query, summary, artifacts, source_url, store=None):
    # Credentials and truth labels are not accepted as import metadata.
    payload = {
        "dataset_id": dataset_id,
        "usage": "external_research_only",
        "tank_profile_compatible": False,
        "imported_at": datetime.now(UTC).isoformat(),
        "source_url": source_url,
        "query": query,
        "summary": summary,
        "artifacts": [
            {"file": str(Path(p)), "sha256": sha256(p), "bytes": Path(p).stat().st_size}
            for p in artifacts
        ],
    }
    return (store or get_store()).put("external_dataset", payload)


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
