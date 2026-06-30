# Main application entry point
import os
import uuid
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers.auth import router as auth_router
from app.routers.document import router as document_router
from app.routers.query import router as query_router
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from app.core.limiter import limiter
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.logging_config import setup_logging, request_id_var
from app.routers import health

load_dotenv(override=False)
setup_logging()


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        req_id = str(uuid.uuid4())
        token = request_id_var.set(req_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        request_id_var.reset(token)
        return response


app = FastAPI()

origins_env = os.getenv("CORS_ORIGINS")
if origins_env:
    origins = [o.strip() for o in origins_env.split(",")]
else:
    origins = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
        "https://rag-platform-llm.netlify.app",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RequestIdMiddleware)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.include_router(auth_router)
app.include_router(document_router)
app.include_router(query_router)
app.include_router(health.router)