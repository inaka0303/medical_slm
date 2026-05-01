#!/usr/bin/env python3
"""
Build cases.jsonl + ACI-Bench compatible CSV views from cases/*.json.

Usage:
    python3 build_jsonl.py

Outputs:
    cases.jsonl                           # one JSON object per line
    aci_compat/metadata.csv               # ACI-Bench-style metadata
    aci_compat/cases.csv                  # ACI-Bench-style data
"""
import json
import csv
import glob
import os
from pathlib import Path

ROOT = Path(__file__).parent.parent
CASES_DIR = ROOT / "cases"
OUT_JSONL = ROOT / "cases.jsonl"
ACI_DIR = ROOT / "aci_compat"
ACI_DIR.mkdir(exist_ok=True)


def assemble_dialogue(case: dict) -> str:
    """Convert structured 4-section interview or voice monologue to a single string
    that mirrors what the EMR backend assembles before sending to the SLM."""
    if case["format"] == "voice":
        return case.get("interview_text_voice", "") or ""
    it = case.get("interview_text") or {}
    parts = []
    if it.get("raw_text"):
        parts.append(f"【問診記録】\n{it['raw_text']}")
    if it.get("medication_list"):
        parts.append(f"【お薬手帳より】\n{it['medication_list']}")
    if it.get("exam_findings"):
        parts.append(f"【診察所見】\n{it['exam_findings']}")
    if it.get("lab_results"):
        parts.append(f"【検査結果】\n{it['lab_results']}")
    return "\n\n".join(parts)


def assemble_note(case: dict) -> str:
    """SOAP reference flattened to a single 'note' column for ACI compat."""
    s = case.get("reference_soap") or {}
    parts = []
    for sec in ("S", "O", "A", "P"):
        if s.get(sec):
            parts.append(f"{sec}: {s[sec]}")
    return "\n\n".join(parts)


def main():
    case_files = sorted(CASES_DIR.glob("JC-*.json"))
    if not case_files:
        raise SystemExit(f"No case files found in {CASES_DIR}")

    cases = []
    for f in case_files:
        with open(f, encoding="utf-8") as fp:
            cases.append(json.load(fp))

    # 1. cases.jsonl
    with open(OUT_JSONL, "w", encoding="utf-8") as fp:
        for c in cases:
            fp.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"wrote {OUT_JSONL} ({len(cases)} lines)")

    # 2. aci_compat/metadata.csv
    meta_path = ACI_DIR / "metadata.csv"
    with open(meta_path, "w", encoding="utf-8", newline="") as fp:
        w = csv.writer(fp)
        w.writerow([
            "dataset", "encounter_id", "id", "doctor_name",
            "patient_gender", "patient_age",
            "patient_firstname", "patient_familyname",
            "cc", "2nd_complaints",
        ])
        for i, c in enumerate(cases, 1):
            p = c.get("patient", {})
            e = c.get("encounter", {})
            second = ";".join(e.get("secondary_complaints") or [])
            w.writerow([
                "acijpcardio",
                c["encounter_id"],
                i,
                "",
                p.get("gender", ""),
                p.get("age", ""),
                "匿名",
                "匿名",
                e.get("chief_complaint", ""),
                second,
            ])
    print(f"wrote {meta_path}")

    # 3. aci_compat/cases.csv
    data_path = ACI_DIR / "cases.csv"
    with open(data_path, "w", encoding="utf-8", newline="") as fp:
        w = csv.writer(fp)
        w.writerow(["dataset", "encounter_id", "dialogue", "note"])
        for c in cases:
            w.writerow([
                "acijpcardio",
                c["encounter_id"],
                assemble_dialogue(c),
                assemble_note(c),
            ])
    print(f"wrote {data_path}")

    # Stats
    print("\n=== summary ===")
    print(f"  total: {len(cases)}")
    by_disease = {}
    for c in cases:
        d = c["disease_label_jp"]
        by_disease[d] = by_disease.get(d, 0) + 1
    for d, n in sorted(by_disease.items()):
        print(f"  {d}: {n}")


if __name__ == "__main__":
    main()
