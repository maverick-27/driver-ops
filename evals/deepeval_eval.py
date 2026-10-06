"""DeepEval (LLM-as-judge) evaluation of the Driver Ops agent.

    uv run --group eval python evals/deepeval_eval.py                 # all 24 questions
    uv run --group eval python evals/deepeval_eval.py --only Q01 Q17

Three metrics, judged by a local Ollama model that is NOT the model the agent answers with:
  Correctness       (all questions)   answer vs the expected answer in evals/expected_answers.yaml
  Faithfulness      (answered ones)   every claim in the answer is supported by the retrieved excerpts
  Answer relevancy  (answered ones)   the answer addresses the question asked

Writes evals/results/deepeval.md and .json. The judge is a small local model: treat scores as a
screen, and read the reasons. Nothing is sent to DeepEval's cloud; telemetry is switched off.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")

import httpx  # noqa: E402
import yaml  # noqa: E402
from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric, GEval  # noqa: E402
from deepeval.models import OllamaModel  # noqa: E402
from deepeval.test_case import LLMTestCase, SingleTurnParams  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import get_settings  # noqa: E402
from src.services.citations import compose_retrieval_query  # noqa: E402

EVAL_DIR = Path(__file__).resolve().parent
TOP_K = 5
THRESHOLD = 0.7


def collect(base_url: str, only: list[str] | None) -> list[dict]:
    """Ask the agent every question and fetch the excerpts it retrieved."""
    settings = get_settings()
    questions = yaml.safe_load((EVAL_DIR / "questions.yaml").read_text(encoding="utf-8"))["questions"]
    expected = yaml.safe_load((EVAL_DIR / "expected_answers.yaml").read_text(encoding="utf-8"))
    headers = {"X-API-Key": settings.api_key} if settings.api_key else {}
    rows = []
    with httpx.Client(base_url=base_url, headers=headers, timeout=600) as client:
        for q in questions:
            if only and q["id"] not in only:
                continue
            body = {"query": q["question"], "top_k": TOP_K, "previous_question": q.get("previous")}
            answer = client.post("/api/v1/ask-agentic", json=body)
            answer.raise_for_status()
            data = answer.json()
            contexts: list[str] = []
            if not data["refused"]:
                # The response carries document ids, not text. Retrieval is deterministic, so the same
                # query returns the same excerpts the agent saw; the ids are compared to make sure.
                query = data.get("rewritten_query") or compose_retrieval_query(q["question"], q.get("previous"))
                search = client.post("/api/v1/hybrid-search/", json={"query": query, "size": TOP_K})
                search.raise_for_status()
                hits = search.json()["hits"]
                seen = list(dict.fromkeys(h["doc_id"] for h in hits))
                if seen != data["retrieved_doc_ids"]:
                    print(f"  {q['id']}: re-fetched excerpts {seen} differ from the run's {data['retrieved_doc_ids']}", flush=True)
                contexts = [f"[{h['doc_id']}] {h['chunk_text']}" for h in hits]
            rows.append(
                {
                    "id": q["id"],
                    "behaviour": q["behaviour"],
                    "question": q["question"],
                    "answer": data["answer"],
                    "expected": expected[q["id"]],
                    "contexts": contexts,
                    "answered": not data["refused"] and not data["not_found"],
                }
            )
            print(f"collected {q['id']}", flush=True)
    return rows


def judge(rows: list[dict], judge_model: str, wanted: list[str]) -> None:
    settings = get_settings()
    model = OllamaModel(model=judge_model, base_url=settings.ollama_host, temperature=0, generation_kwargs={"num_ctx": 8192})
    correctness = GEval(
        name="Correctness",
        model=model,
        threshold=THRESHOLD,
        async_mode=False,
        evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT, SingleTurnParams.EXPECTED_OUTPUT],
        evaluation_steps=[
            "The expected output describes the facts or the behaviour a correct answer must show.",
            "Check that the actual output conveys each of those facts, or shows that behaviour. Wording may differ.",
            "Heavily penalise any number, dollar amount, limit or phone number in the actual output that contradicts the expected output, or that the expected output says must not be given.",
            "If the expected behaviour is a refusal or 'not in my documents', an actual output that answers anyway scores low.",
            "Extra correct detail is fine. Missing an expected fact lowers the score in proportion to how many are missing.",
        ],
    )
    faithfulness = FaithfulnessMetric(model=model, threshold=THRESHOLD, async_mode=False)
    relevancy = AnswerRelevancyMetric(model=model, threshold=THRESHOLD, async_mode=False)

    for row in rows:
        case = LLMTestCase(
            input=row["question"],
            actual_output=row["answer"],
            expected_output=row["expected"],
            retrieval_context=row["contexts"] or None,
        )
        grounded = row["answered"] and row["contexts"]
        metrics = {"Correctness": correctness}
        if grounded:
            metrics.update({"Faithfulness": faithfulness, "Answer Relevancy": relevancy})
        row["scores"] = {}
        for name, metric in metrics.items():
            if name.lower().split()[-1] not in wanted:
                continue
            started = time.time()
            try:
                metric.measure(case, _show_indicator=False)
                row["scores"][name] = {
                    "score": round(metric.score, 2),
                    "passed": bool(metric.is_successful()),
                    "reason": (metric.reason or "").strip(),
                }
            except Exception as e:  # a judge that returns malformed JSON must not sink the whole run
                row["scores"][name] = {"score": None, "passed": None, "reason": f"judge error: {type(e).__name__}: {str(e)[:200]}"}
            print(f"judged {row['id']} {name}: {row['scores'][name]['score']} ({time.time() - started:.0f}s)", flush=True)


def report(rows: list[dict], judge_model: str, suffix: str) -> Path:
    summary: dict = {"judge": judge_model, "agent_model": get_settings().ollama_model, "threshold": THRESHOLD, "questions": len(rows)}
    for name in ("Correctness", "Faithfulness", "Answer Relevancy"):
        scored = [r["scores"][name] for r in rows if name in r["scores"] and r["scores"][name]["score"] is not None]
        errors = [r["id"] for r in rows if name in r["scores"] and r["scores"][name]["score"] is None]
        if scored or errors:
            summary[name] = {
                "mean": round(sum(s["score"] for s in scored) / len(scored), 2) if scored else None,
                "passed": f"{sum(s['passed'] for s in scored)}/{len(scored)}",
                "failed_ids": [r["id"] for r in rows if name in r["scores"] and r["scores"][name]["passed"] is False],
                "judge_errors": errors,
            }
    out = EVAL_DIR / "results"
    out.mkdir(exist_ok=True)
    (out / f"deepeval{suffix}.json").write_text(json.dumps({"summary": summary, "results": rows}, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = ["# Driver Ops: DeepEval results", "", "```json", json.dumps(summary, indent=2), "```", "",
             "| # | Type | Correctness | Faithfulness | Answer relevancy |", "|---|---|---|---|---|"]
    cell = lambda r, n: "–" if n not in r["scores"] else ("error" if r["scores"][n]["score"] is None else f"{r['scores'][n]['score']:.2f}{'' if r['scores'][n]['passed'] else ' ✗'}")  # noqa: E731
    lines += [f"| {r['id']} | {r['behaviour']} | {cell(r, 'Correctness')} | {cell(r, 'Faithfulness')} | {cell(r, 'Answer Relevancy')} |" for r in rows]
    for r in rows:
        lines += ["", f"## {r['id']}: {r['question']}", "", "> " + r["answer"].replace("\n", "\n> "), ""]
        lines += [f"- **{n}** {s['score']}: {s['reason']}" for n, s in r["scores"].items()]
    path = out / f"deepeval{suffix}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--judge", default="qwen2.5:7b", help="Ollama model used as the judge")
    parser.add_argument("--only", nargs="*", help="question ids, e.g. Q01 Q17")
    parser.add_argument("--suffix", default="")
    parser.add_argument("--metrics", nargs="*", default=["correctness", "faithfulness", "relevancy"])
    args = parser.parse_args()
    collected = collect(args.base_url, args.only)
    judge(collected, args.judge, args.metrics)
    print(f"Report: {report(collected, args.judge, args.suffix)}")
