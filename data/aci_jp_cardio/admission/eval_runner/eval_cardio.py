#!/usr/bin/env python3
"""
ACI-JP-Cardio Benchmark — main evaluation runner.

Generates SOAP and admission summaries from the SLM, then computes:
  - ROUGE-L          (lexical similarity)
  - BERTScore F1     (semantic similarity, Japanese)
  - drug_f1          (薬剤名 F1, MEDCON 代替)
  - diagnosis_f1     (診断名 F1)
  - vitals_match     (バイタル/検査値 ±10% 一致率)
  - opus_judge       (5 軸 rubric, 別 stage で実行)

Usage:
    python3 eval_cardio.py \\
        --cases ../cases.jsonl \\
        --target soap \\
        --model 4b_soap_full \\
        --slm-url http://localhost:8081 \\
        --output ../results/run_$(date +%s).json

Modes for --model (which LoRA to activate):
    4b_soap_full      → port 8081, LoRA id=1 (production SOAP)
    4b_admission      → port 8081, LoRA id=2 (4B admission fallback)
    9b_admission      → port 8083, LoRA id=0 (production 9B admission)

Pass --target soap or --target admission to control which generation runs.
"""
import argparse
import json
import logging
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

# Local modules
sys.path.insert(0, str(Path(__file__).parent))
from prompts import build_soap_messages, build_admission_messages, assemble_interview
from slm_client import (
    LlamaServerClient,
    LoRA_SOAP_FULL_4B, LoRA_ADMISSION_4B_FALLBACK, LoRA_ADMISSION_9B,
)
from soap_parser import parse_soap
from metrics_drug import compute_drug_f1, normalize_keyfacts_drugs
from metrics_diagnosis import compute_diagnosis_f1, normalize_keyfacts_diagnoses
from metrics_vitals import compute_vitals_match
from metrics_text import compute_text_metrics

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("eval_cardio")


MODEL_CONFIGS = {
    "4b_soap_full": {"url": "http://localhost:8081", "lora_id": LoRA_SOAP_FULL_4B, "label": "4B + soap_full LoRA"},
    "4b_admission": {"url": "http://localhost:8081", "lora_id": LoRA_ADMISSION_4B_FALLBACK, "label": "4B + admission LoRA (fallback)"},
    "9b_admission": {"url": "http://localhost:8083", "lora_id": LoRA_ADMISSION_9B, "label": "9B + admission LoRA"},
}


