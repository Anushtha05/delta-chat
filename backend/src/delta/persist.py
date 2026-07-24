"""Persistence for delta reports and records.

- Full JSON report → MongoDB collection `delta_reports`
- Individual DeltaRecords → MySQL table `delta_records`
- Markdown + JSON files → backend/outputs/reports/
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import Column, DateTime, Float, Integer, String, Table, MetaData, Text, text

from src.delta.model import DeltaRecord

logger = logging.getLogger(__name__)

# MySQL table definition for delta_records
_metadata = MetaData()

delta_records_table = Table(
    "delta_records",
    _metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("change_id", String(255), nullable=False, unique=True),
    Column("document_a", String(255), nullable=False),
    Column("document_b", String(255), nullable=False),
    Column("change_type", String(50), nullable=False),
    Column("element_type", String(100), nullable=False),
    Column("page", Integer, nullable=False),
    Column("old_value", Text, nullable=True),
    Column("new_value", Text, nullable=True),
    Column("description", Text, nullable=True),
    Column("confidence", Float, nullable=False, default=1.0),
    Column("created_at", DateTime, nullable=False),
)

# Base path for report output files
_OUTPUTS_DIR = Path(__file__).resolve().parent.parent.parent / "outputs" / "reports"


def _ensure_outputs_dir() -> Path:
    """Ensure the outputs/reports directory exists."""
    _OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    return _OUTPUTS_DIR


def persist_report_to_mongo(json_report: dict) -> str:
    """Store the full JSON report in MongoDB collection `delta_reports`.

    Keyed by {document_a.document_id, document_b.document_id, generated_at}.
    Uses upsert: replaces existing report for the same pair.

    Returns the MongoDB document _id as a string.
    """
    from src.db.mongo import get_db

    db = get_db()
    collection = db["delta_reports"]

    doc_a_id = json_report["document_a"].get("document_id", "")
    doc_b_id = json_report["document_b"].get("document_id", "")

    result = collection.replace_one(
        {"document_a.document_id": doc_a_id, "document_b.document_id": doc_b_id},
        json_report,
        upsert=True,
    )

    if result.upserted_id:
        mongo_id = str(result.upserted_id)
    else:
        existing = collection.find_one(
            {"document_a.document_id": doc_a_id, "document_b.document_id": doc_b_id},
            {"_id": 1},
        )
        mongo_id = str(existing["_id"]) if existing else "unknown"

    logger.info("Persisted delta report to MongoDB (id=%s)", mongo_id)
    return mongo_id


def persist_records_to_mysql(records: list[DeltaRecord]) -> int:
    """Insert DeltaRecords into MySQL table `delta_records`.

    Uses INSERT IGNORE semantics on change_id to handle re-runs gracefully.
    Returns the number of rows inserted.
    """
    from src.db.mysql import _get_engine

    engine = _get_engine()
    _metadata.create_all(engine, checkfirst=True)

    inserted = 0
    with engine.begin() as conn:
        for record in records:
            # Check if already exists
            existing = conn.execute(
                text("SELECT id FROM delta_records WHERE change_id = :cid"),
                {"cid": record.change_id},
            ).fetchone()

            if existing:
                continue

            conn.execute(
                delta_records_table.insert().values(
                    change_id=record.change_id,
                    document_a=record.document_a,
                    document_b=record.document_b,
                    change_type=record.change_type,
                    element_type=record.element_type,
                    page=record.page,
                    old_value=record.old_value,
                    new_value=record.new_value,
                    description=record.description,
                    confidence=record.confidence,
                    created_at=record.created_at,
                )
            )
            inserted += 1

    logger.info("Persisted %d delta records to MySQL", inserted)
    return inserted


def write_report_files(
    json_report: dict,
    markdown_report: str,
    document_a_id: str,
    document_b_id: str,
) -> dict:
    """Write the JSON and Markdown reports to the outputs/reports/ directory.

    Filenames: {document_a_id}_vs_{document_b_id}.json / .md

    Returns dict with the file paths written.
    """
    output_dir = _ensure_outputs_dir()

    # Sanitize IDs for filenames
    safe_a = document_a_id.replace("/", "_").replace(" ", "_")
    safe_b = document_b_id.replace("/", "_").replace(" ", "_")
    base_name = f"{safe_a}_vs_{safe_b}"

    json_path = output_dir / f"{base_name}.json"
    md_path = output_dir / f"{base_name}.md"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_report, f, indent=2, ensure_ascii=False, default=str)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(markdown_report)

    logger.info("Wrote report files: %s, %s", json_path.name, md_path.name)
    return {"json_path": str(json_path), "md_path": str(md_path)}


def persist_all(
    json_report: dict,
    markdown_report: str,
    delta_records: list[DeltaRecord],
    document_a_id: str,
    document_b_id: str,
) -> dict:
    """Persist everything: MongoDB report, MySQL records, and output files.

    Returns a summary dict with all persistence results.
    """
    mongo_id = persist_report_to_mongo(json_report)
    mysql_count = persist_records_to_mysql(delta_records)
    file_paths = write_report_files(json_report, markdown_report, document_a_id, document_b_id)

    return {
        "mongo_id": mongo_id,
        "mysql_records_inserted": mysql_count,
        "files": file_paths,
    }
