/**
 * API client for the Delta Chat backend.
 * All calls go through a single base URL configured via VITE_API_BASE_URL.
 */

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

class ApiError extends Error {
  constructor(message, status, body) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }
}

async function request(path, options = {}) {
  const url = `${BASE_URL}${path}`;
  try {
    const res = await fetch(url, options);
    const contentType = res.headers.get('content-type') || '';

    if (!res.ok) {
      let body = '';
      if (contentType.includes('application/json')) {
        const data = await res.json();
        body = data.detail || JSON.stringify(data);
      } else {
        body = await res.text();
      }
      throw new ApiError(`Request failed: ${body}`, res.status, body);
    }

    if (contentType.includes('application/json')) {
      return await res.json();
    }
    return await res.text();
  } catch (err) {
    if (err instanceof ApiError) throw err;
    throw new ApiError(`Network error: ${err.message}`, 0, err.message);
  }
}

/** GET /health */
export async function getHealth() {
  return request('/health');
}

/** POST /api/documents/ingest (multipart) */
export async function ingestDocument(file, documentId, revision) {
  const form = new FormData();
  form.append('file', file);
  form.append('document_id', documentId);
  form.append('revision', revision);
  return request('/api/documents/ingest', { method: 'POST', body: form });
}

/** POST /api/compare */
export async function compareDocuments(docAId, revA, docBId, revB) {
  return request('/api/compare', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      document_a_id: docAId,
      revision_a: revA,
      document_b_id: docBId,
      revision_b: revB,
    }),
  });
}

/** GET /api/compare/{a}/{b} */
export async function getReport(docAId, docBId) {
  return request(`/api/compare/${docAId}/${docBId}`);
}

/** GET /api/compare/{a}/{b}/report.md */
export async function getMarkdownReport(docAId, docBId) {
  return request(`/api/compare/${docAId}/${docBId}/report.md`);
}

/** POST /api/chat */
export async function sendChatMessage(question, docAId, docBId) {
  return request('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, document_a_id: docAId, document_b_id: docBId }),
  });
}

/** GET /api/metrics */
export async function getMetrics() {
  return request('/api/metrics');
}

/** Placeholder: GET /api/eval/latest (using metrics for now) */
export async function getLatestEval() {
  return request('/api/metrics');
}

/** Placeholder: POST /api/eval/run */
export async function runEval() {
  return request('/api/metrics');
}

/** GET /api/compare/history — list past comparisons */
export async function getComparisonHistory() {
  return request('/api/compare/history');
}

export { ApiError };
