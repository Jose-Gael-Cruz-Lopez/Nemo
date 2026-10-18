"""Private saved-footage evaluation; never opens a camera or contacts a provider."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from ....schemas.contracts import StrictModel
from ....services.detector_replay import DetectorReplayService


class ReplayInput(StrictModel):
    pass


def create_detector_replay_router(runtime, operator):
    service = DetectorReplayService(runtime)
    replay_lock = asyncio.Lock()

    def local_only(request: Request, response: Response):
        response.headers["Cache-Control"] = "no-store"
        if getattr(request.app.state, "deployment_profile", None) == "cloud_software_demo":
            raise HTTPException(503, "Saved camera footage stays on the local capture companion",
                                headers={"Cache-Control": "no-store"})

    router = APIRouter(prefix="/camera/detector-replay", tags=["detector-replay"],
                       dependencies=[Depends(local_only), Depends(operator)])

    @router.get("")
    def latest():
        return service.latest()

    @router.post("")
    async def run(body: ReplayInput):
        if replay_lock.locked():
            raise HTTPException(409, "A saved-footage replay is already running",
                                headers={"Cache-Control": "no-store"})
        async with replay_lock:
            task = asyncio.create_task(asyncio.to_thread(service.run))
            try:
                return await asyncio.shield(task)
            except FileNotFoundError:
                raise HTTPException(409, "No saved-footage manifest is prepared locally") from None
            finally:
                # A disconnected browser must not release the CPU-work lock
                # while its worker thread is still reading the private clip.
                if not task.done():
                    await task

    return router
