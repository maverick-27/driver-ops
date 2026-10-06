"""Acceptance test for Driver Ops (evals/questions.yaml, from evals/questions.md).

    uv run python evals/run_eval.py --mode bm25      # stage 3: keyword retrieval only
    uv run python evals/run_eval.py --mode hybrid    # stage 4: hybrid retrieval only
    uv run python evals/run_eval.py --mode ask       # stage 5: plain RAG answers
    uv run python evals/run_eval.py --mode agentic   # stage 7: the agent (what drivers get)

Writes evals/results/<mode>.md and .json. Exit code 1 when a release threshold is missed.
Automatic checks do not verify regulation numbers: read the answers in the report against the cited section.
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

import httpx
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import get_settings  # noqa: E402
from src.services.citations import compose_retrieval_query, extract_citations  # noqa: E402

EVAL_DIR = Path(__file__).resolve().parent
TOP_K = 5


def matches(pattern: str, text: str) -> bool:
    return re.search(pattern, text, re.IGNORECASE) is not None


def score_retrieval(q: dict, retrieved: list[str]) -> dict:
    expected, also = q.get("expected", []), q.get("also_accepted", [])
    groups = q.get("expected_all_of")
    out = {"retrieved": retrieved}
    if q["behaviour"] != "answerable":
        return out
    out["hit"] = any(d in retrieved for d in expected)
    out["hit_lenient"] = any(d in retrieved for d in expected + also)
    if groups:
        out["hit_all_groups"] = all(any(d in retrieved for d in group) for group in groups)
    return out


def score_answer(q: dict, response: dict) -> dict:
    answer = response.get("answer", "")
    retrieved = response.get("retrieved_doc_ids", [])
    cited = extract_citations(answer)
    out = score_retrieval(q, retrieved)
    out.update(answer=answer, cited=cited, refused=response.get("refused", False), not_found=response.get("not_found", False))
    out["removed_citations"] = response.get("removed_citations", [])

    if q["behaviour"] == "answerable":
        expected, also = q.get("expected", []), q.get("also_accepted", [])
        only_retrieved = all(c in retrieved for c in cited)
        out["citation_correct"] = only_retrieved and any(c in expected for c in cited)
        out["citation_correct_lenient"] = only_retrieved and any(c in expected + also for c in cited)
        out["behaviour_ok"] = not out["refused"] and not out["not_found"]
        if q.get("key_facts"):
            out["missing_facts"] = [f for f in q["key_facts"] if not matches(f, answer)]
    elif q["behaviour"] == "not_in_corpus":
        out["invented"] = [p for p in q.get("must_not", []) if matches(p, answer)]
        out["points_to_ok"] = matches(q["points_to"], answer) if q.get("points_to") else None
        out["behaviour_ok"] = not out["invented"]
    else:  # out_of_scope
        out["behaviour_ok"] = bool(out["refused"])
    return out


def run(mode: str, base_url: str, only: list[str] | None, model: str | None = None) -> dict:
    settings = get_settings()
    spec = yaml.safe_load((EVAL_DIR / "questions.yaml").read_text(encoding="utf-8"))
    headers = {"X-API-Key": settings.api_key} if settings.api_key else {}
    results = []
    with httpx.Client(base_url=base_url, headers=headers, timeout=600) as client:
        for q in spec["questions"]:
            if only and q["id"] not in only:
                continue
            started = time.time()
            if mode in ("bm25", "hybrid"):
                query = compose_retrieval_query(q["question"], q.get("previous"))
                r = client.post("/api/v1/hybrid-search/", json={"query": query, "size": TOP_K, "use_hybrid": mode == "hybrid"})
                r.raise_for_status()
                data = r.json()
                row = score_retrieval(q, [h["doc_id"] for h in data["hits"]])
                row["search_mode"] = data["search_mode"]
            else:
                path = "/api/v1/ask" if mode == "ask" else "/api/v1/ask-agentic"
                body = {"query": q["question"], "top_k": TOP_K, "previous_question": q.get("previous"), "model": model}
                r = client.post(path, json=body)
                r.raise_for_status()
                data = r.json()
                row = score_answer(q, data)
                row["search_mode"] = data.get("search_mode")
                for key in ("retrieval_attempts", "rewritten_query", "guardrail_score", "reasoning_steps"):
                    if key in data:
                        row[key] = data[key]
            row.update(id=q["id"], behaviour=q["behaviour"], question=q["question"], seconds=round(time.time() - started, 1))
            results.append(row)
            print(f"{q['id']} {row.get('seconds')}s retrieved={row.get('retrieved')} hit={row.get('hit')}", flush=True)

    answerable = [r for r in results if r["behaviour"] == "answerable"]
    summary: dict = {"mode": mode, "questions": len(results), "answerable": len(answerable)}
    if answerable:
        summary["retrieval_hits"] = sum(bool(r.get("hit")) for r in answerable)
        summary["retrieval_hit_rate"] = round(summary["retrieval_hits"] / len(answerable), 3)
        summary["retrieval_hit_rate_lenient"] = round(sum(bool(r.get("hit_lenient")) for r in answerable) / len(answerable), 3)
        summary["retrieval_misses"] = [r["id"] for r in answerable if not r.get("hit")]
    if mode in ("ask", "agentic"):
        if answerable:
            summary["citation_correct"] = sum(bool(r.get("citation_correct")) for r in answerable)
            summary["citation_correct_rate"] = round(summary["citation_correct"] / len(answerable), 3)
            summary["citation_correct_rate_lenient"] = round(
                sum(bool(r.get("citation_correct_lenient")) for r in answerable) / len(answerable), 3
            )
            summary["citation_failures"] = [r["id"] for r in answerable if not r.get("citation_correct")]
            summary["answerable_not_answered"] = [r["id"] for r in answerable if not r.get("behaviour_ok")]
            summary["missing_key_facts"] = {r["id"]: r["missing_facts"] for r in answerable if r.get("missing_facts")}
        nic = [r for r in results if r["behaviour"] == "not_in_corpus"]
        oos = [r for r in results if r["behaviour"] == "out_of_scope"]
        summary["not_in_corpus_handled"] = f"{sum(r['behaviour_ok'] for r in nic)}/{len(nic)}"
        summary["not_in_corpus_invented"] = [r["id"] for r in nic if not r["behaviour_ok"]]
        summary["out_of_scope_refused"] = f"{sum(r['behaviour_ok'] for r in oos)}/{len(oos)}"
        summary["out_of_scope_not_refused"] = [r["id"] for r in oos if not r["behaviour_ok"]]

    t = spec["thresholds"]
    checks = {}
    if answerable:
        checks["retrieval_hit_rate"] = summary["retrieval_hit_rate"] >= t["retrieval_hit_rate"]
    if mode in ("ask", "agentic"):
        if answerable:
            checks["citation_correct_rate"] = summary["citation_correct_rate"] >= t["citation_correct_rate"]
        checks["not_in_corpus_handled"] = not summary["not_in_corpus_invented"]
        if mode == "agentic":
            checks["out_of_scope_refused"] = not summary["out_of_scope_not_refused"]
    summary["thresholds_met"] = checks
    return {"summary": summary, "results": results}


def write_report(report: dict, mode: str, suffix: str) -> Path:
    out_dir = EVAL_DIR / "results"
    out_dir.mkdir(exist_ok=True)
    name = f"{mode}{suffix}"
    (out_dir / f"{name}.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = [f"# Driver Ops eval: {name}", "", "```json", json.dumps(report["summary"], indent=2, ensure_ascii=False), "```", ""]
    for r in report["results"]:
        lines.append(f"## {r['id']} ({r['behaviour']}): {r['question']}")
        lines.append(f"- retrieved: {r.get('retrieved')}  hit: {r.get('hit')}  mode: {r.get('search_mode')}  time: {r.get('seconds')}s")
        if "answer" in r:
            flags = {k: r[k] for k in ("cited", "citation_correct", "refused", "not_found", "missing_facts", "invented",
                                       "points_to_ok", "removed_citations", "retrieval_attempts", "rewritten_query",
                                       "guardrail_score") if k in r}
            lines.append(f"- {json.dumps(flags, ensure_ascii=False)}")
            lines.append("")
            lines.extend("> " + line for line in r["answer"].splitlines())
        lines.append("")
    path = out_dir / f"{name}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["bm25", "hybrid", "ask", "agentic"], required=True)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--only", nargs="*", help="question ids, e.g. Q01 Q24")
    parser.add_argument("--suffix", default="", help="appended to the report file name")
    parser.add_argument("--model", help="Ollama model to use instead of the configured one")
    args = parser.parse_args()
    report = run(args.mode, args.base_url, args.only, args.model)
    path = write_report(report, args.mode, args.suffix)
    print(json.dumps(report["summary"], indent=2, ensure_ascii=False))
    print(f"Report: {path}")
    sys.exit(0 if all(report["summary"]["thresholds_met"].values()) else 1)
