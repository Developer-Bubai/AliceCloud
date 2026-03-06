import os, jwt, secrets
from datetime import datetime, timedelta
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

JWT_SECRET = os.getenv("JWT_SECRET", "alice-secret-bubai-2025")
JWT_EXPIRE = 30

security = HTTPBearer(auto_error=False)

def create_token(data: dict) -> str:
    payload = {**data, "exp": datetime.utcnow() + timedelta(days=JWT_EXPIRE)}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def verify_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired. Please login again.")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token. Please login.")

def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)):
    if not credentials:
        raise HTTPException(401, "Not authenticated. Please login at /auth/google")
    payload = verify_token(credentials.credentials)
    from app.database import db
    user = db.get_user(payload["user_id"])
    if not user:
        raise HTTPException(401, "User not found.")
    return user

import time
from collections import defaultdict
_req_log = defaultdict(list)
PLAN_LIMITS = {"free": 100, "pro": 2000, "owner": 99999}

def check_limit(user_id: str, plan: str = "free"):
    now = time.time()
    day = 86400
    limit = PLAN_LIMITS.get(plan, 100)
    _req_log[user_id] = [t for t in _req_log[user_id] if now - t < day]
    used = len(_req_log[user_id])
    remaining = max(0, limit - used)
    if used >= limit:
        return False, f"Daily limit of {limit} messages reached. Resets in 24h.", 0
    _req_log[user_id].append(now)
    return True, "ok", remaining - 1
