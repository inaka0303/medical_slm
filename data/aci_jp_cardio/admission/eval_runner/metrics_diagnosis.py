"""
Diagnosis name F1 — fuzzy match by tokenized partial string match plus a small
synonym table for English/Japanese cardiology terms.
"""
import re
from typing import Dict, List, Set


# Synonym map: lowercase variant -> canonical Japanese
DIAGNOSIS_SYNONYMS = {
    "急性心筋梗塞": ["acute myocardial infarction", "ami", "stemi", "心筋梗塞", "急性心筋梗塞"],
    "anterior stemi": ["前壁stemi", "前壁心筋梗塞", "anterior stemi", "anterior mi"],
    "inferior stemi": ["下壁stemi", "下壁心筋梗塞", "inferior stemi", "inferior mi"],
    "右室梗塞": ["右室梗塞", "rv infarction", "right ventricular infarction"],
    "心房細動": ["心房細動", "atrial fibrillation", "af", "afib", "新規発症心房細動", "持続性心房細動"],
    "肺塞栓症": ["肺塞栓症", "肺血栓塞栓症", "pulmonary embolism", "pe", "肺塞栓"],
    "massive pe": ["massive pe", "massive pulmonary embolism", "高リスクpe"],
    "submassive pe": ["submassive pe", "中リスクpe", "intermediate-high risk pe", "intermediate-risk pe"],
    "急性大動脈解離": ["急性大動脈解離", "大動脈解離", "aortic dissection", "ad"],
    "stanford a": ["stanford a", "type a", "a 型解離", "上行大動脈解離"],
    "stanford b": ["stanford b", "type b", "b 型解離", "下行大動脈解離"],
    "慢性心不全": ["慢性心不全", "chronic heart failure", "chf"],
    "急性心不全": ["急性心不全", "acute heart failure", "ahf", "急性増悪"],
    "hfref": ["hfref", "heart failure with reduced ef", "lvef 低下型心不全"],
    "hfpef": ["hfpef", "heart failure with preserved ef", "lvef 保持型心不全"],
    "拡張型心筋症": ["拡張型心筋症", "dcm", "dilated cardiomyopathy"],
    "冠攣縮性狭心症": ["冠攣縮性狭心症", "vsa", "vasospastic angina", "variant angina", "プリンツメタル狭心症"],
    "大動脈弁狭窄症": ["大動脈弁狭窄症", "as", "aortic stenosis", "severe as"],
    "労作性狭心症": ["労作性狭心症", "安定狭心症", "stable angina", "effort angina"],
    "無痛性虚血": ["無痛性虚血", "silent ischemia", "silent myocardial ischemia"],
    "心アミロイドーシス": ["心アミロイドーシス", "cardiac amyloidosis", "ca", "amyloid heart"],
    "attr-ca": ["attr-ca", "attr 心アミロイドーシス", "transthyretin amyloidosis", "野生型 attr"],
    "attrv": ["attrv", "遺伝性 attr", "hereditary attr", "ttr val30met"],
    "たこつぼ心筋症": ["たこつぼ心筋症", "takotsubo", "ストレス心筋症", "apical ballooning"],
    "身体表現性障害": [
        "身体表現性障害", "somatoform disorder", "somatic symptom disorder",
        "ssd", "身体症状症", "非心臓性胸痛", "nccp", "non-cardiac chest pain",
    ],
    "killip ii": ["killip ii", "killip 2", "killip 分類 ii"],
    "killip i": ["killip i", "killip 1", "killip 分類 i"],
}


def _build_reverse_index() -> Dict[str, str]:
    idx = {}
    for canonical, syns in DIAGNOSIS_SYNONYMS.items():
        idx[canonical.lower()] = canonical
        for s in syns:
            idx[s.lower()] = canonical
    return idx


_REVERSE_IDX = _build_reverse_index()


def extract_diagnoses(text: str) -> Set[str]:
    if not text:
        return set()
    text_lower = text.lower()
    found = set()
    for syn, canonical in _REVERSE_IDX.items():
        if syn in text_lower:
            found.add(canonical)
    return found


def normalize_keyfacts_diagnoses(diag_list: List[str]) -> Set[str]:
    norm = set()
    for entry in diag_list or []:
        entry_lower = entry.lower()
        matched = False
        for syn, canonical in _REVERSE_IDX.items():
            if syn in entry_lower:
                norm.add(canonical)
                matched = True
        if not matched:
            # Keep raw lowercase as canonical if no synonym hits
            norm.add(entry_lower.strip())
    return norm


def compute_diagnosis_f1(generated_text: str, gold_diagnoses: Set[str]) -> Dict:
    pred = extract_diagnoses(generated_text)
    # Filter gold to dictionary-known terms (others already canonicalized in normalize)
    gold = gold_diagnoses

    if not gold:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0, "predicted": sorted(pred), "gold": []}

    tp = pred & gold
    fp = pred - gold
    fn = gold - pred

    p = len(tp) / len(pred) if pred else 0.0
    r = len(tp) / len(gold)
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return {
        "precision": round(p, 3),
        "recall": round(r, 3),
        "f1": round(f1, 3),
        "tp": len(tp),
        "fp": len(fp),
        "fn": len(fn),
        "predicted": sorted(pred),
        "gold": sorted(gold),
        "missing": sorted(fn),
    }
