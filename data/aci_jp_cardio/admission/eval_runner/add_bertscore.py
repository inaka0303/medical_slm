#!/usr/bin/env python3
"""
Post-hoc BERTScore evaluator. Loads the Japanese BERT model once and adds
bertscore_f1 to multiple result JSON files in-place.

Usage:
    python3 add_bertscore.py results/baseline_4b_soap.json results/baseline_9b_admission.json
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def assemble_gen_text(pc: dict, target: str) -> str:
    if target == "soap":
        soap = pc.get("generated") or {}
        return "\n".join(soap.get(k, "") for k in ("S", "O", "A", "P"))
    return pc.get("generated") or ""


def assemble_ref_text(case: dict, target: str) -> str:
    if target == "soap":
        ref = case.get("reference_soap") or {}
        return "\n".join(ref.get(k, "") for k in ("S", "O", "A", "P"))
    return case.get("reference_admission_summary") or ""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+", type=Path)
    args = parser.parse_args()

    print("Loading bert_score and Japanese BERT model...")
    from bert_score import BERTScorer
    import torch

    device = "cuda" if torch.cuda.is_available() else "cpu"
    scorer = BERTScorer(
        model_type="cl-tohoku/bert-base-japanese-v3",
        num_layers=9,
        device=device,
        batch_size=8,
    )
    print(f"Model loaded on {device}.")

    # Load case index
    cases_dir = Path(__file__).parent.parent / "cases"
    cases_idx = {}
    for f in cases_dir.glob("JC-*.json"):
        with open(f, encoding="utf-8") as fp:
            c = json.load(fp)
        cases_idx[c["encounter_id"]] = c

    for input_path in args.inputs:
        with open(input_path, encoding="utf-8") as fp:
            run = json.load(fp)
        target = run["config"]["target"]

        cands = []
        refs = []
        idxs = []
        for i, pc in enumerate(run["per_case"]):
            if "metrics" not in pc or pc["metrics"].get("skipped"):
                continue
            case = cases_idx.get(pc["encounter_id"])
            if not case:
                continue
            gen = assemble_gen_text(pc, target)
            ref = assemble_ref_text(case, target)
            if not gen or not ref:
                continue
            cands.append(gen)
            refs.append(ref)
            idxs.append(i)

        print(f"\n[{input_path}] target={target} computing BERTScore for {len(cands)} cases")
        if not cands:
            continue

        P, R, F = scorer.score(cands, refs)
        for j, idx in enumerate(idxs):
            run["per_case"][idx]["metrics"]["bertscore_f1"] = round(F[j].item(), 4)

        # Recompute aggregate
        from eval_cardio import aggregate_summary
        run["aggregate"] = aggregate_summary(run["per_case"], target)

        with open(input_path, "w", encoding="utf-8") as fp:
            json.dump(run, fp, ensure_ascii=False, indent=2)
        print(f"  wrote {input_path}")
        print(f"  bertscore_f1 (mean): {run['aggregate'].get('bertscore_f1')}")
        print(f"  composite_score: {run['aggregate'].get('composite_score')}")


if __name__ == "__main__":
    main()
