#!/usr/bin/env python3
"""Benchmark the agentic ask endpoint with concurrency and latency percentiles."""

import asyncio
import json
import statistics
import sys
from pathlib import Path
from typing import Any

import httpx
import yaml
from pydantic import BaseModel


class AskRequest(BaseModel):
    query: str
    previous_question: str | None = None
    top_k: int = 5
    use_hybrid: bool = True
    model: str | None = None
    doc_types: list[str] | None = None


async def run_benchmark(
    base_url: str = "http://localhost:8000",
    concurrency: int = 1,
    questions_file: str = "evals/questions.yaml",
) -> None:
    """Run benchmark against the API."""
    questions_path = Path(questions_file)
    if not questions_path.exists():
        print(f"Error: {questions_file} not found")
        sys.exit(1)

    with open(questions_path) as f:
        data = yaml.safe_load(f)
    questions = data.get("questions", [])

    if not questions:
        print("Error: no questions found in YAML")
        sys.exit(1)

    print(f"\n📊 Benchmark: {len(questions)} questions, concurrency={concurrency}")
    print(f"API: {base_url}\n")

    results: list[dict[str, Any]] = []
    errors = 0

    async with httpx.AsyncClient(timeout=300, follow_redirects=True) as client:
        semaphore = asyncio.Semaphore(concurrency)

        async def ask_one(q: str, prev: str | None = None) -> None:
            nonlocal errors
            async with semaphore:
                try:
                    resp = await client.post(
                        f"{base_url}/api/v1/ask-agentic",
                        json={"query": q, "previous_question": prev},
                    )
                    if resp.status_code != 200:
                        print(f"❌ {q[:50]}... → {resp.status_code}")
                        errors += 1
                        return

                    data = resp.json()
                    total_ms = data.get("execution_time", 0) * 1000
                    timings = data.get("timings", {})
                    results.append({
                        "query": q,
                        "total_ms": total_ms,
                        "cached": data.get("cached", False),
                        "timings": timings,
                    })
                    cached_str = "(cached)" if data.get("cached") else ""
                    print(f"✓ {q[:50]}... → {total_ms:.0f}ms {cached_str}")
                except Exception as e:
                    print(f"❌ {q[:50]}... → {e}")
                    errors += 1

        tasks = [ask_one(q.get("question"), q.get("previous")) for q in questions]
        await asyncio.gather(*tasks)

    if not results:
        print("\nNo successful requests")
        sys.exit(1)

    total_ms_list = [r["total_ms"] for r in results]
    uncached_ms_list = [r["total_ms"] for r in results if not r["cached"]]

    print(f"\n{'='*60}")
    print(f"Results ({len(results)} successful, {errors} errors)")
    print(f"{'='*60}\n")

    if uncached_ms_list:
        print("📈 Uncached requests:")
        print(f"  Min:    {min(uncached_ms_list):7.0f}ms")
        print(f"  p50:    {statistics.median(uncached_ms_list):7.0f}ms")
        if len(uncached_ms_list) >= 3:
            sorted_ms = sorted(uncached_ms_list)
            p95_idx = int(len(sorted_ms) * 0.95)
            p99_idx = int(len(sorted_ms) * 0.99)
            print(f"  p95:    {sorted_ms[p95_idx]:7.0f}ms")
            print(f"  p99:    {sorted_ms[p99_idx]:7.0f}ms")
        print(f"  Max:    {max(uncached_ms_list):7.0f}ms")
        print(f"  Mean:   {statistics.mean(uncached_ms_list):7.0f}ms")
        print()

    cached_count = sum(1 for r in results if r["cached"])
    if cached_count:
        cached_ms_list = [r["total_ms"] for r in results if r["cached"]]
        print(f"💾 Cached requests ({cached_count}):")
        print(f"  p50:    {statistics.median(cached_ms_list):7.0f}ms")
        print(f"  Max:    {max(cached_ms_list):7.0f}ms")
        print()

    print(f"Overall (all {len(results)} requests):")
    print(f"  p50:    {statistics.median(total_ms_list):7.0f}ms")
    print()

    # Per-stage breakdown for uncached requests
    if uncached_ms_list:
        print("⏱️  Per-stage median (uncached):")
        stage_times: dict[str, list[float]] = {}
        for r in results:
            if not r["cached"]:
                for stage, ms in r.get("timings", {}).items():
                    if stage != "total":
                        stage_times.setdefault(stage, []).append(ms)

        for stage in sorted(stage_times.keys()):
            times = stage_times[stage]
            median_ms = statistics.median(times)
            print(f"  {stage:20s} {median_ms:7.0f}ms")


if __name__ == "__main__":
    asyncio.run(run_benchmark(concurrency=1))
