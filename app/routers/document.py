from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Request
from app.dependencies.auth import get_current_user
from app.models.document import Document
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
import os, uuid

from app.tasks import process_document
from app.core.limiter import limiter

router = APIRouter(prefix="/documents", tags=["documents"])

ALLOWED_CONTENT_TYPES = {"application/pdf", "text/plain"}
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

def get_supabase():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise HTTPException(status_code=500, detail="Supabase not configured on server")
    try:
        from supabase import create_client
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase init failed: {str(e)}")


@router.post("/upload")
@limiter.limit("20/minute")
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="File type allowed nahi hai.")

    file_bytes = await file.read()

    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="File 10MB se badi hai")

    # Supabase Storage pe upload karo
    file_id = str(uuid.uuid4())
    storage_path = f"{current_user.tenant_id}/{file_id}_{file.filename}"

    supabase = get_supabase()
    supabase.storage.from_("documents").upload(
        path=storage_path,
        file=file_bytes,
        file_options={"content-type": file.content_type}
    )

    # Public URL lo
    public_url = supabase.storage.from_("documents").get_public_url(storage_path)

    document = Document(
        filename=file.filename,
        tenant_id=current_user.tenant_id,
        file_path=public_url,
        status="queued"
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    # Celery task queue karo — wrapped in try/except so upload still works if Redis is down
    try:
        print(f"Queuing task for document {document.id}")
        result = process_document.delay(
            document_id=str(document.id),
            tenant_id=str(current_user.tenant_id)
        )
        print(f"Task queued with ID: {result.id}")
    except Exception as e:
        print(f"Warning: Could not queue Celery task: {e}")
        # Don't crash — document is saved, just won't be processed automatically

    return {
        "document_id": document.id,
        "filename": document.filename,
        "status": "queued"
    }


@router.get("/{document_id}/status")
async def get_document_status(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.tenant_id == current_user.tenant_id
    ).first()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    from app.models.chunk import Chunk
    chunk_count = db.query(Chunk).filter(Chunk.document_id == document_id).count()

    return {
        "document_id": document_id,
        "filename": document.filename,
        "status": document.status,
        "chunks_created": chunk_count
    }
