"""Real stack: API, Ollama and the index must be running (`make start`, `make ingest`). Run with `make test-live`.

Assertions are on structure (banner, citations, sources), not on exact model wording.
"""

import re

import httpx
import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.live

SLOW = 120_000


def _stack_ready() -> str | None:
    try:
        health = httpx.get("http://localhost:8000/api/v1/health", timeout=5).json()
        services = health["services"]
    except (httpx.HTTPError, ValueError, KeyError):
        return "API is not running on :8000"
    bad = [name for name in ("search", "llm") if services.get(name, {}).get("status") != "healthy"]
    return f"services not healthy: {bad}" if bad else None


@pytest.fixture(autouse=True)
def require_stack():
    reason = _stack_ready()
    if reason:
        pytest.skip(reason)


@pytest.fixture
def live(page: Page, ui_url: str):
    page.route("**/fonts.googleapis.com/**", lambda r: r.abort())
    page.route("**/fonts.gstatic.com/**", lambda r: r.abort())
    page.goto(ui_url)
    return page


def ask(page: Page, question: str):
    page.fill("#question", question)
    page.press("#question", "Enter")
    card = page.locator("article.msg.a").last
    expect(card.locator(".a-live")).to_have_count(0, timeout=SLOW)  # the run has finished
    return card


def cited_ids(card) -> set[str]:
    return set(card.locator(".a-body button.chip[data-doc]").evaluate_all("els => els.map(e => e.dataset.doc)"))


def source_ids(card) -> set[str]:
    return set(card.locator(".sources .chip").all_inner_texts())


def test_out_of_scope_is_refused_fast(live):  # Q19-style
    card = ask(live, "what is the capital of France")
    expect(card.locator(".banner")).to_have_text("Outside what I cover")
    expect(card.locator("a, .sources")).to_have_count(0)


def test_not_in_corpus_is_not_in_the_documents(live):  # Q18
    card = ask(live, "what is the wifi password at the Brampton yard")
    expect(card.locator(".banner")).to_have_text("Not in the documents")
    expect(card.locator(".a-body")).to_contain_text("905-555-0100")


def test_breakdown_answer_cites_company_policy(live):  # Q02
    card = ask(live, "truck broke down on the 401 at night, who do i call")
    expect(card.locator(".banner")).to_have_count(0)
    assert "C06" in cited_ids(card)
    expect(card.locator(".a-body")).to_contain_text("911")


def test_every_cited_document_is_listed_as_a_source(live):
    card = ask(live, "what do i check on a pre trip inspection")
    cited = cited_ids(card)
    assert cited, "answer cites nothing"
    assert cited <= source_ids(card), f"cited but not in sources: {cited - source_ids(card)}"


def test_fuel_card_question_is_answered_not_missed(live):  # Q01: known flaky grader, a failure here is a finding
    card = ask(live, "can i use the fuel card for food on a long trip")
    expect(card.locator(".banner")).to_have_count(0)
    assert "C05" in cited_ids(card)


def test_ask_twice_second_is_cached(live):
    question = "can i bring my dog in the truck"
    ask(live, question)
    live.click("#new")
    card = ask(live, question)
    expect(card.locator(".meta")).to_contain_text("from cache")


@pytest.mark.xfail(reason="R04/R05 (FMCSA hours) returned HTTP 403 when fetched, so US hours are not in the corpus (Q10)")
def test_us_hours_follow_up_cites_fmcsa(live):
    ask(live, "whats the max hours i can drive in a day in canada")
    card = ask(live, "does that change when i go into the US")
    assert cited_ids(card) & {"R04", "R05"}


@pytest.mark.xfail(reason="Q17: the model invents a dollar figure instead of saying it is not in the documents")
def test_unknown_fine_amount_is_not_invented(live):
    card = ask(live, "what is the fine for driving over hours")
    expect(card.locator(".a-body")).not_to_have_text(re.compile(r"\$\s?\d"))


def test_punjabi_or_typo_question_still_gets_an_answer_or_clean_notice(live):  # Q22-Q24
    card = ask(live, "cn i use fuell card 4 snacks")
    expect(card).not_to_have_class(re.compile(r"\berror\b"))
