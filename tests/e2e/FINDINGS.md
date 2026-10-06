# Findings from the Playwright suite

Tests marked `xfail(strict=True)` in `test_ui_failures.py` pin each bug below; when a bug is fixed the test starts passing and the strict xfail fails, so remove the marker then.

## UI bugs (confirmed by tests)
1. **Stop does nothing when the box is empty.** `#question` is `required` and `#form` has no `novalidate`, so clicking Stop (a submit button) is blocked by native validation before the abort handler runs. The box is always empty while a run is in progress, so Stop effectively never works unless the driver types something first. Fix: add `novalidate` to `#form` (the submit handler already ignores empty input).
2. **Unavailable answers look like normal answers.** When Ollama is down the API returns 200 with `refused=false`, `not_found=false` and the "part of the system is down" text, so the card has no banner. Fix: add a banner (for example "Service unavailable") when `guardrail_score` is null, or add an `unavailable` flag to the response.
3. **An unavailable answer becomes `previous_question`.** `if (!run.final.refused) previousQuestion = question` also fires for unavailable answers, so the next question is sent as a follow-up to a question that was never answered.
4. **A malformed `data:` line shows a raw `SyntaxError` to the driver** ("Expected property name or '}' in JSON..."). Fix: wrap `JSON.parse` and throw "The answer stream was garbled".
5. **CRLF event separators are never split**, so a proxy that rewrites `\n\n` to `\r\n\r\n` makes every answer end with "The answer stream ended early". Fix: normalise `\r\n` to `\n` in the buffer.

## API behavior worth deciding on
- `/api/v1/stream` (plain RAG) turns SearchError and LLMError into HTTP 200 with an in-stream `{"error": ...}`, while `/api/v1/ask` returns 503. Consistent with `/ask-agentic/stream`, but different from `/ask`.
- `HybridSearchRequest.from_` triggers a pydantic `alias` warning (`UnsupportedFieldAttributeWarning`): the `from` alias may not apply as intended.

## Known quality failures (live tests, from `evals/results/agentic.md`)
- **Q01 fuel card for food:** the grader sometimes rejects the right chunk (C05) twice and the driver gets "Not in the documents". Live test `test_fuel_card_question_is_answered_not_missed` is not xfail: a failure is a real regression signal.
- **Q10 US hours:** R04 and R05 returned HTTP 403 in `corpus/regulations/fetch_log.txt`, so they are not in the corpus. Fix the fetch (browser-like headers or manual download), then re-ingest.
- **Q17 fine for driving over hours:** the model invents a dollar figure instead of returning not_found.
- Q15: C03 is missed for border paperwork plus hours questions.

## Not run here
Live tests were skipped: the API was not running on :8000 and Ollama was not running. Run `make start`, start Ollama, `make ingest`, then `make test-live`.
