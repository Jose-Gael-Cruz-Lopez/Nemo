"""Optional Photon 2.0 worker. Run explicitly after provisioning routes and keys.

No messages are sent merely by starting the API or importing this module.
"""

import asyncio
import json
import os
import re
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import httpx

from .agent import investigate
from .service import LocalBackend, get_store


def normalize(item, routes, start):
    from photon_api.generated.models import TextContent, UserSnapshot

    m = item.root.root
    if m.platform != "imessage" or m.status != "received":
        return None
    created = datetime.fromisoformat(m.createdAt)
    if created.tzinfo is None or created < start or not isinstance(m.receivedBy, UserSnapshot):
        return None
    human, agent, space = m.sentBy.root, m.receivedBy.root, m.space.root
    if any(x.platform != "imessage" for x in (human, agent, space)):
        return None
    if (
        human.kind != "human"
        or agent.kind != "agent"
        or human.id == agent.id
        or space.kind != "direct"
    ):
        return None
    route = next(
        (
            r
            for r in routes
            if r["human_handle"] == human.handle and r["agent_handle"] == agent.handle
        ),
        None,
    )
    if (
        not route
        or not isinstance(m.content, TextContent)
        or m.content.format != "plain"
        or len(m.content.text) > 4000
    ):
        return None
    return {
        "id": m.id,
        "created_at": m.createdAt,
        "human_id": human.id,
        "agent_id": agent.id,
        "space_id": space.id,
        "role": route["role"],
        "allowed_cases": route["allowed_cases"],
        "active_case": route["active_case"],
        "text": m.content.text.strip(),
    }


def control(store, message):
    text = message["text"]
    if text == "STOP":
        if message["role"] != "operator":
            return "Operator permission required."
        # Scope STOP to this route's permitted cases, never another conversation.
        with store.connect() as db:
            rows = db.execute(
                "SELECT id,case_id,operator,conversation FROM actions WHERE state IN ('pending','approved','acting')"
            ).fetchall()
        for row in rows:
            if (
                row["case_id"] in message["allowed_cases"]
                and row["operator"] == message["human_id"]
                and row["conversation"] == message["space_id"]
            ):
                store.stop(row["id"])
        return "Pending manual tasks stopped. This does not disconnect physical power."
    if text.startswith(("APPROVE", "CANCEL")):
        approve = re.fullmatch(r"APPROVE (action-[0-9a-f-]{36}) ([A-Za-z0-9_-]+)", text)
        cancel = re.fullmatch(r"CANCEL (action-[0-9a-f-]{36})", text)
        if message["role"] != "operator" or not (approve or cancel):
            return "Invalid command or operator permission missing."
        action_id = (approve or cancel).group(1)
        action = store.action(action_id)
        if (
            action["case_id"] not in message["allowed_cases"]
            or action["operator"] != message["human_id"]
            or action["conversation"] != message["space_id"]
        ):
            return "Proposal is not authorized for this route."
        if cancel:
            store.stop(action_id)
            return "Manual task cancelled."
        store.approve(action_id, approve.group(2), message["human_id"], message["space_id"])
        return "Manual net task authorized. Confirm recovery locally with frame evidence; no pump was triggered."
    return None


def retry_delay(value):
    try:
        return max(2.0, float(value))
    except (ValueError, TypeError):
        try:
            return max(2.0, (parsedate_to_datetime(value) - datetime.now(UTC)).total_seconds())
        except (ValueError, TypeError, OverflowError):
            return 10.0


async def ingress(client, store, project, routes, stop):
    from photon_api import ApiError, PhotonError
    from photon_api.rpc_generated import ListMessagesInput

    start_text = store.session_start()
    start = datetime.fromisoformat(start_text)
    while not stop.is_set():
        delay = 2.0
        try:
            token = None
            while True:
                query = {
                    "createdSince": start_text,
                    "direction": "received",
                    "order": "asc",
                    "pageSize": 100,
                    "platform": "imessage",
                }
                if token:
                    query["pageToken"] = token
                page = await client.projects.list_messages(
                    ListMessagesInput.model_validate({"path": {"id": project}, "query": query})
                )
                for item in page.items:
                    try:
                        message = normalize(item, routes, start)
                        if message and store.ingest_once(message):
                            # Fast lane runs independently of the agent worker.
                            try:
                                result = control(store, message)
                            except (ValueError, KeyError):
                                result = "Control request rejected: stale or unauthorized proposal."
                            if result is not None:
                                store.save_reply(message, result)
                    except (AttributeError, TypeError, ValueError):
                        store.put("transport_error", {"error": "unsupported_message"})
                next_token = page.nextPageToken
                if not isinstance(next_token, str) or not next_token:
                    break
                token = next_token
        except ApiError as error:
            store.put(
                "transport_error",
                {"error": "photon_api", "status": error.status, "request_id": error.request_id},
            )
            if error.status in (401, 403):
                raise
            delay = retry_delay(error.headers.get("retry-after"))
        except PhotonError:
            store.put("transport_error", {"error": "photon_transport"})
            delay = 10.0
        try:
            await asyncio.wait_for(stop.wait(), timeout=delay)
        except TimeoutError:
            pass


