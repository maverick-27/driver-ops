"""What the driver sees when something breaks. Tests marked xfail document real bugs; see FINDINGS.md."""

import re

import pytest
from playwright.sync_api import expect

from .conftest import UNAVAILABLE, answered_stream, final, guardrail, sse, unavailable_stream


def assert_error_card(chat, message: str):
    card = chat.last_answer
    expect(card).to_have_class(re.compile("error"))
    expect(card.locator(".banner")).to_have_text("No answer")
    expect(card.locator(".a-body")).to_contain_text(message)


def test_http_500_from_proxy(chat):
    chat.ask("fuel card?", "boom", status=500)
    assert_error_card(chat, "The service returned an error")
    expect(chat.page.locator("#question")).to_have_value("fuel card?")


def test_stream_ends_without_final(chat):
    chat.ask("fuel card?", sse(guardrail()))
    assert_error_card(chat, "The answer stream ended early")
    expect(chat.page.locator("#question")).to_have_value("fuel card?")


def test_empty_stream(chat):
    chat.ask("fuel card?", "")
    assert_error_card(chat, "The answer stream ended early")


def test_error_event_from_api(chat):
    chat.ask("fuel card?", sse({"type": "error", "message": "The Driver Ops API did not answer"}))
    assert_error_card(chat, "The Driver Ops API did not answer")
    expect(chat.page.locator("#trace")).to_contain_text("Run failed")


def test_error_event_rechecks_status(chat):
    chat.status_payload = None  # /status aborts: the System panel must say so after the failed run
    chat.ask("fuel card?", sse({"type": "error", "message": "Search is temporarily unavailable"}))
    assert_error_card(chat, "Search is temporarily unavailable")
    expect(chat.page.locator("#health")).to_contain_text("not reachable")


def test_error_after_partial_tokens(chat):
    body = sse(guardrail(), {"type": "token", "text": "Partial [C05]"}, {"type": "error", "message": "The run failed"})
    chat.ask("fuel card?", body)
    assert_error_card(chat, "The run failed")
    expect(chat.last_answer).not_to_contain_text("Partial")


def test_unavailable_answer_shows_message_and_scope_check_note(chat):
    chat.ask("fuel card?", unavailable_stream())
    card = chat.last_answer
    expect(card.locator(".a-body")).to_contain_text(UNAVAILABLE)
    expect(card.locator(".a-body")).to_contain_text("905-555-0100")
    chat.page.locator("button[data-trace]").click()
    expect(chat.page.locator("#trace")).to_contain_text("The scope check could not run")


@pytest.mark.xfail(strict=True, reason="BUG: unavailable answers get no banner, so they look like a normal answer")
def test_unavailable_answer_has_a_banner(chat):
    chat.ask("fuel card?", unavailable_stream())
    expect(chat.last_answer.locator(".banner")).to_be_visible()


@pytest.mark.xfail(strict=True, reason="BUG: an unavailable answer is stored as previous_question, polluting the next follow-up")
def test_unavailable_answer_is_not_follow_up_context(chat):
    chat.ask("first question", unavailable_stream())
    expect(chat.last_answer.locator(".a-body")).to_be_visible()
    chat.ask("second question", answered_stream())
    expect(chat.page.locator("article.msg.a")).to_have_count(2)
    assert chat.requests[1]["previous_question"] is None


def test_partial_tokens_then_unavailable_replaces_raw_text(chat):
    body = sse(guardrail(), {"type": "token", "text": "Partial text [C05]"}, final(answer=UNAVAILABLE, search_mode="none"))
    chat.ask("fuel card?", body)
    expect(chat.last_answer.locator(".a-body")).to_contain_text(UNAVAILABLE)
    expect(chat.last_answer).not_to_contain_text("Partial text")


@pytest.mark.xfail(strict=True, reason="BUG: a malformed data: line shows the raw JSON SyntaxError to the driver")
def test_malformed_json_line_gives_friendly_error(chat):
    chat.ask("fuel card?", "data: {not json}\n\n")
    card = chat.last_answer
    expect(card.locator(".banner")).to_have_text("No answer")
    expect(card.locator(".a-body")).not_to_contain_text("JSON")
    expect(card.locator(".a-body")).not_to_contain_text("Unexpected token")


