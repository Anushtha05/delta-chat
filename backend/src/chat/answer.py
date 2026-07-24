"""Grounded chat orchestrator — retrieval → prompt → LLM → citation resolution.

Every answer must be traceable to real retrieved chunks. The system prompt enforces
this constraint, and citation parsing validates it. If the LLM hallucinates chunk_ids
or fails to provide citations, we handle it gracefully.
"""

import json
import logging
import re

from pydantic import BaseModel

from src.chat.llm import LLMClient, LLMResponse
from src.chat.retriever import Chunk, Retriever

logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────

_FALLBACK_ANSWER = (
    "I could not find sufficient evidence in PID A, PID B, or the delta report "
    "to answer this confidently."
)

_SYSTEM_PROMPT = """\
You are Delta Chat, a technical assistant for comparing engineering P&ID documents.

STRICT RULES:
1. ONLY answer using information from the provided CHUNKS below. Do NOT use any outside knowledge.
2. Every factual claim in your answer MUST be traceable to a specific chunk.
3. If the chunks do not contain enough information to answer the question, respond with EXACTLY:
   "I could not find sufficient evidence in PID A, PID B, or the delta report to answer this confidently."
4. Your response MUST be valid JSON with this exact structure:
   {{"answer": "your answer text here", "citations": ["chunk_id_1", "chunk_id_2"]}}
5. The "citations" array must list the chunk_ids you used to form your answer.
6. Do NOT invent or hallucinate chunk_ids. Only use chunk_ids from the CHUNKS provided.

CHUNKS:
{chunks_text}
"""

_RETRY_SYSTEM_PROMPT = """\
You previously failed to return valid JSON. Return ONLY a JSON object with NO other text.
The format must be exactly: {{"answer": "your text", "citations": ["chunk_id_1"]}}
Use ONLY chunk_ids from the CHUNKS provided. If you cannot answer from the chunks, set answer to:
"I could not find sufficient evidence in PID A, PID B, or the delta report to answer this confidently."

CHUNKS:
{chunks_text}
"""


# ─── Response model ───────────────────────────────────────────────────────────


class ChatAnswer(BaseModel):
    """Final chat response with grounded citations."""
    answer: str
    citations: list[str]  # Human-readable citation labels
    chunk_ids: list[str]  # Raw chunk_ids used
    input_tokens: int
    output_tokens: int
    model: str


# ─── Prompt building ─────────────────────────────────────────────────────────


def _format_chunks_for_prompt(chunks: list[Chunk]) -> str:
    """Format retrieved chunks as labeled text blocks for the LLM prompt."""
    parts: list[str] = []
    for chunk in chunks:
        header = f"[CHUNK chunk_id={chunk.chunk_id} source={chunk.source} document={chunk.document_id} page={chunk.page}]"
        parts.append(f"{header}\n{chunk.text}\n[/CHUNK]")
    return "\n\n".join(parts)


def build_prompt(question: str, retrieved_chunks: list[Chunk]) -> tuple[str, str]:
    """Build system and user prompts for the grounded chat call.

    Returns (system_prompt, user_prompt).
    """
    chunks_text = _format_chunks_for_prompt(retrieved_chunks)
    system = _SYSTEM_PROMPT.format(chunks_text=chunks_text)
    user = f"Question: {question}"
    return system, user


# ─── Response parsing ─────────────────────────────────────────────────────────


