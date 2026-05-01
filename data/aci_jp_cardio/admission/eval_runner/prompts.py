"""
Production-mirroring system / user prompts.

Sourced from /home/junkanki/naka/emr/backend/internal/slm/client.go:
- GenerateSOAP @ line 487-495
- GenerateAdmissionSummary @ line 654, 663
- buildPatientHeader (handler/patient_header.go) prepends 【患者情報】 line.
"""
from typing import Optional


def build_patient_header(patient: dict) -> str:
    """Mirror the production buildPatientHeader behavior.

    Production injects: 【患者情報】XX歳 性別\n
    """
    age = patient.get("age", "?")
    gender = patient.get("gender", "")
    return f"【患者情報】{age}歳 {gender}\n"


def assemble_interview(case: dict) -> str:
    """Assemble the SLM input from a case JSON file. Mirrors production."""
    header = build_patient_header(case.get("patient", {}))

    if case["format"] == "voice":
        body = case.get("interview_text_voice", "") or ""
    else:
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
        body = "\n\n".join(parts)

    return header + body


SOAP_SYSTEM_PROMPT = (
    "あなたは日本語の電子カルテ記載を支援する医療AIアシスタントです。"
    "問診情報からSOAP形式のカルテ記載を提案します。"
)

ADMISSION_SYSTEM_PROMPT = (
    "あなたは日本語の電子カルテ記載を支援する医療AIアシスタントです。"
    "詳細な問診・検査情報から入院時サマリを作成します。"
)


def build_soap_messages(interview_text: str, rag_snippet: Optional[str] = None) -> list:
    system = SOAP_SYSTEM_PROMPT
    if rag_snippet:
        system += rag_snippet
    user = interview_text + "\n\n上記の情報から、SOAP形式のカルテ記載を提案してください。"
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def build_admission_messages(interview_text: str, rag_snippet: Optional[str] = None) -> list:
    system = ADMISSION_SYSTEM_PROMPT
    if rag_snippet:
        system += rag_snippet
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": interview_text},
    ]
