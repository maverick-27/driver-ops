from pathlib import Path
from typing import Any

_SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "rag_system.txt"

NO_RESULTS_ANSWER = (
    "I couldn't find that in my documents. For company questions call Dispatch at 905-555-0100 (24/7); "
    "for compliance questions contact Safety & Compliance at 905-555-0140."
)

_LABELS = {"company_policy": "COMPANY POLICY", "regulation": "REGULATION"}


def format_excerpts(chunks: list[dict[str, Any]]) -> str:
    """Render retrieved chunks with the header the model cites from: [C05] COMPANY POLICY / [R01] REGULATION (Ontario)."""
    blocks = []
    for chunk in chunks:
        label = _LABELS.get(chunk.get("doc_type", ""), "DOCUMENT")
        if chunk.get("doc_type") == "regulation" and chunk.get("jurisdiction"):
            label += f" ({chunk['jurisdiction']})"
        blocks.append(f"[{chunk['doc_id']}] {label}\n{chunk['chunk_text']}")
    return "\n\n---\n\n".join(blocks)


class RAGPromptBuilder:
    def __init__(self) -> None:
        self.system_prompt = _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()

    def build(self, query: str, chunks: list[dict[str, Any]], previous_question: str | None = None) -> str:
        # Excerpts first, rules and question last: a small model follows what it read most recently.
        parts = ["### Document excerpts:", format_excerpts(chunks), "### Instructions:\n" + self.system_prompt]
        if previous_question:
            parts.append(f"### The driver's previous question (context only):\n{previous_question}")
        parts.append(f"### Question:\n{query}")
        parts.append("### Answer (plain text, with [ID] citations):")
        return "\n\n".join(parts)
