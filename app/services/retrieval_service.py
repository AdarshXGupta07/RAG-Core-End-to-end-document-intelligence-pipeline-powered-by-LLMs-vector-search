from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Dict
from app.services.embedding_service import get_query_embedding


def retrieve_chunks(
    query: str,
    tenant_id: str,
    db: Session,
    top_k: int = 8
) -> List[Dict]:
    """
    Vector similarity search.
    Sirf current tenant ke chunks mein search karega.
    """

    query_embedding = get_query_embedding(query)
    embedding_str = "[" + ",".join(map(str, query_embedding)) + "]"

    result = db.execute(
        text("""
            SELECT
                c.id,
                c.content,
                c.document_id,
                c.chunk_index,
                d.filename,
                1 - (c.embedding <=> CAST(:embedding AS vector)) AS similarity_score
            FROM chunks c
            JOIN documents d
                ON c.document_id = d.id
            WHERE c.tenant_id = :tenant_id
              AND c.embedding IS NOT NULL
            ORDER BY c.embedding <=> CAST(:embedding AS vector)
            LIMIT :top_k
        """),
        {
            "embedding": embedding_str,
            "tenant_id": tenant_id,
            "top_k": top_k
        }
    )

    rows = result.fetchall()

    return [
        {
            "chunk_id": str(row.id),
            "content": row.content,
            "document_id": str(row.document_id),
            "filename": row.filename,
            "chunk_index": row.chunk_index,
            "similarity_score": float(row.similarity_score)
        }
        for row in rows
    ]