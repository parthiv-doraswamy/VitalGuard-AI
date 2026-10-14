"""Generate a VAPID key pair for Web Push.

    python backend/scripts/generate_vapid_keys.py

Prints environment lines. Put VITALGUARD_VAPID_PRIVATE_KEY only in the backend
service's private environment (never in git, frontend VITE_ variables, or logs).
The public key is derived by the API and served from /api/v1/notifications/config.
Rotating the key invalidates every existing browser subscription.
"""
import base64

from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid

vapid = Vapid()
vapid.generate_keys()
private_raw = vapid.private_key.private_numbers().private_value.to_bytes(32, "big")
public_raw = vapid.public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
encode = lambda raw: base64.urlsafe_b64encode(raw).decode().rstrip("=")  # noqa: E731
print("VITALGUARD_VAPID_PRIVATE_KEY=" + encode(private_raw))
print("VITALGUARD_VAPID_SUBJECT=mailto:you@example.org")
print("# public key (served automatically by the API): " + encode(public_raw))
