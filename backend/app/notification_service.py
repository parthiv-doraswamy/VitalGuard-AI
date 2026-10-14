"""Web Push notifications for committed demo alerts (synthetic data only).

Ownership: there is no user identity in this deployment, so a subscription is
device-scoped. Registering returns a management token once (only its SHA-256
hash is stored); changing, testing or removing the subscription requires it.
Role-based targeting is not possible until real authentication exists.

Flow
1. insert_alert() calls enqueue_for_alert() inside the alert's transaction, so a
   delivery row exists only if the alert committed. (subscription_id, event_key)
   is unique: duplicate alerts, retries and several instances cannot send twice.
2. NotificationWorker claims due rows with a conditional UPDATE (safe across
   instances), sends with VAPID through pywebpush, and records the outcome:
   - 201/202: "accepted" by the push service. NOT proof of delivery or display.
   - 404/410: subscription expired; it is deactivated and pending rows skipped.
   - 429/5xx/network: retried with exponential backoff (honours Retry-After).
   - other 4xx: failed permanently.
3. The service worker posts a receipt (HMAC nonce in the payload) when it shows
   the notification and when it is clicked. Only that sets displayed_at/clicked_at.

Payloads are minimal: alert id, severity and a fixed generic text. No patient
identifiers, vitals or scores. Logs identify subscriptions by id and never
include endpoints (capability URLs), keys or payloads.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import delete, desc, func, insert, select, update
from sqlalchemy.engine import Connection
from starlette.concurrency import run_in_threadpool

from .storage import get_engine
from .storage_schema import push_deliveries, push_subscriptions

logger = logging.getLogger("vitalguard.push")

SEVERITY_RANK = {"high": 1, "critical": 2}
MAX_ATTEMPTS = 5
DEFAULT_ALLOWED_HOSTS = ("fcm.googleapis.com", "updates.push.services.mozilla.com", "push.services.mozilla.com",
                         "web.push.apple.com", "*.notify.windows.com", "*.push.apple.com")
ACTIVE_DELIVERY_STATUSES = ("pending", "retrying", "sending")


class NotificationError(Exception):
    def __init__(self, status_code: int, code: str, detail: str) -> None:
        super().__init__(detail)
        self.status_code, self.code, self.detail = status_code, code, detail


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime | None) -> datetime | None:
    return value.replace(tzinfo=timezone.utc) if value is not None and value.tzinfo is None else value


def _iso(value: datetime | None) -> str | None:
    value = _aware(value)
    return value.astimezone(timezone.utc).isoformat() if value else None


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _b64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


# --- Configuration ----------------------------------------------------------------------

def _private_key() -> str:
    return os.getenv("VITALGUARD_VAPID_PRIVATE_KEY", "").strip()


def _subject() -> str:
    return os.getenv("VITALGUARD_VAPID_SUBJECT", "").strip()


def push_configured() -> bool:
    return bool(_private_key()) and _subject().startswith(("mailto:", "https://"))


def vapid_public_key() -> str | None:
    """Application server key for PushManager.subscribe, derived from the private key."""
    if not push_configured():
        return None
    from cryptography.hazmat.primitives import serialization
    from py_vapid import Vapid
    vapid = Vapid.from_string(_private_key())
    raw = vapid.public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _allowed_hosts() -> list[str]:
    configured = os.getenv("VITALGUARD_PUSH_ALLOWED_HOSTS", "").strip()
    return [host.strip().lower() for host in configured.split(",") if host.strip()] if configured else list(DEFAULT_ALLOWED_HOSTS)


def _host_allowed(host: str) -> bool:
    for pattern in _allowed_hosts():
        if pattern.startswith("*.") and (host.endswith(pattern[1:]) and host != pattern[2:]):
            return True
        if host == pattern:
            return True
    return False


def validate_endpoint(endpoint: str) -> None:
    """Only real push services: the server POSTs to this URL, so arbitrary hosts would allow SSRF."""
    parsed = urlparse(endpoint)
    insecure_ok = os.getenv("VITALGUARD_PUSH_ALLOW_INSECURE_ENDPOINTS", "").lower() == "true"  # tests only
    if parsed.scheme != "https" and not (insecure_ok and parsed.scheme == "http"):
        raise NotificationError(422, "endpoint_not_https", "Push endpoint must use HTTPS")
    if not parsed.hostname or not _host_allowed(parsed.hostname.lower()) or parsed.username or parsed.password:
        raise NotificationError(422, "endpoint_not_allowed", "Push endpoint is not a recognised push service")


def validate_keys(p256dh: str, auth: str) -> None:
    try:
        public, secret = _b64url_decode(p256dh), _b64url_decode(auth)
    except (ValueError, TypeError) as exc:
        raise NotificationError(422, "invalid_keys", "Subscription keys must be base64url") from exc
    if len(public) != 65 or public[0] != 4 or len(secret) != 16:
        raise NotificationError(422, "invalid_keys", "Subscription keys have the wrong format")


# --- Subscriptions ----------------------------------------------------------------------

def public_subscription(row: Any) -> dict[str, Any]:
    return {"subscription_id": row["id"], "status": row["status"], "enabled": bool(row["enabled"]),
            "min_severity": row["min_severity"], "created_at": _iso(row["created_at"]),
            "last_success_at": _iso(row["last_success_at"]), "last_failure_at": _iso(row["last_failure_at"]),
            "consecutive_failures": row["consecutive_failures"], "expired_reason": row["expired_reason"]}


def register(endpoint: str, p256dh: str, auth: str, min_severity: str, receipt_base: str | None) -> tuple[dict[str, Any], str]:
    """Create or re-register a subscription; returns (subscription, management_token shown once).

    Re-registering an existing endpoint (only the browser that owns it knows the
    endpoint URL) reactivates it and rotates the token.
    """
    if not push_configured():
        raise NotificationError(503, "push_not_configured", "Push notifications are not configured on this server")
    validate_endpoint(endpoint)
    validate_keys(p256dh, auth)
    token = secrets.token_urlsafe(32)
    now = _now()
    endpoint_hash = _hash(endpoint)
    with get_engine().begin() as connection:
        existing = connection.execute(select(push_subscriptions.c.id).where(
            push_subscriptions.c.endpoint_hash == endpoint_hash)).scalar()
        values = {"endpoint": endpoint, "p256dh": p256dh, "auth": auth, "token_hash": _hash(token),
                  "min_severity": min_severity, "enabled": True, "status": "active", "receipt_base": receipt_base,
                  "updated_at": now, "consecutive_failures": 0, "expired_reason": None}
        if existing:
            connection.execute(update(push_subscriptions).where(push_subscriptions.c.id == existing).values(**values))
            subscription_id = existing
        else:
            limit = int(os.getenv("VITALGUARD_PUSH_MAX_SUBSCRIPTIONS", "1000"))
            active = connection.execute(select(func.count()).select_from(push_subscriptions).where(
                push_subscriptions.c.status == "active")).scalar()
            if active >= limit:
                raise NotificationError(503, "subscription_limit", "The subscription limit for this demo has been reached")
            subscription_id = str(uuid.uuid4())
            connection.execute(insert(push_subscriptions).values(id=subscription_id, endpoint_hash=endpoint_hash,
                                                                 created_at=now, **values))
        row = connection.execute(select(push_subscriptions).where(push_subscriptions.c.id == subscription_id)).mappings().one()
    logger.info("push subscription %s registered (re-registration=%s)", subscription_id[:8], bool(existing))
    return public_subscription(row), token


def _authorized(connection: Connection, subscription_id: str, token: str | None) -> Any:
    row = connection.execute(select(push_subscriptions).where(push_subscriptions.c.id == subscription_id)).mappings().first()
    if row is None:
        raise NotificationError(404, "subscription_not_found", "Subscription not found")
    if not token or not hmac.compare_digest(_hash(token), row["token_hash"]):
        raise NotificationError(403, "not_subscription_owner", "This browser does not own the subscription")
    return row


def get_status(subscription_id: str, token: str | None, limit: int = 20) -> dict[str, Any]:
    with get_engine().connect() as connection:
        row = _authorized(connection, subscription_id, token)
        deliveries = connection.execute(select(push_deliveries).where(push_deliveries.c.subscription_id == subscription_id)
                                        .order_by(desc(push_deliveries.c.id)).limit(limit)).mappings().all()
    return {"subscription": public_subscription(row), "deliveries": [public_delivery(item) for item in deliveries]}


def update_preferences(subscription_id: str, token: str | None, *, enabled: bool | None, min_severity: str | None) -> dict[str, Any]:
    with get_engine().begin() as connection:
        _authorized(connection, subscription_id, token)
        values: dict[str, Any] = {"updated_at": _now()}
        if enabled is not None:
            values["enabled"] = enabled
        if min_severity is not None:
            values["min_severity"] = min_severity
        connection.execute(update(push_subscriptions).where(push_subscriptions.c.id == subscription_id).values(**values))
        row = connection.execute(select(push_subscriptions).where(push_subscriptions.c.id == subscription_id)).mappings().one()
    return public_subscription(row)


def unregister(subscription_id: str, token: str | None) -> None:
    """Delete the subscription (endpoint and keys) and its delivery history."""
    with get_engine().begin() as connection:
        _authorized(connection, subscription_id, token)
        connection.execute(delete(push_deliveries).where(push_deliveries.c.subscription_id == subscription_id))
        connection.execute(delete(push_subscriptions).where(push_subscriptions.c.id == subscription_id))
    logger.info("push subscription %s removed by its owner", subscription_id[:8])


# --- Payloads and enqueueing --------------------------------------------------------------

def alert_payload(alert: dict[str, Any]) -> dict[str, Any]:
    """Lock-screen safe: no patient identifier, vitals, scores or free text from the alert."""
    severity = alert["severity"] if alert["severity"] in SEVERITY_RANK else "high"
    return {"v": 1, "type": "alert", "alert_id": alert["id"], "severity": severity,
            "title": f"VitalGuard: {severity} demo alert",
            "body": "A new synthetic demo alert needs review. Open VitalGuard to see it.",
            "url": f"/#/alerts?alert={int(alert['id'])}", "tag": f"vg-alert-{int(alert['id'])}"}


def test_payload() -> dict[str, Any]:
    return {"v": 1, "type": "test", "severity": "test", "title": "VitalGuard test notification",
            "body": "Push notifications are working on this device.", "url": "/#/settings", "tag": "vg-test"}


def enqueue_for_alert(connection: Connection, alert: dict[str, Any]) -> int:
    """Queue one delivery per eligible active subscription, inside the alert's transaction."""
    rank = SEVERITY_RANK.get(alert.get("severity"), 0)
    eligible = [row for row in connection.execute(select(push_subscriptions.c.id, push_subscriptions.c.min_severity).where(
        push_subscriptions.c.status == "active", push_subscriptions.c.enabled.is_(True))).all()
        if rank >= SEVERITY_RANK.get(row.min_severity, 1)]
    if not eligible:
        return 0
    now = _now()
    payload = json.dumps(alert_payload(alert), separators=(",", ":"))
    rows = [{"subscription_id": row.id, "kind": "alert", "event_key": f"alert:{alert['id']}:created",
             "alert_id": alert["id"], "payload_json": payload, "status": "pending", "attempts": 0,
             "next_attempt_at": now, "created_at": now, "updated_at": now} for row in eligible]
    connection.execute(insert(push_deliveries), rows)
    return len(rows)