@pytest.mark.xfail(strict=True, reason="BUG: events separated by CRLF CRLF are never split, so the stream appears to end early")
def test_crlf_event_separator(chat):
    chat.ask("fuel card?", answered_stream().replace("\n\n", "\r\n\r\n"))
    expect(chat.last_answer.locator(".meta")).to_be_visible()


def test_comment_and_unknown_lines_are_ignored(chat):
    body = ": keep-alive\n\n" + answered_stream() + "event: ping\n\n"
    chat.ask("fuel card?", body)
    expect(chat.last_answer.locator(".meta")).to_be_visible()


def test_unknown_step_node_does_not_break_the_run(chat):
    odd = {"type": "step", "node": "mystery", "next": None, "data": {}}
    chat.ask("fuel card?", sse(guardrail(), odd, final(answer="Fine [C05].", sources=[])))
    expect(chat.last_answer.locator(".a-body")).to_contain_text("Fine")


def test_html_in_answer_is_escaped(chat):
    chat.ask("fuel card?", sse(final(answer="<img src=x onerror=window.__pwned=1> hi")))
    expect(chat.last_answer.locator(".a-body")).to_contain_text("<img src=x")
    assert chat.page.evaluate("window.__pwned") is None


def test_status_unreachable_marks_system_panel(chat):
    chat.status_payload = None
    chat.page.reload()
    expect(chat.page.locator("#health")).to_contain_text("not reachable")


@pytest.mark.parametrize(
    ("services", "expected"),
    [
        ({"database": "healthy", "search": "unhealthy", "llm": "healthy", "cache": "healthy", "tracing": "disabled"}, "down"),
        ({"database": "healthy", "search": "healthy", "llm": "unhealthy", "cache": "healthy", "tracing": "disabled"}, "down"),
        ({"database": "healthy", "search": "healthy", "llm": "healthy", "cache": "unhealthy", "tracing": "disabled"}, "down"),
    ],
)
def test_degraded_service_shows_down(chat, services, expected):
    chat.status_payload = {"ok": False, "model": "gemma3:4b", "services": services}
    chat.page.reload()
    expect(chat.page.locator("#health .dot.bad")).to_have_count(1)
    expect(chat.page.locator("#health")).to_contain_text(expected)


@pytest.mark.xfail(
    strict=True, reason="BUG: Stop does nothing when the box is empty (textarea is required, form lacks novalidate)"
)
def test_stop_button_aborts_the_run(chat):
    chat.hang_stream()
    chat.page.fill("#question", "slow question")
    chat.page.press("#question", "Enter")
    expect(chat.page.locator("#send")).to_have_attribute("aria-label", "Stop this question")
    expect(chat.last_answer.locator(".a-live")).to_contain_text("Checking the question is in scope")
    chat.page.click("#send")
    expect(chat.last_answer.locator(".banner")).to_have_text("Stopped")
    expect(chat.page.locator("#send")).to_have_attribute("aria-label", "Ask")
    expect(chat.page.locator("#trace")).to_contain_text("Stopped before the answer was finished")


def test_stop_button_works_when_a_draft_is_in_the_box(chat):
    chat.hang_stream()
    chat.page.fill("#question", "slow question")
    chat.page.press("#question", "Enter")
    expect(chat.page.locator("#send")).to_have_attribute("aria-label", "Stop this question")
    chat.page.fill("#question", "next question")
    chat.page.click("#send")
    expect(chat.last_answer.locator(".banner")).to_have_text("Stopped")


def test_new_button_during_run_aborts_it(chat):
    chat.hang_stream()
    chat.page.fill("#question", "slow question")
    chat.page.press("#question", "Enter")
    expect(chat.page.locator("#send")).to_have_attribute("aria-label", "Stop this question")
    chat.page.click("#new")
    expect(chat.page.locator("#send")).to_have_attribute("aria-label", "Ask")
    expect(chat.page.locator(".hero")).to_be_visible()


def test_enter_and_example_clicks_are_ignored_while_running(chat):
    chat.hang_stream()
    chat.page.fill("#question", "slow question")
    chat.page.press("#question", "Enter")
    expect(chat.page.locator("#send")).to_have_attribute("aria-label", "Stop this question")
    chat.page.fill("#question", "second")
    chat.page.press("#question", "Enter")
    expect(chat.page.locator("article.msg.a")).to_have_count(1)
    expect(chat.page.locator("#question")).to_have_value("second")
