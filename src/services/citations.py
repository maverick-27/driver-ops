"""Citation handling shared by /ask and the agent.

Documents are cited by their id in square brackets: [C05], [R01]. An id the model cites that was
not in the retrieved set is removed from the answer before it is returned.
"""

import re

# [C05], [R01, C03], [C01 §5], [C04, section 6]
_BRACKET = re.compile(r"\[([^\[\]]{1,80})\]")
_DOC_ID = re.compile(r"\b([RC]\d{2})\b")


def compose_retrieval_query(question: str, previous_question: str | None) -> str:
    """A follow-up ("does that change in the US") is searched together with the question before it."""
    return f"{previous_question.strip()} {question.strip()}" if previous_question else question.strip()


def extract_citations(answer: str) -> list[str]:
    """Document ids cited in square brackets, in order of first appearance."""
    seen: list[str] = []
    for bracket in _BRACKET.findall(answer):
        for doc_id in _DOC_ID.findall(bracket):
            if doc_id not in seen:
                seen.append(doc_id)
    return seen


def sanitize_citations(answer: str, retrieved_ids: set[str]) -> tuple[str, list[str], list[str]]:
    """Return (answer without citations of unretrieved documents, valid cited ids, removed ids)."""
    removed: list[str] = []

    def fix(match: re.Match) -> str:
        inner = match.group(1)
        ids = _DOC_ID.findall(inner)
        if not ids:
            return match.group(0)
        bad = [i for i in ids if i not in retrieved_ids]
        if not bad:
            return match.group(0)
        removed.extend(i for i in bad if i not in removed)
        good = [i for i in ids if i in retrieved_ids]
        return f"[{', '.join(good)}]" if good else ""

    cleaned = _BRACKET.sub(fix, answer)
    cleaned = re.sub(r"[ \t]+([.,;:])", r"\1", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned).strip()
    return cleaned, extract_citations(cleaned), removed