def enqueue_test(subscription_id: str, token: str | None) -> dict[str, Any]:
    now = _now()
    with get_engine().begin() as connection:
        row = _authorized(connection, subscription_id, token)
        if row["status"] != "active":
            raise NotificationError(409, "subscription_inactive", "Subscription is not active; enable notifications again")
        result = connection.execute(insert(push_deliveries).values(
            subscription_id=subscription_id, kind="test", event_key=f"test:{uuid.uuid4()}", alert_id=None,
            payload_json=json.dumps(test_payload(), separators=(",", ":")), status="pending", attempts=0,
            next_attempt_at=now, created_at=now, updated_at=now))
        delivery = connection.execute(select(push_deliveries).where(
            push_deliveries.c.id == result.inserted_primary_key[0])).mappings().one()
    return public_delivery(delivery)


def public_delivery(row: Any) -> dict[str, Any]:
    return {"delivery_id": row["id"], "kind": row["kind"], "alert_id": row["alert_id"], "status": row["status"],
            "attempts": row["attempts"], "last_status_code": row["last_status_code"], "last_error": row["last_error"],
            "created_at": _iso(row["created_at"]), "accepted_at": _iso(row["accepted_at"]),
            "displayed_at": _iso(row["displayed_at"]), "clicked_at": _iso(row["clicked_at"]),
            "next_attempt_at": _iso(row["next_attempt_at"]) if row["status"] == "retrying" else None,
            "note": "accepted = taken by the push service, not proof the device showed it"}


