#!/usr/bin/env python3
"""
Compare multiple eval runs and produce a Markdown summary table.

Usage:
    python3 aggregate.py results/baseline_4b_soap.json results/baseline_9b_admission.json [...]
    python3 aggregate.py results/*.json --output results/comparison.md
"""
import argparse
import json
from pathlib import Path


def load_run(path: Path) -> dict:
    with open(path, encoding="utf-8") as fp:
        return json.load(fp)


def fmt_pct(v):
    if v is None:
        return "—"
    return f"{v * 100:.1f}%" if isinstance(v, (int, float)) else str(v)


def fmt_score(v):
    if v is None:
        return "—"
    return f"{v:.3f}" if isinstance(v, (int, float)) else str(v)


def render_overall_table(runs: list) -> str:
    headers = ["Run", "Target", "Cases", "ROUGE-L", "BERTScore", "Drug F1",
               "Drug Recall", "Drug Precision", "Diagnosis F1", "Vitals %", "Latency (ms)", "Composite"]
    rows = []
    for r in runs:
        agg = r["aggregate"]
        cfg = r["config"]
        rows.append([
            r["run_id"],
            cfg["target"],
            f"{agg.get('valid_evaluations')}/{agg.get('total_cases')}",
            fmt_score(agg.get("rouge_l")),
            fmt_score(agg.get("bertscore_f1")),
            fmt_score(agg.get("drug_f1")),
            fmt_pct(agg.get("drug_recall")),
            fmt_pct(agg.get("drug_precision")),
            fmt_score(agg.get("diagnosis_f1")),
            fmt_pct(agg.get("vitals_match_rate")),
            str(agg.get("mean_latency_ms", "?")),
            fmt_score(agg.get("composite_score")),
        ])
    return "| " + " | ".join(headers) + " |\n" + \
           "|" + "|".join(["---"] * len(headers)) + "|\n" + \
           "\n".join("| " + " | ".join(row) + " |" for row in rows)


def render_by_format_table(runs: list) -> str:
    out = ["### Format-stratified scores\n"]
    for r in runs:
        bf = r["aggregate"].get("by_format", {})
        if not bf:
            continue
        out.append(f"#### {r['run_id']}\n")
        out.append("| Format | N | ROUGE-L | Drug F1 | Diagnosis F1 |")
        out.append("|---|---|---|---|---|")
        for fmt in ("structured", "voice"):
            d = bf.get(fmt)
            if d:
                out.append(f"| {fmt} | {d['n']} | {fmt_score(d['rouge_l'])} | {fmt_score(d['drug_f1'])} | {fmt_score(d['diagnosis_f1'])} |")
        out.append("")
    return "\n".join(out)


def render_per_disease_table(runs: list) -> str:
    """Per-disease, per-run table for soap target."""
    diseases = set()
    for r in runs:
        for pc in r["per_case"]:
            if not pc.get("skipped"):
                diseases.add(pc.get("disease"))
    diseases = sorted(diseases)

    soap_runs = [r for r in runs if r["config"]["target"] == "soap"]
    if not soap_runs:
        return ""

    out = ["### Per-disease ROUGE-L (SOAP target only)\n"]
    headers = ["Disease"] + [r["run_id"] for r in soap_runs]
    out.append("| " + " | ".join(headers) + " |")
    out.append("|" + "|".join(["---"] * len(headers)) + "|")
    for disease in diseases:
        row = [disease]
        for r in soap_runs:
            cells = []
            for pc in r["per_case"]:
                if pc.get("disease") == disease and not pc.get("skipped") and "metrics" in pc:
                    val = pc["metrics"].get("rouge_l", 0)
                    cells.append(fmt_score(val))
            row.append(" / ".join(cells) if cells else "—")
        out.append("| " + " | ".join(row) + " |")
    return "\n".join(out)


def render_failures(runs: list) -> str:
    """Notable failures: parse failures, drug FP, missing diagnoses."""
    out = ["### Notable issues per case\n"]
    for r in runs:
        out.append(f"#### {r['run_id']}\n")
        for pc in r["per_case"]:
            if pc.get("skipped") or "metrics" not in pc:
                continue
            m = pc["metrics"]
            issues = []
            if r["config"]["target"] == "soap" and not m.get("parse_ok"):
                issues.append("parse failed")
            drug_fp = m.get("drug_f1", {}).get("false_positives") if isinstance(m.get("drug_f1"), dict) else None
            if drug_fp:
                issues.append(f"hallucinated drugs: {drug_fp}")
            drug_miss = m.get("drug_f1", {}).get("missing") if isinstance(m.get("drug_f1"), dict) else None
            if drug_miss:
                issues.append(f"missed drugs: {drug_miss[:5]}{'...' if len(drug_miss) > 5 else ''}")
            diag_miss = m.get("diagnosis_f1", {}).get("missing") if isinstance(m.get("diagnosis_f1"), dict) else None
            if diag_miss:
                issues.append(f"missed diagnoses: {diag_miss}")
            if issues:
                out.append(f"- **{pc['encounter_id']}** ({pc.get('format')}/{pc.get('difficulty', '?')}): " + "; ".join(issues))
        out.append("")
    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    runs = [load_run(p) for p in args.inputs]
    runs.sort(key=lambda r: (r["config"]["target"], r["config"]["model"]))

    parts = []
    parts.append("# ACI-JP-Cardio Benchmark — Comparison\n")
    parts.append("## Overall scores\n")
    parts.append(render_overall_table(runs))
    parts.append("\n")
    parts.append(render_by_format_table(runs))
    parts.append("\n")
    parts.append(render_per_disease_table(runs))
    parts.append("\n")
    parts.append(render_failures(runs))

    md = "\n".join(parts)
    if args.output:
        args.output.write_text(md, encoding="utf-8")
        print(f"wrote {args.output}")
    else:
        print(md)


if __name__ == "__main__":
    main()
