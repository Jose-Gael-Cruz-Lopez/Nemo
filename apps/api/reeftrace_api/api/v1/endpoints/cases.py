import os
import re
from pathlib import Path
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import Field

from apps.core.reeftrace_core.agent import investigate
from apps.core.reeftrace_core.contracts import CaseInput, Contract, Profile
from apps.core.reeftrace_core.service import (
    LocalBackend,
    analyze,
    create_case,
    get_store,
    profile_for,
    register_profile,
)

from ....core.security import require_operator

router = APIRouter(dependencies=[Depends(require_operator)])


class Preset(Contract):
    preset_id: Literal["age_short_v1", "age_wide_v1"]


class Question(Contract):
    question: str = Field(min_length=1, max_length=4000)


class Proposal(Contract):
    case_id: str
    evidence_id: str
    mode: Literal["manual_net"] = "manual_net"


class Approval(Contract):
    token: str = Field(min_length=1, max_length=200)


class RecoveryEvidence(Contract):
    action_id: str
    frame_reference: str = Field(min_length=1, max_length=500)
    human_confirmation: str = Field(min_length=1, max_length=2000)


class Outcome(Contract):
    recovered: bool
    evidence_id: str


def guarded(function, *args):
    try:
        return function(*args)
    except KeyError:
        raise HTTPException(404, "Record not found") from None
    except ValueError as error:
        raise HTTPException(409, str(error)) from None


@router.get("/system")
def system():
    return {
        "manual_recovery": True,
        "hardware_enabled": False,
        "chalk_configured": all(
            os.environ.get(k) for k in ["CHALK_ROUTER_API_KEY", "CHALK_ENV_ID", "CHALK_MODEL"]
        ),
        "photon_configured": all(
            os.environ.get(k) for k in ["PHOTON_API_KEY", "PHOTON_PROJECT_ID", "PHOTON_ROUTES_JSON"]
        ),
        "asus": {
            "model": os.environ.get("REEFTRACE_COMPUTER_MODEL", "ASUS model TBD"),
            "os": os.environ.get("REEFTRACE_COMPUTER_OS", "OS TBD"),
            "gpu_required": False,
        },
    }


@router.post("/profiles")
def profiles(profile: Profile):
    return guarded(register_profile, get_store(), profile)


@router.get("/profiles")
def list_profiles():
    return get_store().list("profile")


@router.post("/cases")
def cases(case: CaseInput):
    return guarded(create_case, get_store(), case)


@router.get("/cases")
def list_cases():
    return get_store().list("case")


@router.get("/cases/{case_id}")
def get_case(case_id: str):
    case = guarded(get_store().get, case_id, "case")
    profile = guarded(profile_for, get_store(), case["calibration_id"])
    return {**case, "width_cm": profile.width_cm, "height_cm": profile.height_cm}


@router.get("/cases/{case_id}/evidence")
def evidence(case_id: str):
    return guarded(get_store().latest_evidence, case_id)


@router.post("/cases/{case_id}/sensitivity")
def sensitivity(case_id: str, request: Preset):
    return guarded(analyze, get_store(), case_id, request.preset_id)


@router.post("/cases/{case_id}/observe")
async def observe(case_id: str):
    backend = guarded(LocalBackend, get_store(), case_id)
    return await backend.call("observe_again", {})


@router.post("/cases/{case_id}/investigate")
async def question(case_id: str, request: Question, operator: str = Depends(require_operator)):
    store = get_store()
    backend = guarded(LocalBackend, store, case_id, operator)
    try:
        result = await investigate(
            request.question, backend, {"case_id": case_id, "role": "operator"}
        )
        if store.latest_evidence(case_id)["id"] != backend.evidence_id:
            raise ValueError("Evidence changed during investigation")
        return store.put("investigation", result, case_id)
    except (TimeoutError, RuntimeError, ValueError, KeyError, TypeError):
        raise HTTPException(
            503, "Investigation unavailable or failed evidence validation; no action authorized"
        ) from None
    except httpx.HTTPError:
        raise HTTPException(502, "Gateway request failed; no action authorized") from None


@router.post("/actions/propose")
def propose(request: Proposal, operator: str = Depends(require_operator)):
    return guarded(get_store().propose, request.case_id, request.evidence_id, operator, "dashboard")


@router.get("/actions/{action_id}")
def action(action_id: str):
    return guarded(get_store().action, action_id)


@router.post("/actions/{action_id}/approve")
def approve(action_id: str, request: Approval, operator: str = Depends(require_operator)):
    return guarded(get_store().approve, action_id, request.token, operator, "dashboard")


@router.post("/actions/{action_id}/stop")
def stop(action_id: str):
    guarded(get_store().action, action_id)
    return get_store().stop(action_id)


@router.post("/stop")
def stop_all():
    return get_store().stop()


@router.post("/recovery-evidence")
def recovery_evidence(request: RecoveryEvidence):
    guarded(get_store().action, request.action_id)
    return get_store().put("recovery_evidence", request.model_dump())


@router.post("/actions/{action_id}/outcome")
def outcome(action_id: str, request: Outcome, operator: str = Depends(require_operator)):
    return guarded(get_store().outcome, action_id, request.recovered, request.evidence_id, operator)


class RigCheck(Contract):
    calibration_id: str
    waterline_checked: Literal[True]
    camera_mapping_checked: Literal[True]
    pump_and_geometry_checked: Literal[True]
    flow_recovered: Literal[True]


@router.get("/rig")
def rig():
    store = get_store()
    return {
        "state": store.setting("rig_state", "startup_check_required"),
        "calibration_id": store.setting("active_calibration"),
    }


@router.post("/rig/check")
def check_rig(request: RigCheck):
    profile = guarded(profile_for, get_store(), request.calibration_id)
    if profile.validity != "validated" or profile.synthetic:
        raise HTTPException(409, "A validated measured profile is required for live rig checks")
    return get_store().check_rig(profile.id)


@router.post("/rig/invalidate")
def invalidate_rig():
    return get_store().invalidate_rig()


@router.get("/frames/{frame_id}")
def frame(frame_id: str):
    if not re.fullmatch(r"camera-[0-9]+-[0-9]+", frame_id):
        raise HTTPException(404, "Frame not found")
    path = Path("data/runs/frames") / (frame_id + ".jpg")
    if not path.is_file() or path.is_symlink():
        raise HTTPException(404, "Frame not found")
    return FileResponse(path, media_type="image/jpeg")
