import base64
import hashlib
import hmac
import json
import os
import time
import binascii
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
from .db import get_db
from .models import ApplicationUser


def secret():
    value = os.getenv("SESSION_SECRET", "")
    if len(value) < 32:
        raise HTTPException(503, "Set SESSION_SECRET to at least 32 characters in .env")
    return value.encode()


def token(user_id):
    payload = base64.urlsafe_b64encode(json.dumps({"id": user_id, "exp": int(time.time())+28800}).encode()).decode()
    return payload+"."+hmac.new(secret(), payload.encode(), hashlib.sha256).hexdigest()


def actor(request: Request, db: Session = Depends(get_db)):
    raw = request.cookies.get("safeops_session", "")
    try:
        payload, signature = raw.rsplit(".", 1)
        expected = hmac.new(secret(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected): raise ValueError()
        decoded = json.loads(base64.urlsafe_b64decode(payload))
        if decoded["exp"] < time.time(): raise ValueError()
        user = db.get(ApplicationUser, decoded["id"])
        if not user: raise ValueError()
        return user
    except (ValueError, KeyError, binascii.Error, json.JSONDecodeError):
        raise HTTPException(401, "Sign in to continue")


def permit(*roles):
    def dependency(user=Depends(actor)):
        if user.role not in roles: raise HTTPException(403, "Your role cannot perform this operation")
        return user
    return dependency
