"""Input handling, controls and responsive layout (API stream mocked)."""

import re

import pytest
from playwright.sync_api import expect

from .conftest import answered_stream


def test_whitespace_only_is_ignored(chat):
    chat.stream_body = answered_stream()
    chat.page.fill("#question", "   \n  ")
    chat.page.press("#question", "Enter")
    chat.page.wait_for_timeout(200)
    assert chat.requests == []
    expect(chat.page.locator(".hero")).to_be_visible()


def test_enter_submits_and_shift_enter_adds_newline(chat):
    chat.stream_body = answered_stream()
    chat.page.fill("#question", "line one")
    chat.page.press("#question", "Shift+Enter")
    chat.page.keyboard.type("line two")
    assert chat.requests == []
    assert chat.page.input_value("#question") == "line one\nline two"
    chat.page.press("#question", "Enter")
    expect(chat.page.locator("article.msg.a")).to_have_count(1)
    assert chat.requests[0]["query"] == "line one\nline two"


def test_input_clears_after_submit(chat):
    chat.ask("fuel card?", answered_stream())
    expect(chat.page.locator("#question")).to_have_value("")


def test_textarea_limits_typing_to_1000(chat):
    assert chat.page.get_attribute("#question", "maxlength") == "1000"


def test_example_buttons_ask_their_own_text(chat):
    chat.stream_body = answered_stream()
    buttons = chat.page.locator(".examples button[data-q]")
    expect(buttons).to_have_count(4)
    texts = [buttons.nth(i).get_attribute("data-q") for i in range(4)]
    buttons.first.click()
    expect(chat.page.locator("article.msg.a")).to_have_count(1)
    assert chat.requests[0]["query"] == texts[0]
    expect(chat.page.locator(".msg.q")).to_have_text(texts[0])


def test_history_lists_questions_and_selects_card(chat):
    expect(chat.page.locator("#history-empty")).to_be_visible()
    chat.ask("first question", answered_stream())
    expect(chat.last_answer.locator(".meta")).to_be_visible()
    chat.ask("second question", answered_stream())
    expect(chat.page.locator("article.msg.a")).to_have_count(2)
    expect(chat.page.locator("#history-empty")).to_be_hidden()
    expect(chat.page.locator("#history button")).to_have_text(["first question", "second question"])
    chat.page.locator("#history button").first.click()
    expect(chat.page.locator("article.msg.a").first).to_have_class(re.compile("selected"))
    expect(chat.page.locator("#trace .trace-q")).to_have_text("first question")


def test_copy_button_copies_answer(chat):
    chat.ask("fuel card?", answered_stream("Fuel only [C05]"))
    chat.last_answer.locator("[data-copy]").click()
    expect(chat.last_answer.locator("[data-copy]")).to_contain_text("Copied")
    assert chat.page.evaluate("navigator.clipboard.readText()") == "Fuel only [C05]"


def test_theme_toggle_persists(chat):
    before = chat.page.evaluate("document.documentElement.dataset.theme || ''")
    chat.page.click("#theme")
    after = chat.page.evaluate("document.documentElement.dataset.theme || ''")
    assert before != after
    assert chat.page.evaluate("localStorage.getItem('driverops-theme')") == after
    chat.page.reload()
    assert chat.page.evaluate("document.documentElement.dataset.theme || ''") == after


def test_system_panel_lists_services(chat):
    health = chat.page.locator("#health")
    for label in ("Database", "Search index", "Model", "Answer cache", "Tracing"):
        expect(health).to_contain_text(label)
    expect(health).to_contain_text("gemma3:4b")
    expect(chat.page.locator("#health .dot.bad")).to_have_count(0)


def test_chips_are_keyboard_reachable(chat):
    chat.ask("fuel card?", answered_stream())
    chip = chat.last_answer.locator("button.chip[data-doc='C05']").first
    chip.focus()
    chat.page.keyboard.press("Enter")
    expect(chat.page.locator("#app")).to_have_class(re.compile("trace-open"))


def test_question_and_input_have_accessible_names(chat):
    expect(chat.page.get_by_label("Your question")).to_be_visible()
    expect(chat.page.locator("#log")).to_have_attribute("aria-live", "polite")


@pytest.mark.parametrize("size", [(1440, 900), (900, 800), (390, 844)])
def test_no_horizontal_scroll_and_core_flow_at_every_width(chat, size):
    chat.page.set_viewport_size({"width": size[0], "height": size[1]})
    chat.page.reload()
    chat.ask("fuel card?", answered_stream())
    expect(chat.last_answer.locator(".meta")).to_be_visible()
    overflow = chat.page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
    assert overflow <= 0


def test_narrow_layout_trace_and_rail_buttons(chat):
    chat.page.set_viewport_size({"width": 390, "height": 844})
    chat.page.reload()
    chat.ask("fuel card?", answered_stream())
    expect(chat.last_answer.locator(".meta")).to_be_visible()
    expect(chat.page.locator("#open-trace")).to_be_visible()
    expect(chat.page.locator("#open-rail")).to_be_visible()
    chat.page.click("#open-trace")
    expect(chat.page.locator("#app")).to_have_class(re.compile("trace-open"))
    chat.page.keyboard.press("Escape")
    expect(chat.page.locator("#app")).not_to_have_class(re.compile("trace-open"))


def test_wide_layout_hides_panel_toggles(chat):
    chat.page.set_viewport_size({"width": 1440, "height": 900})
    chat.page.reload()
    expect(chat.page.locator("#open-trace")).to_be_hidden()
    expect(chat.page.locator("#open-rail")).to_be_hidden()