def load_cases(path: Path) -> list:
    cases = []
    with open(path, encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


def generate_soap(client: LlamaServerClient, lora_id: int, interview: str) -> dict:
    messages = build_soap_messages(interview)
    resp = client.chat(messages, active_lora_id=lora_id, max_tokens=1536, temperature=0.3)
    soap = parse_soap(resp["text"])
    return {
        "soap": soap,
        "raw": resp["text"],
        "latency_ms": resp["latency_ms"],
        "parse_ok": all(soap.get(k) for k in ("S", "O", "A", "P")),
    }


def generate_admission(client: LlamaServerClient, lora_id: int, interview: str) -> dict:
    messages = build_admission_messages(interview)
    resp = client.chat(messages, active_lora_id=lora_id, max_tokens=1536, temperature=0.3)
    return {
        "admission": resp["text"].strip(),
        "raw": resp["text"],
        "latency_ms": resp["latency_ms"],
    }


def evaluate_soap(case: dict, gen: dict, skip_bertscore: bool = False) -> dict:
    soap = gen["soap"]
    ref_soap = case.get("reference_soap") or {}
    kf = case.get("key_facts") or {}

    # Concatenate for whole-text metrics
    gen_full = "\n".join(soap.get(k, "") for k in ("S", "O", "A", "P"))
    ref_full = "\n".join(ref_soap.get(k, "") for k in ("S", "O", "A", "P"))

    text_metrics = compute_text_metrics(gen_full, ref_full, skip_bertscore=skip_bertscore)

    gold_drugs = normalize_keyfacts_drugs(
        (kf.get("medications_to_start") or []) + (kf.get("medications_to_continue") or [])
    )
    gold_diagnoses = normalize_keyfacts_diagnoses(kf.get("diagnoses") or [])

    return {
        **text_metrics,
        "drug_f1": compute_drug_f1(gen_full, gold_drugs),
        "diagnosis_f1": compute_diagnosis_f1(gen_full, gold_diagnoses),
        "vitals_match": compute_vitals_match(gen_full, kf.get("vitals"), kf.get("labs")),
        "parse_ok": gen["parse_ok"],
        "section_lengths": {k: len(soap.get(k, "")) for k in ("S", "O", "A", "P")},
    }


def evaluate_admission(case: dict, gen: dict, skip_bertscore: bool = False) -> dict:
    if case.get("is_negative_control"):
        # SCP: admission was not requested for these. Skip metrics.
        return {"skipped": "negative_control"}

    gen_text = gen["admission"]
    ref_text = case.get("reference_admission_summary") or ""
    kf = case.get("key_facts") or {}

    text_metrics = compute_text_metrics(gen_text, ref_text, skip_bertscore=skip_bertscore)

    gold_drugs = normalize_keyfacts_drugs(
        (kf.get("medications_to_start") or []) + (kf.get("medications_to_continue") or [])
    )
    gold_diagnoses = normalize_keyfacts_diagnoses(kf.get("diagnoses") or [])

    return {
        **text_metrics,
        "drug_f1": compute_drug_f1(gen_text, gold_drugs),
        "diagnosis_f1": compute_diagnosis_f1(gen_text, gold_diagnoses),
        "vitals_match": compute_vitals_match(gen_text, kf.get("vitals"), kf.get("labs")),
        "output_length": len(gen_text),
    }


def aggregate_summary(per_case: list, target: str) -> dict:
    """Compute average metrics, also broken down by format and difficulty."""
    valid = [r for r in per_case if "metrics" in r and not r["metrics"].get("skipped")]
    if not valid:
        return {"total_cases": len(per_case), "valid_evaluations": 0}

    def avg(field, sub=None, subkey=None):
        vals = []
        for r in valid:
            m = r["metrics"]
            v = m.get(field) if not sub else (m.get(field, {}) or {}).get(sub)
            if subkey and v is not None:
                v = v.get(subkey) if isinstance(v, dict) else None
            if isinstance(v, (int, float)):
                vals.append(v)
        return round(sum(vals) / len(vals), 4) if vals else None

    overall = {
        "total_cases": len(per_case),
        "valid_evaluations": len(valid),
        "rouge_l": avg("rouge_l"),
        "bertscore_f1": avg("bertscore_f1"),
        "drug_f1": avg("drug_f1", "f1"),
        "drug_recall": avg("drug_f1", "recall"),
        "drug_precision": avg("drug_f1", "precision"),
        "diagnosis_f1": avg("diagnosis_f1", "f1"),
        "vitals_match_rate": avg("vitals_match", "match_rate"),
        "mean_latency_ms": int(sum(r.get("latency_ms", 0) for r in valid) / len(valid)) if valid else 0,
    }
    if target == "soap":
        overall["parse_ok_rate"] = round(sum(1 for r in valid if r["metrics"].get("parse_ok")) / len(valid), 3)

    # Component score for ranking (if metrics present)
    if all(overall.get(k) is not None for k in ("rouge_l", "drug_f1", "diagnosis_f1")):
        comps = [overall["rouge_l"], overall.get("bertscore_f1") or 0,
                 overall["drug_f1"], overall["diagnosis_f1"], overall["vitals_match_rate"] or 0]
        overall["composite_score"] = round(sum(comps) / len(comps), 4)

    # Stratified
    by_format = {}
    for fmt in ("structured", "voice"):
        sub = [r for r in valid if r["format"] == fmt]
        if sub:
            by_format[fmt] = {
                "n": len(sub),
                "rouge_l": round(sum(r["metrics"].get("rouge_l", 0) for r in sub) / len(sub), 4),
                "drug_f1": round(sum(r["metrics"].get("drug_f1", {}).get("f1", 0) for r in sub) / len(sub), 4),
                "diagnosis_f1": round(sum(r["metrics"].get("diagnosis_f1", {}).get("f1", 0) for r in sub) / len(sub), 4),
            }
    overall["by_format"] = by_format

    return overall


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", required=True, type=Path)
    parser.add_argument("--target", required=True, choices=["soap", "admission"])
    parser.add_argument("--model", required=True, choices=list(MODEL_CONFIGS.keys()))
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--limit", type=int, default=0, help="0=all, otherwise first N")
    parser.add_argument("--skip-bertscore", action="store_true")
    parser.add_argument("--include-negative-control", action="store_true",
                       help="By default SCP is skipped for admission target")
    args = parser.parse_args()

    cfg = MODEL_CONFIGS[args.model]
    log.info(f"=== run config ===")
    log.info(f"  cases: {args.cases}")
    log.info(f"  target: {args.target}")
    log.info(f"  model: {args.model} ({cfg['label']}) at {cfg['url']}")
    log.info(f"  output: {args.output}")

    cases = load_cases(args.cases)
    if args.limit:
        cases = cases[:args.limit]
    log.info(f"  cases loaded: {len(cases)}")

    client = LlamaServerClient(cfg["url"])
    if not client.health():
        log.error(f"server not healthy at {cfg['url']}")
        sys.exit(2)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    per_case = []
    raw_outputs = {}

    for i, case in enumerate(cases, 1):
        eid = case["encounter_id"]

        # Skip admission for negative controls unless overridden
        if args.target == "admission" and case.get("is_negative_control") and not args.include_negative_control:
            log.info(f"[{i}/{len(cases)}] {eid}: SKIP (negative control)")
            per_case.append({
                "encounter_id": eid,
                "format": case["format"],
                "disease": case["disease_label"],
                "skipped": "negative_control",
            })
            continue

        interview = assemble_interview(case)

        try:
            t0 = time.time()
            if args.target == "soap":
                gen = generate_soap(client, cfg["lora_id"], interview)
                metrics = evaluate_soap(case, gen, skip_bertscore=args.skip_bertscore)
                raw_outputs[eid] = gen["soap"]
            else:
                gen = generate_admission(client, cfg["lora_id"], interview)
                metrics = evaluate_admission(case, gen, skip_bertscore=args.skip_bertscore)
                raw_outputs[eid] = gen["admission"]

            elapsed = time.time() - t0
            score_summary = (
                f"R-L={metrics.get('rouge_l', '?')} drug_f1={metrics.get('drug_f1', {}).get('f1', '?') if isinstance(metrics.get('drug_f1'), dict) else '?'} "
                f"diag_f1={metrics.get('diagnosis_f1', {}).get('f1', '?') if isinstance(metrics.get('diagnosis_f1'), dict) else '?'}"
            )
            log.info(f"[{i}/{len(cases)}] {eid}: {gen['latency_ms']}ms  {score_summary}")

            per_case.append({
                "encounter_id": eid,
                "format": case["format"],
                "disease": case["disease_label"],
                "difficulty": case.get("difficulty"),
                "is_negative_control": case.get("is_negative_control", False),
                "latency_ms": gen["latency_ms"],
                "metrics": metrics,
                "generated": gen.get("soap") if args.target == "soap" else gen.get("admission"),
                "raw_output": gen["raw"][:2000],  # truncated
            })
        except Exception as e:
            log.exception(f"[{i}/{len(cases)}] {eid}: FAILED")
            per_case.append({
                "encounter_id": eid,
                "format": case["format"],
                "error": str(e),
            })

    aggregate = aggregate_summary(per_case, args.target)
    log.info(f"=== aggregate ===")
    for k, v in aggregate.items():
        log.info(f"  {k}: {v}")

    out = {
        "run_id": f"{args.model}_{args.target}_{int(time.time())}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config": {
            "model": args.model,
            "url": cfg["url"],
            "lora_id": cfg["lora_id"],
            "target": args.target,
            "skip_bertscore": args.skip_bertscore,
        },
        "aggregate": aggregate,
        "per_case": per_case,
        "raw_outputs": raw_outputs,
    }
    with open(args.output, "w", encoding="utf-8") as fp:
        json.dump(out, fp, ensure_ascii=False, indent=2)
    log.info(f"wrote {args.output}")


if __name__ == "__main__":
    main()
