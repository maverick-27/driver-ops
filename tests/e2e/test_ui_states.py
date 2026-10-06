"""How each kind of answer renders (API stream mocked)."""

import re

from playwright.sync_api import expect

from .conftest import (
    NOT_FOUND,
    OUT_OF_SCOPE,
    answered_stream,
    final,
    not_found_stream,
    refused_stream,
    source,
    sse,
)


def test_answered_shows_chips_sources_and_meta(chat):
    chat.ask("fuel card for food?", answered_stream())
    card = chat.last_answer
    expect(card.locator(".a-body")).to_contain_text("Use the fuel card for fuel only")
    expect(card.locator("button.chip[data-doc='C05']").first).to_be_visible()
    expect(card.locator(".sources")).to_contain_text("Fuel Card Policy")
    expect(card.locator(".sources")).to_contain_text("Company policy")
    expect(card.locator(".meta")).to_contain_text("hybrid search")
    expect(card).not_to_have_class("msg a notice")


def test_regulation_source_shows_jurisdiction(chat):
    body = sse(final(answer="See [R01].", sources=[source("R01", "NSC Standard", "regulation", "Canada")]))
    chat.ask("rule?", body)
    expect(chat.last_answer.locator(".sources")).to_contain_text("Regulation · Canada")
    expect(chat.last_answer.locator("button.chip.reg").first).to_be_visible()


def test_citation_chip_opens_trace_and_excerpt(chat):
    chat.ask("fuel card?", answered_stream())
    chat.last_answer.locator("button.chip[data-doc='C05']").first.click()
    expect(chat.page.locator("#app")).to_have_class(re.compile("trace-open"))
    expect(chat.page.locator("#trace details[data-doc='C05']").first).to_have_attribute("open", "")


def test_refused_shows_banner_and_meter(chat):
    chat.ask("what is the capital of France", refused_stream())
    card = chat.last_answer
    expect(card).to_have_class(re.compile("notice"))
    expect(card.locator(".banner")).to_have_text("Outside what I cover")
    expect(card.locator(".a-body")).to_contain_text(OUT_OF_SCOPE)
    chat.page.locator("button[data-trace]").click()
    expect(chat.page.locator(".meter[aria-label='Scope score 10 out of 100, pass mark 60']")).to_be_visible()
    expect(chat.page.locator("#trace")).to_contain_text("Refused")


def test_not_found_shows_banner_dispatch_number_and_trace(chat):
    chat.ask("fuel card for food", not_found_stream())
    card = chat.last_answer
    expect(card.locator(".banner")).to_have_text("Not in the documents")
    expect(card.locator(".a-body")).to_contain_text(NOT_FOUND)
    expect(card.locator(".a-body")).to_contain_text("905-555-0100")
    chat.page.locator("button[data-trace]").click()
    expect(chat.page.locator("#trace")).to_contain_text("Nothing relevant found")
    expect(chat.page.locator("#trace")).to_contain_text("After 2 searches")
    expect(chat.page.locator("#trace .verdict.no")).to_have_count(2)


def test_cached_answer_has_no_steps(chat):
    chat.ask("fuel card?", sse(final(answer="Cached [C05].", cached=True, sources=[source()], reasoning_steps=["Checked scope"])))
    expect(chat.last_answer.locator(".meta")).to_contain_text("from cache")
    chat.page.locator("button[data-trace]").click()
    expect(chat.page.locator("#trace")).to_contain_text("Served from cache")
    expect(chat.page.locator("#trace .cached-steps li")).to_have_text(["Checked scope"])


def test_bm25_fallback_is_labelled(chat):
    chat.ask("fuel card?", answered_stream(mode="bm25"))
    expect(chat.last_answer.locator(".meta")).to_contain_text("bm25 search")


def test_removed_citations_are_reported(chat):
    chat.ask("fuel card?", answered_stream(removed_citations=["R99"]))
    chat.page.locator("button[data-trace]").click()
    expect(chat.page.locator("#trace")).to_contain_text("Removed 1 citation(s)")


def test_streaming_tokens_then_formatted_answer(chat):
    # A route that holds the stream open is not needed: the final replaces the raw text in one pass.
    chat.ask("fuel card?", answered_stream("**Fuel only** [C05]"))
    expect(chat.last_answer.locator(".a-body")).not_to_have_class(re.compile("raw"))
    expect(chat.last_answer.locator(".a-body strong")).to_have_text("Fuel only")


def test_follow_up_sends_previous_question_but_refusal_does_not(chat):
    chat.ask("first question", answered_stream())
    expect(chat.last_answer.locator(".meta")).to_be_visible()
    chat.ask("second question", refused_stream())
    expect(chat.page.locator("article.msg.a.notice")).to_have_count(1)
    chat.ask("third question", answered_stream())
    expect(chat.page.locator("article.msg.a")).to_have_count(3)
    assert chat.requests[0]["previous_question"] is None
    assert chat.requests[1]["previous_question"] == "first question"
    # the refused turn must not become the context for the next one
    assert chat.requests[2]["previous_question"] == "first question"


def test_new_resets_conversation_and_previous_question(chat):
    chat.ask("first question", answered_stream())
    expect(chat.last_answer.locator(".meta")).to_be_visible()
    chat.page.click("#new")
    expect(chat.page.locator(".hero")).to_be_visible()
    chat.ask("fresh question", answered_stream())
    assert chat.requests[1]["previous_question"] is None
