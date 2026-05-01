#!/usr/bin/env python3
"""
Re-parse and re-score saved raw outputs from a previous eval_cardio run, without
re-calling the SLM. Useful when:
- The parser was improved
- New synonyms were added to the drug dict
- BERTScore is being added post-hoc

Usage:
    python3 reevaluate.py <input.json> [--output <new.json>] [--enable-bertscore]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from soap_parser import parse_soap
from metrics_drug import compute_drug_f1, normalize_keyfacts_drugs
from metrics_diagnosis import compute_diagnosis_f1, normalize_keyfacts_diagnoses
from metrics_vitals import compute_vitals_match
from metrics_text import compute_text_metrics


def load_cases_index() -> dict:
    cases_dir = Path(__file__).parent.parent / "cases"
    idx = {}
    for f in cases_dir.glob("JC-*.json"):
        with open(f, encoding="utf-8") as fp:
            c = json.load(fp)
        idx[c["encounter_id"]] = c
    return idx


def reevaluate_soap(case: dict, raw_output: str, skip_bertscore: bool) -> dict:
    soap = parse_soap(raw_output)
    parse_ok = all(soap.get(k) for k in ("S", "O", "A", "P"))

    ref_soap = case.get("reference_soap") or {}
    kf = case.get("key_facts") or {}

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
        "parse_ok": parse_ok,
        "section_lengths": {k: len(soap.get(k, "")) for k in ("S", "O", "A", "P")},
    }, soap


def reevaluate_admission(case: dict, raw_output: str, skip_bertscore: bool) -> dict:
    if case.get("is_negative_control"):
        return {"skipped": "negative_control"}

    gen_text = (raw_output or "").strip()
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--enable-bertscore", action="store_true")
    args = parser.parse_args()

    out_path = args.output or args.input.with_suffix(".reeval.json")

    with open(args.input, encoding="utf-8") as fp:
        run = json.load(fp)

    cases_idx = load_cases_index()
    target = run["config"]["target"]
    skip_bertscore = not args.enable_bertscore

    new_per_case = []
    for pc in run["per_case"]:
        eid = pc["encounter_id"]
        case = cases_idx.get(eid)
        if not case or "raw_output" not in pc:
            new_per_case.append(pc)
            continue

        raw = pc["raw_output"]
        if target == "soap":
            metrics, soap = reevaluate_soap(case, raw, skip_bertscore)
            new_pc = {**pc, "metrics": metrics, "generated": soap}
        else:
            metrics = reevaluate_admission(case, raw, skip_bertscore)
            new_pc = {**pc, "metrics": metrics}

        new_per_case.append(new_pc)

    # Recompute aggregate
    from eval_cardio import aggregate_summary
    new_aggregate = aggregate_summary(new_per_case, target)

    new_run = {
        **run,
        "aggregate": new_aggregate,
        "per_case": new_per_case,
        "reevaluated_at": str(Path(__file__).parent),
    }

    with open(out_path, "w", encoding="utf-8") as fp:
        json.dump(new_run, fp, ensure_ascii=False, indent=2)
    print(f"wrote {out_path}")
    print(f"\n=== aggregate ===")
    for k, v in new_aggregate.items():
        if k != "by_format":
            print(f"  {k}: {v}")
    print(f"  by_format: {new_aggregate.get('by_format')}")


if __name__ == "__main__":
    main()
