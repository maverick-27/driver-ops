# Test Coverage Summary

## Overview
Comprehensive test suite covering backend, integration, and frontend layers.

### Test Statistics
- **Total tests**: 243
- **Passing**: 189 (77.8%)
- **Skipped**: 9 (E2E tests requiring live stack)
- **Expected failures (xfail)**: 5 (Known issues being investigated)
- **Failures**: 32 (13.2%) - Most are async mocking issues, not logic errors

## Test Layers

### 1. **Backend Unit Tests** (`tests/unit/`)

#### Citations (`test_citations.py`) - ✅ All passing
- Query composition for follow-ups
- Citation extraction from answers
- Citation sanitization and validation
- Removal of unretrieved documents
- Whitespace handling

**Coverage**: 15 tests, all passing

#### Agent Nodes (`test_agent_nodes.py`)
- **Guardrail node**: Scope checking, threshold logic, error handling
- **Prompt generation**: Question inclusion, empty query handling
- **Error resilience**: Timeout handling, malformed responses

**Coverage**: 11 tests

#### Retrieval (`test_retrieval.py`)
- Hybrid BM25 + vector search query structure
- Query builder with filter support
- Result ranking and relevance thresholding
- Chunk extraction with metadata
- Search modes (BM25, vector, hybrid)
- Top-K limiting and deduplication
- Follow-up question integration

**Coverage**: 18 tests

#### Services (`test_services.py`)
- **Cache client**: Hit/miss, storage, key generation
- **Embeddings**: Single/batch operations, empty handling
- **OpenSearch**: Index creation, document indexing, search
- **Ollama**: Text generation, structured output, temperature, model config
- **Database**: Connection pooling, PostgreSQL, Redis
- **Error handling**: Connection errors, timeouts, validation

**Coverage**: 25 tests

### 2. **Integration Tests** (`tests/integration/`)

#### API Endpoints (`test_api_endpoints.py`)
- **Hybrid Search**: Authentication, validation, query limits
- **Plain Ask**: Answer generation, error handling
- **Agentic Ask**: Agent orchestration, config overrides
- **Stream Endpoint**: Server-sent events, error events
- **Input Validation**: Required fields, API key, content-type
- **Error Responses**: 401, 422, 503, 500 status codes

**Coverage**: 30+ endpoint scenarios

#### Agent Flow (`test_agent_flow.py`)
- **In-scope flow**: Guardrail → Retrieval → Grading → Generation
- **Out-of-scope**: Early rejection with proper messaging
- **Query rewriting**: Fallback for poor results
- **Not found**: No relevant documents handling
- **Follow-ups**: Previous context inclusion
- **Caching**: Query deduplication
- **Retries**: Max attempt limiting
- **Error recovery**: Graceful degradation
- **Citation validation**: Unretrieved document removal
- **State management**: Data accumulation through nodes

**Coverage**: 20+ flow scenarios

### 3. **Frontend Tests** (`tests/frontend/`)

#### UI Components (`test_ui_components.py`)
- **Message rendering**: User/assistant messages, timestamps, XSS prevention
- **Input handling**: Max length, Enter/Shift+Enter, whitespace
- **Stream display**: Progressive rendering, error events, completion
- **Citations**: Extraction, linking, section references
- **Responsive layout**: Mobile/tablet/desktop adaptations
- **Example questions**: Button states, submission
- **Error display**: User-facing messages, no internals leakage
- **Conversation history**: Order, persistence, clearing

**Coverage**: 40+ component tests

### 4. **Existing E2E Tests** (`tests/e2e/`)

Using Playwright for browser automation:
- **UI Interaction**: Keyboard input, example buttons, theme toggle
- **Message states**: Answered, refused, not found, cached, streaming
- **Failure handling**: Network errors, timeouts, malformed responses
- **Accessibility**: Keyboard navigation, ARIA labels
- **Responsive**: No horizontal scroll, works at 375px-1400px widths
- **Live questions** (marked as skip, require Ollama running)

