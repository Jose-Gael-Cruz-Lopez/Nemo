from fastapi import APIRouter, Depends, HTTPException

from apps.core.reeftrace_core.service import get_store
from apps.datasets.reeftrace_datasets.catalog import CATALOG

from ....core.security import require_operator

router = APIRouter(dependencies=[Depends(require_operator)])


@router.get("/datasets")
def datasets():
    return {
        "catalog": CATALOG,
        "imports": get_store().list("external_dataset"),
        "note": "External research data; no automatic tank profile or agent source-evidence ingestion.",
    }


@router.get("/datasets/imports/{record_id}")
def imported(record_id: str):
    try:
        return get_store().get(record_id, "external_dataset")
    except KeyError:
        raise HTTPException(404, "Dataset import not found") from None
