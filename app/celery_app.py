import os
import ssl
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# SSL config only needed for Upstash (rediss://)
use_ssl = REDIS_URL.startswith("rediss://")
ssl_config = {"ssl_cert_reqs": ssl.CERT_NONE} if use_ssl else None

celery_app = Celery(
    "rag_platform",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["app.tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
)

if ssl_config:
    celery_app.conf.update(
        broker_use_ssl=ssl_config,
        redis_backend_use_ssl=ssl_config,
    )