# --- Receipts -----------------------------------------------------------------------------

def _receipt_nonce(delivery_id: int) -> str:
    key = (_private_key() or "unconfigured").encode()
    return hmac.new(key, f"receipt:{delivery_id}".encode(), hashlib.sha256).hexdigest()[:32]


def record_receipt(delivery_id: int, nonce: str, event: str) -> None:
    if not hmac.compare_digest(_receipt_nonce(delivery_id), nonce or ""):
        raise NotificationError(403, "invalid_receipt", "Receipt could not be verified")
    column = {"displayed": push_deliveries.c.displayed_at, "clicked": push_deliveries.c.clicked_at}[event]
    with get_engine().begin() as connection:
        changed = connection.execute(update(push_deliveries).where(push_deliveries.c.id == delivery_id, column.is_(None))
                                     .values({column.key: _now()})).rowcount
    if changed:
        logger.info("push delivery %s %s on device", delivery_id, event)


# --- Sending --------------------------------------------------------------------------------

def _claim_due(limit: int, instance: str) -> list[dict[str, Any]]:
    now = _now()
    lease = now + timedelta(seconds=90)
    with get_engine().connect() as connection:
        candidates = connection.execute(select(push_deliveries.c.id).where(
            push_deliveries.c.status.in_(ACTIVE_DELIVERY_STATUSES), push_deliveries.c.next_attempt_at <= now,
            (push_deliveries.c.locked_until.is_(None)) | (push_deliveries.c.locked_until < now))
            .order_by(push_deliveries.c.id).limit(limit)).scalars().all()
    claimed = []
    for delivery_id in candidates:
        with get_engine().begin() as connection:
            # Conditional UPDATE: exactly one instance wins each row.
            won = connection.execute(update(push_deliveries).where(
                push_deliveries.c.id == delivery_id, push_deliveries.c.status.in_(ACTIVE_DELIVERY_STATUSES),
                (push_deliveries.c.locked_until.is_(None)) | (push_deliveries.c.locked_until < now))
                .values(status="sending", locked_until=lease, updated_at=now)).rowcount
            if not won:
                continue
            delivery = connection.execute(select(push_deliveries).where(push_deliveries.c.id == delivery_id)).mappings().one()
            subscription = connection.execute(select(push_subscriptions).where(
                push_subscriptions.c.id == delivery["subscription_id"])).mappings().first()
            claimed.append({"delivery": dict(delivery), "subscription": dict(subscription) if subscription else None})
    return claimed


