"""Tests for the chat module — LLM abstraction, retrieval, and grounded answers.

Uses a mock LLM client (does not call real OpenRouter API).

Run: pytest backend/tests/test_chat.py -v
"""

import os
import uuid
from unittest.mock import patch, MagicMock

import pytest

os.environ["TESTING"] = "true"

from src.chat.llm import LLMClient, LLMResponse, LLMRequestError
from src.chat.retriever import Chunk, KeywordFuzzyRetriever, _extract_technical_terms
from src.chat.answer import (
    generate_grounded_answer,
    build_prompt,
    _parse_llm_response,
    _resolve_citations,
    _FALLBACK_ANSWER,
)


# ─── Mock LLM Client ─────────────────────────────────────────────────────────


class MockLLMClient(LLMClient):
    """Mock LLM that returns a configurable response for testing."""

    def __init__(self, response_text: str = "", fail: bool = False):
        self._response_text = response_text
        self._fail = fail
        self.call_count = 0

    async def generate(self, system_prompt: str, user_prompt: str, max_tokens: int = 800) -> LLMResponse:
        self.call_count += 1
        if self._fail:
            raise LLMRequestError("Mock LLM failure", status_code=500, body="error")
        return LLMResponse(
            text=self._response_text,
            input_tokens=100,
            output_tokens=50,
            model="mock-model",
        )


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def sample_chunks() -> list[dict]:
    """Simulate chunks as stored in MongoDB."""
    return [
        {
            "chunk_id": "chunk-001",
            "source": "PID_A",
            "document_id": "DOC-A",
            "page": 1,
            "text": "XV-100 Control Valve\nOperating Pressure: 150 PSI\nFlow Rate: 3.5 m/s",
            "bbox_union": [10, 10, 200, 100],
            "delta_change_id": None,
        },
        {
            "chunk_id": "chunk-002",
            "source": "PID_B",
            "document_id": "DOC-B",
            "page": 1,
            "text": "XV-100 Control Valve\nOperating Pressure: 200 PSI\nFlow Rate: 4.0 m/s",
            "bbox_union": [10, 10, 200, 100],
            "delta_change_id": None,
        },
        {
            "chunk_id": "chunk-003",
            "source": "DELTA_REPORT",
            "document_id": "DOC-A_vs_DOC-B",
            "page": 1,
            "text": "Change: modified\nType: technical_value\nPage: 1\nOld: Operating Pressure: 150 PSI\nNew: Operating Pressure: 200 PSI\nDescription: Content modified (similarity: 92%)",
            "bbox_union": [10, 40, 200, 55],
            "delta_change_id": "delta-001",
        },
        {
            "chunk_id": "chunk-004",
            "source": "DELTA_REPORT",
            "document_id": "DOC-A_vs_DOC-B",
            "page": 1,
            "text": "Change: modified\nType: technical_value\nPage: 1\nOld: Flow Rate: 3.5 m/s\nNew: Flow Rate: 4.0 m/s\nDescription: Content modified (similarity: 88%)",
            "bbox_union": [10, 60, 200, 75],
            "delta_change_id": "delta-002",
        },
        {
            "chunk_id": "chunk-005",
            "source": "PID_A",
            "document_id": "DOC-A",
            "page": 2,
            "text": "26-KA-902 3RD STAGE HP GAS EXPORT COMPRESSOR\nDuty: 500 kW\nSuction pressure: 45 barg",
            "bbox_union": [50, 50, 300, 150],
            "delta_change_id": None,
        },
    ]


@pytest.fixture
def mock_mongo_collection(sample_chunks):
    """Patch MongoDB to return sample chunks."""
    mock_db = MagicMock()
    mock_collection = MagicMock()
    mock_collection.find.return_value = sample_chunks
    mock_db.__getitem__ = lambda self, key: mock_collection
    with patch("src.chat.retriever.get_db", return_value=mock_db) as _:
        # We need to patch at the import location
        pass
    return sample_chunks


# ─── LLM Client Tests ────────────────────────────────────────────────────────


class TestLLMClient:
    """Tests for the LLM client abstraction."""

    @pytest.mark.asyncio
    async def test_mock_client_returns_response(self):
        client = MockLLMClient(response_text='{"answer": "test", "citations": []}')
        resp = await client.generate("sys", "user")
        assert resp.text == '{"answer": "test", "citations": []}'
        assert resp.model == "mock-model"

    @pytest.mark.asyncio
    async def test_mock_client_failure_raises_error(self):
        client = MockLLMClient(fail=True)
        with pytest.raises(LLMRequestError):
            await client.generate("sys", "user")