def _parse_llm_response(text: str) -> tuple[str, list[str]]:
    """Parse the LLM response to extract answer and citations.

    Tries multiple strategies:
    1. Direct JSON parse of the full text
    2. Extract JSON block from markdown code fences
    3. Regex extraction of answer and citations fields

    Returns (answer_text, list_of_chunk_ids).
    Raises ValueError if parsing fails completely.
    """
    # Strategy 1: direct JSON parse
    try:
        data = json.loads(text.strip())
        if isinstance(data, dict) and "answer" in data:
            answer = data["answer"]
            citations = data.get("citations", [])
            if isinstance(citations, list):
                return answer, [str(c) for c in citations]
            return answer, []
    except (json.JSONDecodeError, TypeError):
        pass

    # Strategy 2: extract from code fences
    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(1))
            if isinstance(data, dict) and "answer" in data:
                answer = data["answer"]
                citations = data.get("citations", [])
                if isinstance(citations, list):
                    return answer, [str(c) for c in citations]
                return answer, []
        except (json.JSONDecodeError, TypeError):
            pass

    # Strategy 3: regex extraction
    answer_match = re.search(r'"answer"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
    citations_match = re.search(r'"citations"\s*:\s*\[(.*?)\]', text)

    if answer_match:
        answer = answer_match.group(1).replace('\\"', '"').replace("\\n", "\n")
        citations = []
        if citations_match:
            raw = citations_match.group(1)
            citations = [c.strip().strip('"').strip("'") for c in raw.split(",") if c.strip()]
        return answer, citations

    raise ValueError(f"Could not parse LLM response as JSON: {text[:200]}...")


# ─── Citation resolution ─────────────────────────────────────────────────────


def _resolve_citations(chunk_ids: list[str], retrieved_chunks: list[Chunk]) -> list[str]:
    """Resolve raw chunk_ids to human-readable citation labels.

    Format: "[SOURCE, Page N, first_few_words...]" or "[DELTA_REPORT, change_id]"
    Only includes chunk_ids that actually exist in the retrieved set.
    """
    chunk_map = {c.chunk_id: c for c in retrieved_chunks}
    labels: list[str] = []

    for cid in chunk_ids:
        chunk = chunk_map.get(cid)
        if not chunk:
            continue  # Skip hallucinated chunk_ids

        if chunk.source == "DELTA_REPORT":
            label = f"[DELTA_REPORT, Page {chunk.page}, {chunk.delta_change_id or cid[:8]}]"
        else:
            # Take first ~40 chars of text as context
            preview = chunk.text[:40].replace("\n", " ").strip()
            if len(chunk.text) > 40:
                preview += "..."
            label = f"[{chunk.source}, Page {chunk.page}, \"{preview}\"]"

        labels.append(label)

    return labels


# ─── Main orchestrator ────────────────────────────────────────────────────────


async def generate_grounded_answer(
    question: str,
    llm_client: LLMClient,
    retriever: Retriever,
    document_a_id: str,
    document_b_id: str,
) -> ChatAnswer:
    """Full grounded chat pipeline: retrieve → prompt → generate → parse → cite.

    If retrieval returns no chunks, returns the fallback answer immediately.
    If LLM response parsing fails, retries once with a stricter prompt.
    """
    # Determine document scope for retrieval
    delta_doc_id = f"{document_a_id}_vs_{document_b_id}"
    scope = [document_a_id, document_b_id, delta_doc_id]

    # Retrieve relevant chunks
    chunks = retriever.retrieve(query=question, document_scope=scope, top_k=6)

    if not chunks:
        return ChatAnswer(
            answer=_FALLBACK_ANSWER,
            citations=[],
            chunk_ids=[],
            input_tokens=0,
            output_tokens=0,
            model="none",
        )

    # Build prompt and call LLM
    system_prompt, user_prompt = build_prompt(question, chunks)
    llm_response: LLMResponse = await llm_client.generate(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=800,
    )

    total_input = llm_response.input_tokens
    total_output = llm_response.output_tokens

    # Parse response
    try:
        answer_text, cited_ids = _parse_llm_response(llm_response.text)
    except ValueError:
        # Retry with stricter prompt
        logger.warning("First LLM response parse failed, retrying with strict JSON prompt")
        retry_system = _RETRY_SYSTEM_PROMPT.format(
            chunks_text=_format_chunks_for_prompt(chunks)
        )
        retry_response = await llm_client.generate(
            system_prompt=retry_system,
            user_prompt=user_prompt,
            max_tokens=800,
        )
        total_input += retry_response.input_tokens
        total_output += retry_response.output_tokens

        try:
            answer_text, cited_ids = _parse_llm_response(retry_response.text)
        except ValueError:
            # Give up — return the raw text as-is with no citations
            logger.error("Both LLM parse attempts failed. Returning raw response.")
            answer_text = llm_response.text
            cited_ids = []

    # Filter citations to only include real chunk_ids from our retrieved set
    valid_chunk_ids = {c.chunk_id for c in chunks}
    verified_ids = [cid for cid in cited_ids if cid in valid_chunk_ids]

    # Resolve to human-readable
    citation_labels = _resolve_citations(verified_ids, chunks)

    return ChatAnswer(
        answer=answer_text,
        citations=citation_labels,
        chunk_ids=verified_ids,
        input_tokens=total_input,
        output_tokens=total_output,
        model=llm_response.model,
    )


async def generate_delta_explanation(
    llm_client: LLMClient,
    json_report: dict,
) -> str:
    """Generate a human-friendly narrative summary of all delta changes.

    This is an optional enrichment — clearly separated from deterministic descriptions.
    The LLM summarizes ALL changes together into a coherent paragraph.
    """
    summary = json_report.get("summary", {})
    changes = json_report.get("changes", [])

    # Build a condensed representation of changes for the LLM
    change_lines: list[str] = []
    for i, c in enumerate(changes[:50]):  # Cap at 50 to avoid token overflow
        if c["change_type"] == "modified":
            line = f"- Modified ({c['element_type']}, p{c['page']}): \"{c['old_value']}\" → \"{c['new_value']}\""
        elif c["change_type"] == "added":
            line = f"- Added ({c['element_type']}, p{c['page']}): \"{c['new_value']}\""
        else:
            line = f"- Removed ({c['element_type']}, p{c['page']}): \"{c['old_value']}\""
        change_lines.append(line)

    if len(changes) > 50:
        change_lines.append(f"- ... and {len(changes) - 50} more changes")

    system = (
        "You are a technical writer summarizing engineering document changes. "
        "Write a concise, professional narrative (2-4 paragraphs) summarizing the "
        "key differences between the two P&ID documents. Focus on engineering-significant "
        "changes (equipment, instruments, pressures, flows) rather than trivial text edits. "
        "Be specific about what changed."
    )

    user = (
        f"Summary: {summary['added']} additions, {summary['removed']} removals, "
        f"{summary['modified']} modifications.\n\n"
        f"Changes:\n" + "\n".join(change_lines)
    )

    response = await llm_client.generate(system_prompt=system, user_prompt=user, max_tokens=600)
    return response.text