def _send(delivery: dict[str, Any], subscription: dict[str, Any]) -> tuple[int | None, str | None, float | None]:
    """POST one encrypted message; returns (status_code, error, retry_after_seconds)."""
    from pywebpush import WebPushException, webpush
    payload = json.loads(delivery["payload_json"])
    payload["delivery_id"] = delivery["id"]
    if subscription.get("receipt_base"):
        payload["receipt"] = {"url": subscription["receipt_base"].rstrip("/") + "/api/v1/notifications/receipts",
                              "nonce": _receipt_nonce(delivery["id"])}
    headers = {"Urgency": "high" if payload.get("severity") == "critical" else "normal"}
    if payload.get("tag"):
        headers["Topic"] = payload["tag"][:32]
    try:
        response = webpush(subscription_info={"endpoint": subscription["endpoint"],
                                              "keys": {"p256dh": subscription["p256dh"], "auth": subscription["auth"]}},
                           data=json.dumps(payload, separators=(",", ":")), vapid_private_key=_private_key(),
                           vapid_claims={"sub": _subject()}, ttl=300 if delivery["kind"] == "test" else 3600,
                           headers=headers, timeout=10)
        return response.status_code, None, None
    except WebPushException as exc:
        response = exc.response
        if response is None:
            return None, "push service unreachable", None
        retry_after = response.headers.get("Retry-After")
        return response.status_code, f"push service returned {response.status_code}", (
            float(retry_after) if retry_after and retry_after.isdigit() else None)
    except Exception as exc:  # network errors, timeouts
        return None, type(exc).__name__, None


