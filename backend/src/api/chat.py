"""Chat API endpoints — grounded Q&A and delta explanation.

POST /api/chat — ask a question about compared documents, get a grounded answer
POST /api/compare/{a}/{b}/explain — LLM narrative summary of delta changes
"""

import logging
import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.chat.answer import generate_grounded_answer, generate_delta_explanation, ChatAnswer
from src.chat.llm import LLMRequestError, get_llm_client
from src.chat.retriever import KeywordFuzzyRetriever
from src.observability.tracing import RequestTrace
from src.observability.metrics import metrics
from src.observability.logging import log_event

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    """Request body for POST /api/chat."""
    question: str
    document_a_id: str
    document_b_id: str


@router.post("/api/chat")
async def chat(request: ChatRequest):
    """Ask a grounded question about two compared documents."""
    trace = RequestTrace()
    trace.endpoint = "POST /api/chat"

    if not request.question.strip():
        trace.finish("error")
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    try:
        llm_client = get_llm_client()
    except ValueError as e:
        trace.finish("error")
        raise HTTPException(
            status_code=503,
            detail=f"LLM client not configured: {e}. Set OPENROUTER_API_KEY.",
        )

    retriever = KeywordFuzzyRetriever()

    try:
        # Retrieval stage
        with trace.stage("retrieval") as ret_stage:
            ret_stage.set("question", request.question[:200])
            ret_stage.set("document_a_id", request.document_a_id)
            ret_stage.set("document_b_id", request.document_b_id)

            # We'll use the retriever directly to capture metrics
            delta_doc_id = f"{request.document_a_id}_vs_{request.document_b_id}"
            scope = [request.document_a_id, request.document_b_id, delta_doc_id]
            chunks = retriever.retrieve(query=request.question, document_scope=scope, top_k=6)
            ret_stage.set("chunks_retrieved", len(chunks))

        metrics.record_latency("retrieval", ret_stage.duration_ms)
        metrics.increment("chunks_retrieved", len(chunks))

        # LLM stage
        with trace.stage("llm") as llm_stage:
            answer: ChatAnswer = await generate_grounded_answer(
                question=request.question,
                llm_client=llm_client,
                retriever=retriever,
                document_a_id=request.document_a_id,
                document_b_id=request.document_b_id,
            )
            llm_stage.set("input_tokens", answer.input_tokens)
            llm_stage.set("output_tokens", answer.output_tokens)
            llm_stage.set("model", answer.model)
            llm_stage.set("citations_count", len(answer.chunk_ids))

            # Estimate cost
            from src.observability.llm_telemetry import estimate_cost
            cost = estimate_cost(answer.input_tokens, answer.output_tokens)
            llm_stage.set("estimated_cost", cost)

        metrics.record_latency("llm", llm_stage.duration_ms)
        metrics.increment("llm_input_tokens", answer.input_tokens)
        metrics.increment("llm_output_tokens", answer.output_tokens)
        metrics.increment("citation_count", len(answer.chunk_ids))

        log_event(logger, logging.INFO, "chat_complete",
                  input_tokens=answer.input_tokens,
                  output_tokens=answer.output_tokens,
                  model=answer.model, duration_ms=llm_stage.duration_ms)

        response_body = answer.model_dump()
        response_body["request_id"] = trace.request_id

        trace.finish("success")

        return JSONResponse(
            content=response_body,
            headers={"X-Request-Id": trace.request_id},
        )

    except LLMRequestError as e:
        log_event(logger, logging.ERROR, "llm_request_failed",
                  error_type="LLMRequestError", error_detail=str(e),
                  status_code=e.status_code)
        trace.finish("error")
        raise HTTPException(status_code=502, detail=f"LLM service error: {e}")
    except HTTPException:
        trace.finish("error")
        raise
    except Exception as e:
        log_event(logger, logging.ERROR, "chat_failed",
                  error_type=type(e).__name__, error_detail=str(e))
        trace.finish("error")
        raise HTTPException(status_code=500, detail=f"Chat error: {type(e).__name__}")


@router.post("/api/compare/{document_a_id}/{document_b_id}/explain")
async def explain_delta(document_a_id: str, document_b_id: str):
    """Generate a human-friendly narrative summary of all delta changes."""
    from src.db.mongo import get_db

    db = get_db()
    collection = db["delta_reports"]

    report = collection.find_one(
        {"document_a.document_id": document_a_id, "document_b.document_id": document_b_id}
    )

    if not report:
        raise HTTPException(
            status_code=404,
            detail=f"No delta report found for {document_a_id} vs {document_b_id}. "
                   f"Run POST /api/compare first.",
        )

    report.pop("_id", None)

    try:
        llm_client = get_llm_client()
    except ValueError as e:
        raise HTTPException(status_code=503, detail=f"LLM client not configured: {e}")

    try:
        llm_summary = await generate_delta_explanation(llm_client, report)
    except LLMRequestError as e:
        log_event(logger, logging.ERROR, "llm_explain_failed",
                  error_type="LLMRequestError", error_detail=str(e))
        raise HTTPException(status_code=502, detail=f"LLM service error: {e}")

    collection.update_one(
        {"document_a.document_id": document_a_id, "document_b.document_id": document_b_id},
        {"$set": {"llm_summary": llm_summary}},
    )

    return {
        "document_a_id": document_a_id,
        "document_b_id": document_b_id,
        "llm_summary": llm_summary,
    }
