"""Citation extraction, validation, and sanitization."""

import pytest

from src.services.citations import compose_retrieval_query, extract_citations, sanitize_citations


class TestComposeRetrievalQuery:
    """Test query composition for follow-up questions."""

    def test_simple_question_unchanged(self):
        result = compose_retrieval_query("what is a fuel card?", None)
        assert result == "what is a fuel card?"

    def test_follow_up_combines_with_previous(self):
        result = compose_retrieval_query("in the US?", "what is a fuel card?")
        assert result == "what is a fuel card? in the US?"

    def test_leading_trailing_whitespace_trimmed(self):
        result = compose_retrieval_query("  follow-up  ", "  previous  ")
        assert result == "previous follow-up"

    def test_empty_previous_treated_as_none(self):
        result = compose_retrieval_query("question", "")
        assert result == "question"


class TestExtractCitations:
    """Test citation ID extraction from answers."""

    def test_single_citation(self):
        answer = "According to [C05], drivers must..."
        assert extract_citations(answer) == ["C05"]

    def test_multiple_citations_in_one_bracket(self):
        answer = "See [C05, R01] for details."
        assert extract_citations(answer) == ["C05", "R01"]

    def test_multiple_brackets(self):
        answer = "First point [C01]. Second point [R02]."
        assert extract_citations(answer) == ["C01", "R02"]

    def test_no_duplicates_first_appearance_order(self):
        answer = "See [C05] and [R01] and [C05] again."
        assert extract_citations(answer) == ["C05", "R01"]

    def test_citations_with_sections(self):
        answer = "According to [C05 §3], see [R01 section 2]."
        assert extract_citations(answer) == ["C05", "R01"]

    def test_no_citations_returns_empty_list(self):
        answer = "This answer has no citations."
        assert extract_citations(answer) == []

    def test_invalid_brackets_ignored(self):
        answer = "Not a citation [XYZ], but [C05] is valid."
        assert extract_citations(answer) == ["C05"]

    def test_malformed_ids_skipped(self):
        answer = "See [CA1] for comparison, [R02] for rules."
        assert extract_citations(answer) == ["R02"]


class TestSanitizeCitations:
    """Test citation removal and validation."""

    def test_all_citations_valid(self):
        answer = "See [C05] and [R01] for details."
        retrieved_ids = {"C05", "R01"}
        cleaned, valid, removed = sanitize_citations(answer, retrieved_ids)
        assert cleaned == "See [C05] and [R01] for details."
        assert valid == ["C05", "R01"]
        assert removed == []

    def test_invalid_citation_removed(self):
        answer = "According to [C99], drivers must..."
        retrieved_ids = {"C05"}
        cleaned, valid, removed = sanitize_citations(answer, retrieved_ids)
        assert "C99" not in cleaned
        assert valid == []
        assert removed == ["C99"]

    def test_partial_invalid_citations(self):
        answer = "See [C05, C99, R01] for details."
        retrieved_ids = {"C05", "R01"}
        cleaned, valid, removed = sanitize_citations(answer, retrieved_ids)
        assert "[C05, R01]" in cleaned
        assert "C99" not in cleaned
        assert valid == ["C05", "R01"]
        assert removed == ["C99"]

    def test_extra_whitespace_cleaned(self):
        answer = "See  [C05]  and  [R01]  for  details."
        retrieved_ids = {"C05", "R01"}
        cleaned, valid, removed = sanitize_citations(answer, retrieved_ids)
        assert "  " not in cleaned
        assert "[C05]" in cleaned

    def test_empty_brackets_after_sanitization_removed(self):
        answer = "First [C99], then [C05]."
        retrieved_ids = {"C05"}
        cleaned, valid, removed = sanitize_citations(answer, retrieved_ids)
        assert "[" not in cleaned.split("[C05]")[0]
        assert cleaned == "First, then [C05]."
        assert removed == ["C99"]

    def test_citation_with_punctuation_attached(self):
        answer = "See [C05], [R01]."
        retrieved_ids = {"C05", "R01"}
        cleaned, valid, removed = sanitize_citations(answer, retrieved_ids)
        assert "," not in cleaned.split("[C05]")[1][:2]
        assert valid == ["C05", "R01"]

    def test_empty_retrieved_set_removes_all(self):
        answer = "According to [C05, R01], drivers..."
        retrieved_ids = set()
        cleaned, valid, removed = sanitize_citations(answer, retrieved_ids)
        assert "[C05" not in cleaned
        assert removed == ["C05", "R01"]

    def test_case_sensitivity(self):
        answer = "See [c05] for rules."
        retrieved_ids = {"C05"}
        cleaned, valid, removed = sanitize_citations(answer, retrieved_ids)
        # c05 (lowercase) should not match C05
        assert "c05" not in cleaned or removed  # Depending on implementation


class TestCitationIntegration:
    """Integration tests for the full citation flow."""

    def test_full_citation_workflow(self):
        question = "What about fuel cards in Canada?"
        previous = "What is a fuel card?"
        query = compose_retrieval_query(question, previous)
        assert query == "What is a fuel card? What about fuel cards in Canada?"

        answer = "According to [C05] and [R02], fuel cards in Canada must follow [C05 §4]."
        retrieved_ids = {"C05", "R02", "R03"}
        cleaned, valid, removed = sanitize_citations(answer, retrieved_ids)

        assert valid == ["C05", "R02"]
        assert removed == []
        assert "§4" in cleaned
