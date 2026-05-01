"""
Opus-as-judge — generates a JSONL of judging prompts that can be batch-fed to
Claude Code subagents (Opus 4.7). The runner doesn't directly call Anthropic API
to avoid coupling; instead it dumps prompts that an external orchestrator
(this conversation, or a wrapper script) reads and dispatches.

Output format (one line per case per task):
    {"case_id": "...", "task": "soap"|"admission", "prompt": "..."}

The conversation-side handler can then invoke 1 subagent per line, collect the
judging JSON output, and merge back into the eval results via aggregate.py.

5-axis rubric (each 1-5):
  1. medical: 医学的妥当性
  2. completeness: 情報網羅性
  3. naturalness: 日本語自然さ
  4. hallucination: ハルシネーション無さ (5 = no hallucinations)
  5. format: フォーマット遵守 (S/O/A/P が明示的に書かれているか等)
"""
import json
from pathlib import Path
from typing import Dict, List


JUDGE_RUBRIC = """
あなたは日本語の循環器カルテの専門医レビュアーです。生成された SOAP カルテ (もしくは入院時サマリ) を、与えられた reference (正解) と key_facts (薬剤・診断・数値の正解集合) と照らし合わせて 5 軸で評価してください。

各軸 1-5 の整数で採点してください。
1=非常に悪い、2=悪い、3=普通、4=良い、5=非常に良い

## 評価軸

1. **medical** (医学的妥当性): 診断・治療方針が臨床的に妥当か。ガイドライン違反や禁忌薬の誤処方があれば 1-2。
2. **completeness** (情報網羅性): reference や key_facts に含まれる重要情報 (主要診断・薬剤・スコア・処置) を漏らしていないか。漏れが少なければ高得点。
3. **naturalness** (日本語自然さ): カルテとして読みやすい日本語か。冗長・不自然・誤訳的表現があれば減点。
4. **hallucination** (ハルシネーション無さ): 入力にも reference にもない架空の薬名・検査値・診断を生成していないか。1 つでもあれば最大 3 まで、複数あれば 1-2。**5 = 一切なし**。
5. **format** (フォーマット遵守): SOAP の場合は S/O/A/P が明示的に区別されているか。入院時サマリの場合は #1, #2 など問題リスト構造が整っているか。

## 出力形式

必ず以下の JSON だけを返してください。説明文は一切不要。

```json
{
  "medical": 4,
  "completeness": 3,
  "naturalness": 5,
  "hallucination": 4,
  "format": 5,
  "comment": "1-2 文の総評。具体的な問題点があれば指摘。"
}
```
""".strip()


def build_soap_judge_prompt(case: Dict, generated_soap: Dict) -> str:
    ref = case.get("reference_soap") or {}
    kf = case.get("key_facts") or {}

    return f"""{JUDGE_RUBRIC}

---

## 入力された問診 ({case['format']} 形式)

{_format_input(case)}

## 正解 SOAP (reference)

S: {ref.get('S', '')}

O: {ref.get('O', '')}

A: {ref.get('A', '')}

P: {ref.get('P', '')}

## key_facts (正解集合)

- 診断名: {kf.get('diagnoses', [])}
- 開始薬: {kf.get('medications_to_start', [])}
- 継続薬: {kf.get('medications_to_continue', [])}
- 中止薬: {kf.get('medications_to_stop', [])}
- バイタル: {kf.get('vitals', {})}
- スコア: {kf.get('scores', {})}

## 生成された SOAP (評価対象)

S: {generated_soap.get('S', '')}

O: {generated_soap.get('O', '')}

A: {generated_soap.get('A', '')}

P: {generated_soap.get('P', '')}

---

5 軸で採点して JSON だけ返してください。
"""


def build_admission_judge_prompt(case: Dict, generated_admission: str) -> str:
    ref = case.get("reference_admission_summary") or ""
    kf = case.get("key_facts") or {}

    return f"""{JUDGE_RUBRIC}

---

## 入力された問診 ({case['format']} 形式)

{_format_input(case)}

## 正解 入院時サマリ (reference)

{ref}

## key_facts (正解集合)

- 診断名: {kf.get('diagnoses', [])}
- 開始薬: {kf.get('medications_to_start', [])}
- 継続薬: {kf.get('medications_to_continue', [])}
- 中止薬: {kf.get('medications_to_stop', [])}
- バイタル: {kf.get('vitals', {})}
- スコア: {kf.get('scores', {})}

## 生成された 入院時サマリ (評価対象)

{generated_admission}

---

5 軸で採点して JSON だけ返してください。
"""


def _format_input(case: Dict) -> str:
    if case["format"] == "voice":
        return case.get("interview_text_voice") or ""
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


def write_judge_prompts(
    cases: List[Dict],
    soap_outputs: Dict[str, Dict],
    admission_outputs: Dict[str, str],
    out_path: Path,
):
    """Write JSONL of judging prompts. soap_outputs / admission_outputs are
    keyed by encounter_id."""
    n = 0
    with open(out_path, "w", encoding="utf-8") as fp:
        for c in cases:
            eid = c["encounter_id"]
            if eid in soap_outputs:
                fp.write(json.dumps({
                    "case_id": eid,
                    "task": "soap",
                    "prompt": build_soap_judge_prompt(c, soap_outputs[eid]),
                }, ensure_ascii=False) + "\n")
                n += 1
            if eid in admission_outputs and not c.get("is_negative_control"):
                fp.write(json.dumps({
                    "case_id": eid,
                    "task": "admission",
                    "prompt": build_admission_judge_prompt(c, admission_outputs[eid]),
                }, ensure_ascii=False) + "\n")
                n += 1
    return n


def parse_judge_response(text: str) -> Dict:
    """Extract the JSON block from a subagent response."""
    import re
    # Look for JSON inside ```json ... ``` or just bare {...}
    m = re.search(r"```json\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if not m:
        m = re.search(r"(\{[^{]*\"medical\".*?\})", text, flags=re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # Fallback: try the whole thing
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}
