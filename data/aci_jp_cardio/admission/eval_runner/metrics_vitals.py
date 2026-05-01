"""
Vitals/labs match rate — extracts numeric values for known vital sign / lab keys
and checks whether they're present in the generated text within ±10%.
"""
import re
from typing import Dict


VITAL_PATTERNS = {
    # blood pressure: "BP 152/94" or "152/94 mmHg" or "血圧 152/94"
    "BP_sys": [r"(?:BP|血圧)?\s*(\d{2,3})\s*/\s*\d{2,3}\s*(?:mmHg)?"],
    "BP_dia": [r"(?:BP|血圧)?\s*\d{2,3}\s*/\s*(\d{2,3})\s*(?:mmHg)?"],
    "HR": [r"(?:HR|心拍|脈)\s*[:：]?\s*(\d{2,3})\s*(?:回|/min|bpm)?"],
    "SpO2": [r"SpO2\s*[:：]?\s*(\d{2,3})\s*%?"],
    "RR": [r"(?:RR|呼吸数)\s*[:：]?\s*(\d{1,2})\s*(?:回|/min)?"],
    "BT": [r"(?:BT|体温|T\.P\.|t\.p\.)\s*[:：]?\s*(\d{2}(?:\.\d)?)\s*(?:℃|度)?"],
}

LAB_PATTERNS = {
    "Tnl": [r"(?:troponin\s*I|トロポニン\s*I|tnl|トロポニン)\s*[:：]?\s*(\d+(?:\.\d+)?)"],
    "CK": [r"\bCK\s*[:：]?\s*(\d+)"],
    "CK_MB": [r"CK-?\s*MB\s*[:：]?\s*(\d+)"],
    "BNP": [r"\bBNP\s*[:：]?\s*(\d+(?:\.\d+)?)"],
    "Cr": [r"(?:Cr|クレアチニン)\s*[:：]?\s*(\d+(?:\.\d+)?)"],
    "eGFR": [r"eGFR\s*[:：]?\s*(\d+(?:\.\d+)?)"],
    "Glucose": [r"(?:glucose|血糖|BG)\s*[:：]?\s*(\d+(?:\.\d+)?)"],
    "HbA1c": [r"HbA1c\s*[:：]?\s*(\d+(?:\.\d+)?)"],
    "LDL_C": [r"(?:LDL|LDL-?C)\s*[:：]?\s*(\d+)"],
    "K": [r"\bK\s*[:：]?\s*(\d+(?:\.\d+)?)"],
    "D_dimer": [r"D-?dimer\s*[:：]?\s*(\d+(?:\.\d+)?)"],
}

ALL_PATTERNS = {**VITAL_PATTERNS, **LAB_PATTERNS}


def extract_value(text: str, key: str):
    patterns = ALL_PATTERNS.get(key, [])
    for p in patterns:
        m = re.search(p, text, flags=re.IGNORECASE)
        if m:
            try:
                return float(m.group(1))
            except (ValueError, IndexError):
                continue
    return None


def compute_vitals_match(generated_text: str, gold_vitals: Dict, gold_labs: Dict, tolerance: float = 0.1) -> Dict:
    """For each vital/lab in gold, check presence with ±tolerance% tolerance."""
    expected = {**(gold_vitals or {}), **(gold_labs or {})}
    if not expected:
        return {"match_rate": 0.0, "matched": 0, "expected": 0, "details": {}}

    text = generated_text or ""
    matched = 0
    details = {}
    for key, gold_val in expected.items():
        if not isinstance(gold_val, (int, float)):
            continue
        pred_val = extract_value(text, key)
        if pred_val is None:
            details[key] = {"gold": gold_val, "predicted": None, "matched": False}
        else:
            tol = abs(gold_val) * tolerance
            ok = abs(pred_val - gold_val) <= max(tol, 0.5)
            if ok:
                matched += 1
            details[key] = {"gold": gold_val, "predicted": pred_val, "matched": ok}

    total = sum(1 for k, v in expected.items() if isinstance(v, (int, float)))
    return {
        "match_rate": round(matched / total, 3) if total else 0.0,
        "matched": matched,
        "expected": total,
        "details": details,
    }