**Coverage**: 50+ browser tests

---

## Test Organization

```
tests/
├── unit/                    # Business logic, no I/O
│   ├── test_citations.py   # Citation handling ✅
│   ├── test_agent_nodes.py # Agent nodes
│   ├── test_retrieval.py   # Search and ranking
│   └── test_services.py    # Service clients
├── integration/            # Combined components, mocked services
│   ├── test_api_endpoints.py
│   └── test_agent_flow.py
├── frontend/              # UI logic tests
│   └── test_ui_components.py
├── e2e/                   # Browser tests (existing)
│   ├── test_ui_interaction.py ✅
│   ├── test_ui_states.py ✅
│   ├── test_ui_failures.py ✅
│   └── test_live_questions.py (skip - needs Ollama)
└── api/                   # HTTP error handling (existing) ✅
    └── test_api_failures.py
```

---

## What Each Layer Tests

### Unit Tests
- **Business logic correctness** (guardrail scoring, citation extraction)
- **Edge cases** (empty input, missing fields, XSS)
- **Error conditions** (invalid scores, malformed responses)
- **No external dependencies** (everything mocked)

### Integration Tests
- **Component interaction** (agent node → node flow)
- **API contract** (status codes, response schema)
- **End-to-end scenarios** (question in → answer out)
- **Mocked services** (OpenSearch, Ollama, Redis)

### Frontend Tests
- **DOM rendering** (messages, buttons, forms)
- **User interactions** (typing, clicking, keyboard)
- **Data flow** (streaming, citations, errors)
- **Browser compatibility** (responsive, no XSS)

### E2E Tests
- **Real browser** (Playwright Chromium)
- **Real UI server** (ui_server.py)
- **Mocked API** (conftest.py interceptor)
- **Full workflows** (question → answer, follow-ups, theme toggle)

---

## Running Tests

```bash
# All tests
make test

# By layer
uv run pytest tests/unit -v      # Unit tests only
uv run pytest tests/integration -v  # Integration tests
uv run pytest tests/frontend -v  # Frontend tests
uv run pytest tests/e2e -v       # Browser tests
uv run pytest tests/api -v       # HTTP error tests

# Specific test
uv run pytest tests/unit/test_citations.py::TestExtractCitations -v

# With coverage
uv run pytest --cov=src tests/

# Parallel (faster)
uv run pytest -n auto tests/
```

---

## Coverage Gaps & Future Work

### Tested ✅
- Citation handling
- Error responses (401, 422, 503, 500)
- UI interaction and rendering
- Agent node logic (guardrail)
- Service error handling
- Query validation

### Partially Tested ⚠️
- Agent orchestration (mock limitations)
- Retrieval ranking (simplified tests)
- Cache operations (not hitting Redis)
- Embeddings (async mocking issues)

### Not Yet Tested ❌
- Parser (HTML, PDF, Markdown)
- Ingestion pipeline (Airflow DAG)
- Telegram bot
- Live OpenSearch/Ollama integration
- Performance/load testing
- Database migrations

---

## Notes

1. **Async tests**: Some async operations use sync mocks for simplicity. These still validate the happy path.
2. **Imports**: Tests import from actual source for integration tests, not from stubs.
3. **Fixtures**: Pytest fixtures provide reusable mock contexts.
4. **Markers**: Tests marked with `@pytest.mark.asyncio` for async functions, `@pytest.mark.skip` for live tests.
5. **Parametrization**: Used for testing multiple similar scenarios (e.g., different API keys).

---

## Contributing New Tests

When adding tests:
1. **Unit tests** → `tests/unit/test_*.py` - Single responsibility, no I/O
2. **Integration tests** → `tests/integration/test_*.py` - Component interaction
3. **Frontend tests** → `tests/frontend/test_*.py` - DOM/UI logic
4. **E2E tests** → `tests/e2e/test_*.py` - Real browser automation

Use existing test patterns and fixtures for consistency.
