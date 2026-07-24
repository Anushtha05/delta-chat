"""Persistence for ingested documents.

After ingestion produces a CanonicalDocument:
- Store the full document as JSON in MongoDB collection `canonical_documents`
  (keyed by {document_id, revision}).
- Insert/update a summary row in MySQL table `documents` for structured querying.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Table, MetaData, text

from src.canonical.model import CanonicalDocument

logger = logging.getLogger(__name__)

# MySQL table definition
_metadata = MetaData()

documents_table = Table(
    "documents",
    _metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("document_id", String(255), nullable=False),
    Column("revision", String(100), nullable=False),
    Column("format", String(50), nullable=False),
    Column("source_filename", String(500), nullable=False),
    Column("ingested_at", DateTime, nullable=False),
    Column("page_count", Integer, nullable=False),
    Column("element_count", Integer, nullable=False),
)


def persist_to_mongo(doc: CanonicalDocument) -> str:
    """Store the CanonicalDocument in MongoDB.

    Uses upsert semantics: if a document with the same (document_id, revision)
    exists, it is replaced.

    Returns the MongoDB document _id as a string.
    """
    from src.db.mongo import get_db

    db = get_db()
    collection = db["canonical_documents"]

    doc_dict = doc.model_dump(mode="json")

    result = collection.replace_one(
        {"document_id": doc.document_id, "revision": doc.revision},
        doc_dict,
        upsert=True,
    )

    if result.upserted_id:
        mongo_id = str(result.upserted_id)
    else:
        # Find the existing doc's id
        existing = collection.find_one(
            {"document_id": doc.document_id, "revision": doc.revision},
            {"_id": 1},
        )
        mongo_id = str(existing["_id"]) if existing else "unknown"

    logger.info(
        "Persisted document %s rev %s to MongoDB (id=%s)",
        doc.document_id, doc.revision, mongo_id,
    )
    return mongo_id


def persist_to_mysql(doc: CanonicalDocument) -> int:
    """Insert or update the document summary in MySQL.

    Returns the row id.
    """
    from src.db.mysql import _get_engine

    engine = _get_engine()

    # Ensure table exists
    _metadata.create_all(engine, checkfirst=True)

    element_count = sum(len(page.elements) for page in doc.pages)

    with engine.begin() as conn:
        # Check if record exists
        existing = conn.execute(
            text(
                "SELECT id FROM documents WHERE document_id = :doc_id AND revision = :rev"
            ),
            {"doc_id": doc.document_id, "rev": doc.revision},
        ).fetchone()

        if existing:
            conn.execute(
                text(
                    "UPDATE documents SET format = :fmt, source_filename = :fname, "
                    "ingested_at = :ts, page_count = :pages, element_count = :elems "
                    "WHERE id = :id"
                ),
                {
                    "fmt": doc.format,
                    "fname": doc.source_filename,
                    "ts": doc.ingested_at,
                    "pages": len(doc.pages),
                    "elems": element_count,
                    "id": existing[0],
                },
            )
            return existing[0]
        else:
            result = conn.execute(
                documents_table.insert().values(
                    document_id=doc.document_id,
                    revision=doc.revision,
                    format=doc.format,
                    source_filename=doc.source_filename,
                    ingested_at=doc.ingested_at,
                    page_count=len(doc.pages),
                    element_count=element_count,
                )
            )
            row_id = result.inserted_primary_key[0]
            logger.info(
                "Persisted document %s rev %s to MySQL (id=%d)",
                doc.document_id, doc.revision, row_id,
            )
            return row_id


def persist(doc: CanonicalDocument) -> dict:
    """Persist to both MongoDB and MySQL. Returns summary dict."""
    mongo_id = persist_to_mongo(doc)
    mysql_id = persist_to_mysql(doc)
    return {"mongo_id": mongo_id, "mysql_id": mysql_id}