async def agent_worker(store, stop):
    while not stop.is_set():
        message = store.claim_message()
        if not message:
            await asyncio.sleep(0.2)
            continue
        try:
            result = control(store, message)
            if result is None:
                case_id = message["active_case"]
                if case_id not in message["allowed_cases"]:
                    raise ValueError("Case not authorized")
                backend = LocalBackend(
                    store, case_id, message["human_id"], message["space_id"], message["role"]
                )
                result = await investigate(
                    message["text"], backend, {"case_id": case_id, "role": message["role"]}
                )
                store.put("investigation", result, case_id)
                # Render numeric source evidence directly, outside generated explanation.
                report = store.latest_evidence(case_id)
                table = ", ".join(f"{k}: {v:.3f}" for k, v in report["relative_support"].items())
                text = f"{report['source']} — relative support, not probability: {table}\n{result['explanation']}\nEvidence: {', '.join(result['evidence_ids'])}"
                proposal_id = result.get("proposal_id")
                if proposal_id:
                    proposal = next(
                        t["result"]
                        for t in result["trace"]
                        if t["tool"] == "propose_collection" and t["result"]["id"] == proposal_id
                    )
                    text += f"\nManual net only. APPROVE {proposal_id} {proposal['approval_token']}"
            else:
                text = result
        except (httpx.HTTPError, RuntimeError, ValueError, KeyError, TypeError, TimeoutError):
            text = "Investigation unavailable or request rejected; no action authorized."
        store.save_reply(message, text)


async def outbox(client, store, project, stop):
    from photon_api import ApiError, PhotonError
    from photon_api.rpc_generated import SendMessageInput

    while not stop.is_set():
        for row in store.pending_replies():
            try:
                response = await client.raw.projects.send_message(
                    SendMessageInput.model_validate(
                        {
                            "path": {"id": project},
                            "headers": {"idempotency-key": row["key"]},
                            "body": {
                                "spaceId": row["space_id"],
                                "senderId": row["agent_id"],
                                "parentMessageId": row["parent_message_id"],
                                "content": {"type": "text", "format": "plain", "text": row["text"]},
                            },
                        }
                    )
                )
                if 200 <= response.status < 300:
                    store.reply_accepted(row["key"], response.request_id)
            except ApiError as error:
                if error.status in (401, 403):
                    raise
                await asyncio.sleep(retry_delay(error.headers.get("retry-after")))
            except (PhotonError, httpx.HTTPError, ValueError):
                # Identical saved body/key is retried, never regenerating a reply.
                store.put(
                    "transport_error", {"error": "outbox_send_failed", "reply_id": row["key"]}
                )
        await asyncio.sleep(2)


async def main():
    from dotenv import load_dotenv
    from photon_api import AsyncPhoton

    load_dotenv()
    routes = json.loads(os.environ["PHOTON_ROUTES_JSON"])
    for route in routes:
        if (
            route["role"] not in {"operator", "observer"}
            or route["active_case"] not in route["allowed_cases"]
        ):
            raise ValueError("Invalid Photon route")
    store = get_store()
    stop = asyncio.Event()
    async with AsyncPhoton(
        headers={"Authorization": "Bearer " + os.environ["PHOTON_API_KEY"]},
        timeout=5,
        max_attempts=2,
        max_retry_after=3,
    ) as client:
        await asyncio.gather(
            ingress(client, store, os.environ["PHOTON_PROJECT_ID"], routes, stop),
            agent_worker(store, stop),
            outbox(client, store, os.environ["PHOTON_PROJECT_ID"], stop),
        )


if __name__ == "__main__":
    asyncio.run(main())
