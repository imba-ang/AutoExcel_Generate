from __future__ import annotations

import hashlib
import hmac
import time


COOKIE_NAME = "autoexcel_teacher"
SESSION_SECONDS = 12 * 60 * 60


def make_teacher_token(secret: str) -> str:
    timestamp = str(int(time.time()))
    signature = hmac.new(secret.encode(), timestamp.encode(), hashlib.sha256).hexdigest()
    return f"{timestamp}.{signature}"


def verify_teacher_token(token: str | None, secret: str) -> bool:
    if not token or "." not in token:
        return False
    timestamp, signature = token.split(".", 1)
    if not timestamp.isdigit():
        return False
    age = int(time.time()) - int(timestamp)
    if age < 0 or age > SESSION_SECONDS:
        return False
    expected = hmac.new(secret.encode(), timestamp.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)