# ─── Retriever Tests ──────────────────────────────────────────────────────────


class TestRetriever:
    """Tests for the keyword+fuzzy retriever."""

    def test_extract_technical_terms(self):
        terms = _extract_technical_terms("Operating Pressure: 150 PSI at valve XV-100")
        assert "150" in terms
        assert "XV-100" in terms
        assert "pressure" in terms
        assert "valve" in terms

    def test_retriever_finds_relevant_chunk(self, sample_chunks):
        """When querying about pressure, retriever should return pressure-related chunks."""
        with patch("src.db.mongo.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_collection = MagicMock()
            mock_collection.find.return_value = sample_chunks
            mock_db.__getitem__ = lambda self, key: mock_collection
            mock_get_db.return_value = mock_db

            retriever = KeywordFuzzyRetriever()
            results = retriever.retrieve(
                query="What is the operating pressure?",
                document_scope=["DOC-A", "DOC-B", "DOC-A_vs_DOC-B"],
                top_k=3,
            )

            assert len(results) > 0
            # Top result should mention pressure
            assert "pressure" in results[0].text.lower() or "150" in results[0].text

    def test_retriever_respects_top_k(self, sample_chunks):
        with patch("src.db.mongo.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_collection = MagicMock()
            mock_collection.find.return_value = sample_chunks
            mock_db.__getitem__ = lambda self, key: mock_collection
            mock_get_db.return_value = mock_db

            retriever = KeywordFuzzyRetriever()
            results = retriever.retrieve(query="compressor", top_k=2)
            assert len(results) <= 2

    def test_retriever_returns_empty_when_no_chunks(self):
        with patch("src.db.mongo.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_collection = MagicMock()
            mock_collection.find.return_value = []
            mock_db.__getitem__ = lambda self, key: mock_collection
            mock_get_db.return_value = mock_db

            retriever = KeywordFuzzyRetriever()
            results = retriever.retrieve(query="anything")
            assert results == []


# ─── Response Parsing Tests ───────────────────────────────────────────────────


class TestResponseParsing:
    """Tests for LLM response parsing."""

    def test_parse_clean_json(self):
        text = '{"answer": "The pressure is 150 PSI.", "citations": ["chunk-001", "chunk-003"]}'
        answer, citations = _parse_llm_response(text)
        assert answer == "The pressure is 150 PSI."
        assert citations == ["chunk-001", "chunk-003"]

    def test_parse_json_in_code_fence(self):
        text = 'Here is my answer:\n```json\n{"answer": "Test answer", "citations": ["c1"]}\n```'
        answer, citations = _parse_llm_response(text)
        assert answer == "Test answer"
        assert citations == ["c1"]

    def test_parse_malformed_raises_valueerror(self):
        text = "This is just plain text with no JSON at all."
        with pytest.raises(ValueError):
            _parse_llm_response(text)

    def test_parse_fallback_answer(self):
        text = f'{{"answer": "{_FALLBACK_ANSWER}", "citations": []}}'
        answer, citations = _parse_llm_response(text)
        assert answer == _FALLBACK_ANSWER
        assert citations == []


# ─── Citation Resolution Tests ────────────────────────────────────────────────


class TestCitationResolution:
    """Tests for resolving chunk_ids to human-readable labels."""

    def test_resolve_pid_chunk(self):
        chunks = [
            Chunk(
                chunk_id="chunk-001", source="PID_A", document_id="DOC-A",
                page=1, text="XV-100 Control Valve Operating Pressure 150 PSI",
                bbox_union=[10, 10, 200, 100], score=90.0,
            )
        ]
        labels = _resolve_citations(["chunk-001"], chunks)
        assert len(labels) == 1
        assert "PID_A" in labels[0]
        assert "Page 1" in labels[0]

    def test_resolve_delta_chunk(self):
        chunks = [
            Chunk(
                chunk_id="chunk-003", source="DELTA_REPORT", document_id="DOC-A_vs_DOC-B",
                page=1, text="Change: modified", bbox_union=[10, 10, 100, 50],
                delta_change_id="delta-001", score=85.0,
            )
        ]
        labels = _resolve_citations(["chunk-003"], chunks)
        assert len(labels) == 1
        assert "DELTA_REPORT" in labels[0]
        assert "delta-001" in labels[0]

    def test_resolve_ignores_hallucinated_ids(self):
        chunks = [
            Chunk(
                chunk_id="real-001", source="PID_A", document_id="DOC-A",
                page=1, text="Real content", bbox_union=[0, 0, 100, 100], score=90.0,
            )
        ]
        labels = _resolve_citations(["fake-id-999", "real-001"], chunks)
        # Only the real one should resolve
        assert len(labels) == 1
        assert "PID_A" in labels[0]


# ─── Grounded Answer Tests ───────────────────────────────────────────────────


class TestGroundedAnswer:
    """Integration tests for the full grounded answer pipeline (with mock LLM)."""

    @pytest.mark.asyncio
    async def test_returns_answer_with_citations(self, sample_chunks):
        """When chunks match and LLM provides valid JSON, return grounded answer."""
        mock_response = '{"answer": "The operating pressure changed from 150 PSI to 200 PSI.", "citations": ["chunk-003"]}'
        client = MockLLMClient(response_text=mock_response)

        with patch("src.db.mongo.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_collection = MagicMock()
            mock_collection.find.return_value = sample_chunks
            mock_db.__getitem__ = lambda self, key: mock_collection
            mock_get_db.return_value = mock_db

            retriever = KeywordFuzzyRetriever()
            answer = await generate_grounded_answer(
                question="What changed with the operating pressure?",
                llm_client=client,
                retriever=retriever,
                document_a_id="DOC-A",
                document_b_id="DOC-B",
            )

        assert "150 PSI" in answer.answer or "200 PSI" in answer.answer
        assert len(answer.chunk_ids) > 0
        assert "chunk-003" in answer.chunk_ids
        assert answer.model == "mock-model"

    @pytest.mark.asyncio
    async def test_fallback_when_no_chunks(self):
        """When no chunks are found, return the fallback message."""
        client = MockLLMClient(response_text="should not be called")

        with patch("src.db.mongo.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_collection = MagicMock()
            mock_collection.find.return_value = []  # No chunks
            mock_db.__getitem__ = lambda self, key: mock_collection
            mock_get_db.return_value = mock_db

            retriever = KeywordFuzzyRetriever()
            answer = await generate_grounded_answer(
                question="What is the meaning of life?",
                llm_client=client,
                retriever=retriever,
                document_a_id="DOC-A",
                document_b_id="DOC-B",
            )

        assert answer.answer == _FALLBACK_ANSWER
        assert answer.chunk_ids == []
        assert answer.citations == []
        # LLM should not have been called
        assert client.call_count == 0

    @pytest.mark.asyncio
    async def test_citations_reference_real_chunk_ids(self, sample_chunks):
        """Citations in the answer must reference chunk_ids that exist in retrieved set."""
        # LLM returns both a real and a fake chunk_id
        mock_response = '{"answer": "Test answer", "citations": ["chunk-001", "FAKE-999"]}'
        client = MockLLMClient(response_text=mock_response)

        with patch("src.db.mongo.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_collection = MagicMock()
            mock_collection.find.return_value = sample_chunks
            mock_db.__getitem__ = lambda self, key: mock_collection
            mock_get_db.return_value = mock_db

            retriever = KeywordFuzzyRetriever()
            answer = await generate_grounded_answer(
                question="Tell me about XV-100",
                llm_client=client,
                retriever=retriever,
                document_a_id="DOC-A",
                document_b_id="DOC-B",
            )

        # Only the real chunk_id should be in verified citations
        assert "chunk-001" in answer.chunk_ids
        assert "FAKE-999" not in answer.chunk_ids
        # Citation labels should reference real chunks only
        assert len(answer.citations) == 1

    @pytest.mark.asyncio
    async def test_retry_on_parse_failure(self, sample_chunks):
        """If first parse fails, retry with strict prompt and succeed."""

        class RetryMockClient(LLMClient):
            def __init__(self):
                self.call_count = 0

            async def generate(self, system_prompt, user_prompt, max_tokens=800):
                self.call_count += 1
                if self.call_count == 1:
                    # First call: return unparseable text
                    return LLMResponse(text="Just plain text no JSON", input_tokens=50, output_tokens=20, model="mock")
                else:
                    # Retry: return valid JSON
                    return LLMResponse(
                        text='{"answer": "Retried successfully", "citations": ["chunk-001"]}',
                        input_tokens=60, output_tokens=25, model="mock",
                    )

        client = RetryMockClient()

        with patch("src.db.mongo.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_collection = MagicMock()
            mock_collection.find.return_value = sample_chunks
            mock_db.__getitem__ = lambda self, key: mock_collection
            mock_get_db.return_value = mock_db

            retriever = KeywordFuzzyRetriever()
            answer = await generate_grounded_answer(
                question="Test question",
                llm_client=client,
                retriever=retriever,
                document_a_id="DOC-A",
                document_b_id="DOC-B",
            )

        assert answer.answer == "Retried successfully"
        assert client.call_count == 2  # First failed, retry succeeded
