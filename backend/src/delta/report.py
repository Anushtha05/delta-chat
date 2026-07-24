"""Delta report generation — JSON and Markdown formats.

Produces structured reports from DeltaRecords for persistence and human review.
"""

from datetime import datetime, timezone

from src.delta.model import DeltaRecord


def generate_json_report(
    delta_records: list[DeltaRecord],
    doc_a_meta: dict,
    doc_b_meta: dict,
) -> dict:
    """Generate a structured JSON report from delta records.

    Args:
        delta_records: List of DeltaRecord instances from the comparison engine.
        doc_a_meta: Metadata dict for document A (document_id, revision, format, source_filename, etc.)
        doc_b_meta: Metadata dict for document B.

    Returns:
        A dict matching the report schema:
        {
            "document_a": {...},
            "document_b": {...},
            "generated_at": ISO timestamp,
            "summary": {"added": n, "removed": n, "modified": n},
            "changes": [...]
        }
    """
    added = [r for r in delta_records if r.change_type == "added"]
    removed = [r for r in delta_records if r.change_type == "removed"]
    modified = [r for r in delta_records if r.change_type == "modified"]

    changes = []
    for record in delta_records:
        change_entry = {
            "change_id": record.change_id,
            "change_type": record.change_type,
            "element_type": record.element_type,
            "page": record.page,
            "old_value": record.old_value,
            "new_value": record.new_value,
            "description": record.description,
            "confidence": record.confidence,
            "bbox_a": list(record.bbox_a) if record.bbox_a else None,
            "bbox_b": list(record.bbox_b) if record.bbox_b else None,
        }
        changes.append(change_entry)

    return {
        "document_a": doc_a_meta,
        "document_b": doc_b_meta,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "added": len(added),
            "removed": len(removed),
            "modified": len(modified),
        },
        "changes": changes,
    }


def generate_markdown_report(json_report: dict) -> str:
    """Generate a human-readable Markdown report from a JSON report dict.

    Format:
    - Title with document identifiers
    - Summary table (added/removed/modified counts)
    - Changes grouped by change_type, each with location, type, old/new value,
      description, and confidence.
    """
    doc_a = json_report["document_a"]
    doc_b = json_report["document_b"]
    summary = json_report["summary"]
    changes = json_report["changes"]
    generated_at = json_report["generated_at"]

    lines: list[str] = []

    # Title
    lines.append(f"# Delta Report: {doc_a.get('document_id', 'Doc A')} vs {doc_b.get('document_id', 'Doc B')}")
    lines.append("")
    lines.append(f"**Generated:** {generated_at}")
    lines.append("")

    # Document metadata
    lines.append("## Documents")
    lines.append("")
    lines.append(f"| | Document A | Document B |")
    lines.append(f"|---|---|---|")
    lines.append(f"| **ID** | {doc_a.get('document_id', '-')} | {doc_b.get('document_id', '-')} |")
    lines.append(f"| **Revision** | {doc_a.get('revision', '-')} | {doc_b.get('revision', '-')} |")
    lines.append(f"| **Format** | {doc_a.get('format', '-')} | {doc_b.get('format', '-')} |")
    lines.append(f"| **Filename** | {doc_a.get('source_filename', '-')} | {doc_b.get('source_filename', '-')} |")
    lines.append("")

    # Summary table
    lines.append("## Summary")
    lines.append("")
    lines.append("| Change Type | Count |")
    lines.append("|---|---|")
    lines.append(f"| Added | {summary['added']} |")
    lines.append(f"| Removed | {summary['removed']} |")
    lines.append(f"| Modified | {summary['modified']} |")
    lines.append(f"| **Total** | **{summary['added'] + summary['removed'] + summary['modified']}** |")
    lines.append("")

    # Group changes by type
    grouped: dict[str, list[dict]] = {"added": [], "removed": [], "modified": []}
    for change in changes:
        grouped[change["change_type"]].append(change)

    # Render each group
    type_labels = {"added": "Added Elements", "removed": "Removed Elements", "modified": "Modified Elements"}
    type_icons = {"added": "🟢", "removed": "🔴", "modified": "🟡"}

    for change_type in ["modified", "added", "removed"]:
        group = grouped[change_type]
        if not group:
            continue

        icon = type_icons[change_type]
        label = type_labels[change_type]
        lines.append(f"## {icon} {label} ({len(group)})")
        lines.append("")

        for i, change in enumerate(group, 1):
            lines.append(f"### {i}. [{change['element_type']}] Page {change['page']}")
            lines.append("")

            if change_type == "modified":
                lines.append(f"- **Old value:** `{change['old_value'] or ''}`")
                lines.append(f"- **New value:** `{change['new_value'] or ''}`")
            elif change_type == "added":
                lines.append(f"- **Value:** `{change['new_value'] or ''}`")
            elif change_type == "removed":
                lines.append(f"- **Value:** `{change['old_value'] or ''}`")

            lines.append(f"- **Description:** {change['description']}")
            lines.append(f"- **Confidence:** {change['confidence']:.2f}")

            if change.get("bbox_a"):
                lines.append(f"- **Location A:** ({', '.join(f'{v:.1f}' for v in change['bbox_a'])})")
            if change.get("bbox_b"):
                lines.append(f"- **Location B:** ({', '.join(f'{v:.1f}' for v in change['bbox_b'])})")

            lines.append("")

    if not any(grouped.values()):
        lines.append("*No changes detected between the two documents.*")
        lines.append("")

    return "\n".join(lines)
