"""
SOAP parser — Python port of /home/junkanki/naka/emr/backend/internal/slm/parser.go.

Parses SLM-generated free text into S/O/A/P sections. Handles the bulk of
real-world SLM output formatting variations seen in production logs.
"""
import re
from typing import Dict


_SKIP_HEADER_PREFIXES = (
    "■ SOAP", "■ 【SOAP", "■ カルテ記載", "■ 電子カルテ", "■ 診療記録", "■ 医療記録",
)

# Markers ordered longest-first; first to match for a line wins.
_SECTION_MARKERS = [
    # 【】 + ダッシュ付きラベル (with closing bracket variations)
    ("S", "■ 【S - Subjective】"), ("O", "■ 【O - Objective】"),
    ("A", "■ 【A - Assessment】"), ("P", "■ 【P - Plan】"),
    ("S", "【S - Subjective】"), ("O", "【O - Objective】"),
    ("A", "【A - Assessment】"), ("P", "【P - Plan】"),
    # ダッシュ付きラベル (no closing bracket — handles parenthetical extra text)
    ("S", "【S - Subjective"), ("O", "【O - Objective"),
    ("A", "【A - Assessment"), ("P", "【P - Plan"),
    ("S", "【S -Subjective"), ("O", "【O -Objective"),
    ("A", "【A -Assessment"), ("P", "【P -Plan"),
    ("S", "【S- Subjective"), ("O", "【O- Objective"),
    ("A", "【A- Assessment"), ("P", "【P- Plan"),
    # 半角コロン + ラベル付き (e.g. 【S: 主訴・現病歴】)
    ("S", "【S:"), ("O", "【O:"), ("A", "【A:"), ("P", "【P:"),
    ("S", "■ 【S】"), ("O", "■ 【O】"), ("A", "■ 【A】"), ("P", "■ 【P】"),
    ("S", "■ 【S："), ("O", "■ 【O："), ("A", "■ 【A："), ("P", "■ 【P："),
    ("S", "■ 【S:"), ("O", "■ 【O:"), ("A", "■ 【A:"), ("P", "■ 【P:"),
    # cleaned 出力
    ("S", "■ S (Subjective)"), ("O", "■ O (Objective)"),
    ("A", "■ A (Assessment)"), ("P", "■ P (Plan)"),
    ("S", "■ S（主観的情報）"), ("O", "■ O（客観的情報）"),
    ("A", "■ A（評価）"), ("P", "■ P（計画）"),
    ("S", "■ S:"), ("O", "■ O:"), ("A", "■ A:"), ("P", "■ P:"),
    ("S", "■ S："), ("O", "■ O："), ("A", "■ A："), ("P", "■ P："),
    # 英語フル表記
    ("S", "S (Subjective)"), ("O", "O (Objective)"),
    ("A", "A (Assessment)"), ("P", "P (Plan)"),
    # 太字 + 日本語
    ("S", "**S（主観的情報）**"), ("O", "**O（客観的情報）**"),
    ("A", "**A（評価）**"), ("P", "**P（計画）**"),
    # 太字
    ("S", "**S**:"), ("O", "**O**:"), ("A", "**A**:"), ("P", "**P**:"),
    ("S", "**S**"), ("O", "**O**"), ("A", "**A**"), ("P", "**P**"),
    # 【】
    ("S", "【S】"), ("O", "【O】"), ("A", "【A】"), ("P", "【P】"),
    ("S", "【S："), ("O", "【O："), ("A", "【A："), ("P", "【P："),
    # 日本語ラベル
    ("S", "S（主観的情報）:"), ("O", "O（客観的情報）:"),
    ("A", "A（評価）:"), ("P", "P（計画）:"),
    ("S", "S（主観的情報）"), ("O", "O（客観的情報）"),
    ("A", "A（評価）"), ("P", "P（計画）"),
]

# Bare letter markers — matched on whole-line equality, not prefix
_BARE_MARKERS = {
    "S:": "S", "S：": "S", "■ S": "S",
    "O:": "O", "O：": "O", "■ O": "O",
    "A:": "A", "A：": "A", "■ A": "A",
    "P:": "P", "P：": "P", "■ P": "P",
}


def parse_soap(text: str) -> Dict[str, str]:
    """Return dict with keys S, O, A, P (empty string if not found)."""
    # Strip <think>...</think> if present
    if "</think>" in text:
        text = text.split("</think>", 1)[1].lstrip()

    # Mirror production cleanModelOutput: strip ** bold markers so that
    # `**【S - Subjective】**` becomes `【S - Subjective】` for marker matching.
    # Also strip `## ` headings.
    text = re.sub(r"\*\*", "", text)
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)

    lines = text.split("\n")
    sections = {"S": [], "O": [], "A": [], "P": []}
    current = None

    for line in lines:
        trimmed = line.strip()

        # Skip lines that are SOAP "header" lines like "■ SOAP 形式..."
        if any(trimmed.startswith(h) for h in _SKIP_HEADER_PREFIXES):
            continue

        # Try bare marker (whole-line equality)
        if trimmed in _BARE_MARKERS:
            current = _BARE_MARKERS[trimmed]
            continue

        # Try long markers (longest first)
        matched = None
        for sec, marker in _SECTION_MARKERS:
            if trimmed.startswith(marker):
                matched = sec
                content = trimmed[len(marker):].lstrip(" :：　")
                if content:
                    sections[sec].append(content)
                break
        if matched:
            current = matched
            continue

        # Otherwise, append to current section
        if current and trimmed:
            sections[current].append(trimmed)
        elif current and not trimmed:
            sections[current].append("")  # preserve blank line

    return {k: _normalize("\n".join(v)).strip() for k, v in sections.items()}


def _normalize(s: str) -> str:
    """Light cleanup mirroring production cleanModelOutput."""
    # Remove leading **, ##, ###, etc.
    s = re.sub(r"^\s*\*\*\s*", "", s, flags=re.MULTILINE)
    s = re.sub(r"^\s*#+\s*", "", s, flags=re.MULTILINE)
    # Collapse 3+ blank lines
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s
