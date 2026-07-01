import os
from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request
from jose import jwt
from app.config import SECRET_KEY, ALGORITHM


def get_tenant_key(request: Request) -> str:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return get_remote_address(request)
    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return f"tenant:{payload.get('tenant_id', 'unknown')}"
    except Exception:
        return get_remote_address(request)


redis_url = os.getenv("REDIS_URL", "").strip('"').strip("'")

# Use memory storage if Redis URL not set or if it's Upstash (avoid 500k limit crashes)
# Switch to Redis when Railway Redis is available
if redis_url and not redis_url.startswith("rediss://default:"):
    storage_uri = redis_url
else:
    storage_uri = "memory://"

limiter = Limiter(key_func=get_tenant_key, storage_uri=storage_uri)
