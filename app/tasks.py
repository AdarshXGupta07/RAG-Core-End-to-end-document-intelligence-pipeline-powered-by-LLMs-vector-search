from dotenv import load_dotenv
load_dotenv()

import httpx
from app.celery_app import celery_app
from app.database import SessionLocal
from app.models.document import Document
from app.models.chunk import Chunk
from app.services.pdf_service import extract_text_from_pdf
from app.services.chunker import chunk_text
from app.services.embedding_service import get_embeddings_batch

@celery_app.task(bind=True)
def process_document(self, document_id: str, tenant_id: str):
    db = SessionLocal()
    document = None

    try:
        document = db.query(Document).filter(
            Document.id == document_id
        ).first()

        document.status = "processing"
        db.commit()

        if document.file_path.startswith("http"):
            response = httpx.get(document.file_path)
            file_bytes = response.content
        else:
            with open(document.file_path, "rb") as f:
                file_bytes = f.read()

        text = extract_text_from_pdf(file_bytes)

        # FIX 1: NUL bytes strip karo — PostgreSQL inhe reject karta hai
        text = text.replace('\x00', '').strip()

        # FIX 2: Agar text empty hai (scanned/image PDF) toh early return
        if not text:
            document.status = "failed"
            db.commit()
            return {"status": "failed", "chunks": 0, "reason": "No text extracted — possibly a scanned/image PDF"}

        chunks = chunk_text(text)

        chunk_objects = []
        for i, c in enumerate(chunks):
            # FIX 3: Individual chunk mein bhi NUL ho sakta hai
            clean_content = c.replace('\x00', '').strip()
            if not clean_content:
                continue
            chunk = Chunk(
                content=clean_content,
                chunk_index=i,
                document_id=document_id,
                tenant_id=tenant_id,
                embedding=None
            )
            db.add(chunk)
            chunk_objects.append(chunk)
        db.commit()

        BATCH_SIZE = 50
        for i in range(0, len(chunk_objects), BATCH_SIZE):
            batch = chunk_objects[i:i + BATCH_SIZE]
            embeddings = get_embeddings_batch([c.content for c in batch])
            for chunk, emb in zip(batch, embeddings):
                chunk.embedding = emb
            db.commit()

        document.status = "completed"
        db.commit()

        return {"status": "completed", "chunks": len(chunk_objects)}

    except Exception as e:
        # FIX 4: Session rollback karo warna corrupted state mein rehta hai
        db.rollback()
        if document:
            document.status = "failed"
            db.commit()
        raise e

    finally:
        db.close()