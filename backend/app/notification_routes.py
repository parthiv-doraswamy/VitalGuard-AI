"""Web Push endpoints. Subscriptions are device-scoped; X-Subscription-Token proves ownership."""
import os
from fastapi import APIRouter, Header, Request, Response
from starlette.concurrency import run_in_threadpool
from . import notification_service as service
from .notification_service import notifications
from .schemas import PushPreferences, PushReceipt, PushRegistration

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


@router.get("/config")
def push_config():
    """Whether push is available and the VAPID public key (never the private key)."""
    return {"push_available": service.push_configured(), "vapid_public_key": service.vapid_public_key(),
            "min_severity_options": ["high", "critical"], "ownership": "device-scoped token (no user accounts)",
            "fallback": "in-app alert center (/#/alerts)", "demo_only": True}


@router.post("/subscriptions", status_code=201)
async def register_subscription(payload: PushRegistration, request: Request):
    # Receipts from the service worker go back to this API; VITALGUARD_PUBLIC_API_URL overrides behind proxies.
    receipt_base = os.getenv("VITALGUARD_PUBLIC_API_URL") or str(request.base_url).rstrip("/")
    subscription, token = await run_in_threadpool(service.register, payload.subscription.endpoint,
        payload.subscription.keys.p256dh, payload.subscription.keys.auth, payload.min_severity, receipt_base)
    return {"subscription": subscription, "management_token": token, "demo_only": True}


@router.get("/subscriptions/{subscription_id}")
def subscription_status(subscription_id: str, x_subscription_token: str | None = Header(default=None)):
    return {**service.get_status(subscription_id, x_subscription_token), "demo_only": True}


@router.patch("/subscriptions/{subscription_id}")
def subscription_preferences(subscription_id: str, payload: PushPreferences,
                             x_subscription_token: str | None = Header(default=None)):
    return {"subscription": service.update_preferences(subscription_id, x_subscription_token,
            enabled=payload.enabled, min_severity=payload.min_severity), "demo_only": True}


@router.delete("/subscriptions/{subscription_id}", status_code=204)
def remove_subscription(subscription_id: str, x_subscription_token: str | None = Header(default=None)):
    service.unregister(subscription_id, x_subscription_token)
    return Response(status_code=204)


@router.post("/subscriptions/{subscription_id}/test", status_code=202)
async def send_test(subscription_id: str, x_subscription_token: str | None = Header(default=None)):
    delivery = await run_in_threadpool(service.enqueue_test, subscription_id, x_subscription_token)
    notifications.wake()
    return {"delivery": delivery, "note": "Queued. 'accepted' later means the push service took it, not that the device showed it.",
            "demo_only": True}


@router.post("/receipts", status_code=204)
def delivery_receipt(payload: PushReceipt):
    """Called by the service worker when a notification is shown or clicked."""
    service.record_receipt(payload.delivery_id, payload.nonce, payload.event)
    return Response(status_code=204)