def _record_outcome(delivery: dict[str, Any], code: int | None, error: str | None, retry_after: float | None) -> str:
    now = _now()
    attempts = delivery["attempts"] + 1
    values: dict[str, Any] = {"attempts": attempts, "last_status_code": code, "last_error": error, "locked_until": None,
                              "updated_at": now}
    subscription_values: dict[str, Any] = {}
    if code in (200, 201, 202):
        status = "accepted"
        values["accepted_at"] = now
        subscription_values = {"last_success_at": now, "consecutive_failures": 0}
    elif code in (404, 410):
        status = "expired"
        subscription_values = {"status": "expired", "expired_reason": f"push service returned {code}",
                               "last_failure_at": now}
    elif code is None or code == 429 or code >= 500:
        status = "retrying" if attempts < MAX_ATTEMPTS else "failed"
        delay = retry_after if retry_after is not None else min(900.0, 10.0 * 2 ** (attempts - 1))
        values["next_attempt_at"] = now + timedelta(seconds=min(delay, 3600))
        subscription_values = {"last_failure_at": now, "consecutive_failures": push_subscriptions.c.consecutive_failures + 1}
    else:
        status = "failed"
        subscription_values = {"last_failure_at": now, "consecutive_failures": push_subscriptions.c.consecutive_failures + 1}
    values["status"] = status
    with get_engine().begin() as connection:
        connection.execute(update(push_deliveries).where(push_deliveries.c.id == delivery["id"]).values(**values))
        if subscription_values:
            connection.execute(update(push_subscriptions).where(
                push_subscriptions.c.id == delivery["subscription_id"]).values(**subscription_values))
        if status == "expired":
            # A gone subscription will never accept anything again.
            connection.execute(update(push_deliveries).where(
                push_deliveries.c.subscription_id == delivery["subscription_id"],
                push_deliveries.c.status.in_(("pending", "retrying"))).values(status="skipped", updated_at=now,
                                                                             last_error="subscription expired"))
    logger.info("push delivery %s sub %s attempt %s -> %s (code %s)", delivery["id"], delivery["subscription_id"][:8],
                attempts, status, code)
    return status


def process_due(limit: int = 20, instance: str = "local") -> list[str]:
    """Claim, send and record due deliveries synchronously (used by the worker and tests)."""
    outcomes = []
    for item in _claim_due(limit, instance):
        delivery, subscription = item["delivery"], item["subscription"]
        if subscription is None or subscription["status"] != "active" or not subscription["enabled"]:
            with get_engine().begin() as connection:
                connection.execute(update(push_deliveries).where(push_deliveries.c.id == delivery["id"]).values(
                    status="skipped", locked_until=None, last_error="subscription inactive", updated_at=_now()))
            outcomes.append("skipped")
            continue
        outcomes.append(_record_outcome(delivery, *_send(delivery, subscription)))
    return outcomes


class NotificationWorker:
    """Background sender: woken after alert commits, and polls for retries."""

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._wake: asyncio.Event | None = None
        self._stopping = False
        self.last_run_at: str | None = None
        self.last_error: str | None = None

    async def start(self) -> None:
        self._stopping = False
        self._wake = asyncio.Event()
        if push_configured():
            self._task = asyncio.create_task(self._run(), name="vitalguard-push-worker")
        else:
            logger.info("Web Push not configured (VAPID keys missing); in-app alerts only")

    async def stop(self) -> None:
        self._stopping = True
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
        self._task = None

    def wake(self) -> None:
        if self._wake is not None:
            self._wake.set()

    async def _run(self) -> None:
        poll = float(os.getenv("VITALGUARD_PUSH_POLL_SECONDS", "5"))
        while not self._stopping:
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=poll)
            except asyncio.TimeoutError:
                pass
            self._wake.clear()
            try:
                while await run_in_threadpool(process_due):
                    pass
                self.last_run_at = _now().isoformat()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.last_error = type(exc).__name__
                logger.warning("push worker iteration failed (%s); will retry", type(exc).__name__)

    def health(self) -> dict[str, Any]:
        return {"configured": push_configured(), "worker_running": self._task is not None and not self._task.done(),
                "last_run_at": self.last_run_at, "last_error": self.last_error}


notifications = NotificationWorker()
