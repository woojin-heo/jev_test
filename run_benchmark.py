"""Jev guardrail benchmark runner.

Usage:
    export TYPESAFE_API_KEY=...        # or put TYPESAFE_API_KEY=... in ./.env (create a key at console.typesafe.ai)
    .venv/bin/python run_benchmark.py  # -> results/results.json, results/results.csv
    .venv/bin/python make_report.py    # -> results/report.html

For every case this sends one request to Jev (the whole filter battery in a single call) and
records latency (ms), input tokens, cost (USD), every filter probability, the fired labels,
and whether the classification was correct.
"""
from __future__ import annotations

import csv
import json
import os
import statistics
import sys
import time
from pathlib import Path

from typesafe_sdk import TypeSafeClient, TypeSafeError

import guardrail as g
from dataset import GROUNDING_CASES, MODERATION_CASES

OUT = Path(__file__).parent / "results"
OUT.mkdir(exist_ok=True)

# Load ./.env (TYPESAFE_API_KEY=...) if present. An existing environment variable wins.
_env = Path(__file__).parent / ".env"
if _env.exists():
    for line in _env.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def cost_usd(input_tokens: int) -> float:
    return input_tokens * g.PRICE_USD_PER_MTOK / 1_000_000


def run_one(client: TypeSafeClient, state, questions: dict, model: str):
    t0 = time.perf_counter()
    resp = client.system_one(state=state, questions=questions, model=model)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    return resp, elapsed_ms


def main(model: str = g.MODEL) -> int:
    if not os.environ.get("TYPESAFE_API_KEY"):
        print("TYPESAFE_API_KEY is not set. Create a key at console.typesafe.ai, then either\n"
              "  export TYPESAFE_API_KEY=...\n"
              "or add a line TYPESAFE_API_KEY=... to ./.env and run again.", file=sys.stderr)
        return 2

    rows: list[dict] = []
    # 20 s per request so a single stalled call cannot hang the whole run.
    with TypeSafeClient(timeout=20.0) as client:
        # 1) Moderation cases: Bedrock content / denied-topic / word / PII filters in one request
        for case in MODERATION_CASES:
            try:
                resp, ms = run_one(client, {"text": case["text"]}, g.INPUT_BATTERY, model)
            except TypeSafeError as e:
                print(f"[ERR] {case['id']}: {e}", file=sys.stderr)
                rows.append(dict(id=case["id"], category=case["category"], kind="moderation",
                                 text=case["text"], error=str(e)))
                continue
            probs = {k: round(resp.nouls[k].noul, 4) for k in g.NOUL_LABELS}
            fired = sorted(k for k, p in probs.items() if p >= g.THRESHOLD)
            if g.custom_word_hit(case["text"]):
                fired.append("custom_word")  # code-owned filter (Bedrock custom word list)
            expected = sorted(case["expected"])
            primary = resp.choices["primary_category"]
            pii_type = resp.choices["pii_type"]
            rows.append(dict(
                id=case["id"], category=case["category"], kind="moderation", text=case["text"],
                model=resp.model, elapsed_ms=round(ms, 1),
                input_tokens=resp.usage.input_tokens, output_tokens=resp.usage.output_tokens,
                cost_usd=round(cost_usd(resp.usage.input_tokens), 8),
                probs=probs, fired=fired, expected=expected,
                # exact_match: the set of fired Noul filters equals the expected label set
                exact_match=(sorted(set(fired) - {"custom_word"}) == expected),
                # primary_match: Jev's single classification is one of the expected labels
                # (or 'none' for a safe case)
                primary_match=(primary.choice == "none") if not expected else (primary.choice in expected),
                primary_category=primary.choice, primary_confidence=round(primary.confidence, 3),
                primary_probabilities={k: round(v, 3) for k, v in primary.probabilities.items()},
                pii_type=pii_type.choice, pii_type_confidence=round(pii_type.confidence, 3),
            ))
            mark = "OK " if rows[-1]["primary_match"] else "MISS"
            print(f"[{mark}] {case['id']:<26} {ms:7.0f}ms  {resp.usage.input_tokens:5d}tok  "
                  f"primary={primary.choice} fired={fired}")

        # 2) Contextual grounding cases: source / query / response as the state
        for case in GROUNDING_CASES:
            try:
                resp, ms = run_one(client, case["state"], g.GROUNDING_BATTERY, model)
            except TypeSafeError as e:
                print(f"[ERR] {case['id']}: {e}", file=sys.stderr)
                rows.append(dict(id=case["id"], category=case["category"], kind="grounding",
                                 text=json.dumps(case["state"]), error=str(e)))
                continue
            probs = {k: round(resp.nouls[k].noul, 4) for k in g.GROUNDING_BATTERY}
            fired = sorted(k for k, p in probs.items() if p >= g.GROUNDING_THRESHOLD)
            expected = sorted(case["expected"])
            rows.append(dict(
                id=case["id"], category=case["category"], kind="grounding",
                text=case["state"]["response"], state=case["state"],
                model=resp.model, elapsed_ms=round(ms, 1),
                input_tokens=resp.usage.input_tokens, output_tokens=resp.usage.output_tokens,
                cost_usd=round(cost_usd(resp.usage.input_tokens), 8),
                probs=probs, fired=fired, expected=expected,
                exact_match=(fired == expected), primary_match=(fired == expected),
                primary_category="grounded+relevant" if fired == ["grounded", "relevant"] else
                                 ("ungrounded" if "grounded" not in fired else "irrelevant"),
            ))
            mark = "OK " if rows[-1]["primary_match"] else "MISS"
            print(f"[{mark}] {case['id']:<26} {ms:7.0f}ms  {resp.usage.input_tokens:5d}tok  "
                  f"grounded={probs['grounded']:.2f} relevant={probs['relevant']:.2f}")

    ok = [r for r in rows if "error" not in r]
    lat = [r["elapsed_ms"] for r in ok]
    summary = dict(
        model=ok[0]["model"] if ok else model,
        n_cases=len(rows), n_ok=len(ok), n_errors=len(rows) - len(ok),
        primary_accuracy=round(sum(r["primary_match"] for r in ok) / max(len(ok), 1), 4),  # classification correct
        accuracy=round(sum(r["exact_match"] for r in ok) / max(len(ok), 1), 4),            # fired filter set exact match
        total_input_tokens=sum(r["input_tokens"] for r in ok),
        total_cost_usd=round(sum(r["cost_usd"] for r in ok), 6),
        latency_ms=dict(mean=round(statistics.mean(lat), 1) if lat else None,
                        p50=round(statistics.median(lat), 1) if lat else None,
                        p95=round(sorted(lat)[int(len(lat) * 0.95) - 1], 1) if len(lat) >= 2 else None,
                        min=round(min(lat), 1) if lat else None, max=round(max(lat), 1) if lat else None),
        threshold=g.THRESHOLD, price_usd_per_mtok=g.PRICE_USD_PER_MTOK,
        run_at=time.strftime("%Y-%m-%d %H:%M:%S %z"),
    )
    (OUT / "results.json").write_text(json.dumps(dict(summary=summary, rows=rows), ensure_ascii=False, indent=2))

    cols = ["id", "category", "kind", "elapsed_ms", "input_tokens", "cost_usd", "primary_category",
            "primary_match", "fired", "expected", "exact_match", "text"]
    with (OUT / "results.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({**r, "fired": "|".join(r.get("fired", [])), "expected": "|".join(r.get("expected", []))})

    print("\n== SUMMARY ==")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else g.MODEL))
