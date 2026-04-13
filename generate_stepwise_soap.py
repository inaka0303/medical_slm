"""
段階的SOAPsuggestデータ生成スクリプト

既存の15件の問診→SOAP一括データから、以下を生成:
  1. 段階的suggest: S→O→A→P を1つずつ出力するデータ (15×4=60件)
  2. 途中から続き: S確定済みでOAP出力、SO確定済みでAP出力 等 (15×3=45件)
  3. 元の一括SOAP (15件)

合計: 120件

使い方:
  python3 generate_stepwise_soap.py
"""

import json
import re
import sys

INPUT_FILE = "/home/junkanki/naka/data/sft_data_1.jsonl"
OUTPUT_FILE = "/home/junkanki/naka/data/sft_soap_stepwise.jsonl"

SYSTEM_PROMPT = "あなたは日本語の電子カルテ記載を支援する医療AIアシスタントです。問診情報からカルテ記載を提案します。"


def parse_soap(text):
    """SOAP出力をS, O, A, Pに分割"""
    sections = {}
    # S:, O:, A:, P: で分割（各セクションは次のセクション or 末尾まで）
    pattern = r'(S:|O:|A:|P:)'
    parts = re.split(pattern, text.strip())

    current_key = None
    for part in parts:
        part = part.strip()
        if part in ('S:', 'O:', 'A:', 'P:'):
            current_key = part[0]  # 'S', 'O', 'A', 'P'
        elif current_key:
            sections[current_key] = part.strip()

    return sections


def make_messages(system, user, assistant):
    return {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
            {"role": "assistant", "content": assistant},
        ]
    }


def generate_stepwise_data(soap_items):
    results = []

    for item in soap_items:
        monshin = item["input"]
        full_output = item["output"]
        sections = parse_soap(full_output)

        if not all(k in sections for k in ['S', 'O', 'A', 'P']):
            print(f"  SKIP: SOAP不完全 ({list(sections.keys())})", file=sys.stderr)
            continue

        s_text = sections['S']
        o_text = sections['O']
        a_text = sections['A']
        p_text = sections['P']

        # --- 1. 段階的suggest（各セクション単独出力）---

        # S のみ出力
        results.append(make_messages(
            SYSTEM_PROMPT,
            f"{monshin}\n\n上記の問診記録から、S（主観的情報）を記載してください。",
            f"S: {s_text}"
        ))

        # O のみ出力（S確定済み）
        results.append(make_messages(
            SYSTEM_PROMPT,
            f"{monshin}\n\n【ここまでの記載】\nS: {s_text}\n\n上記に続けて、O（客観的情報）を記載してください。",
            f"O: {o_text}"
        ))

        # A のみ出力（SO確定済み）
        results.append(make_messages(
            SYSTEM_PROMPT,
            f"{monshin}\n\n【ここまでの記載】\nS: {s_text}\n\nO: {o_text}\n\n上記に続けて、A（評価・アセスメント）を記載してください。",
            f"A: {a_text}"
        ))

        # P のみ出力（SOA確定済み）
        results.append(make_messages(
            SYSTEM_PROMPT,
            f"{monshin}\n\n【ここまでの記載】\nS: {s_text}\n\nO: {o_text}\n\nA: {a_text}\n\n上記に続けて、P（計画）を記載してください。",
            f"P: {p_text}"
        ))

        # --- 2. 途中から続き（複数セクションまとめて出力）---

        # OAP まとめて出力（S確定済み）
        results.append(make_messages(
            SYSTEM_PROMPT,
            f"{monshin}\n\n【ここまでの記載】\nS: {s_text}\n\n上記に続けて、O・A・Pを記載してください。",
            f"O: {o_text}\n\nA: {a_text}\n\nP: {p_text}"
        ))

        # AP まとめて出力（SO確定済み）
        results.append(make_messages(
            SYSTEM_PROMPT,
            f"{monshin}\n\n【ここまでの記載】\nS: {s_text}\n\nO: {o_text}\n\n上記に続けて、A・Pを記載してください。",
            f"A: {a_text}\n\nP: {p_text}"
        ))

        # --- 3. 一括SOAP出力 ---
        results.append(make_messages(
            SYSTEM_PROMPT,
            f"{monshin}\n\n上記の問診記録をSOAP形式のカルテに変換してください。",
            f"S: {s_text}\n\nO: {o_text}\n\nA: {a_text}\n\nP: {p_text}"
        ))

        # --- 4. 部分編集（途中まで書いたカルテの続き）---

        # S の前半だけ書いてある → 続きを提案
        s_words = s_text.split('。')
        if len(s_words) >= 2:
            partial_s = s_words[0] + '。'
            results.append(make_messages(
                SYSTEM_PROMPT,
                f"{monshin}\n\n【途中まで記載済み】\nS: {partial_s}\n\nS（主観的情報）の続きを提案してください。",
                f"S: {partial_s}{'。'.join(s_words[1:])}"
            ))

    return results


if __name__ == "__main__":
    with open(INPUT_FILE) as f:
        all_lines = [json.loads(l) for l in f]

    soap_items = [r for r in all_lines if 'SOAP' in r['instruction']]
    print(f"元データ: SOAP {len(soap_items)}件")

    results = generate_stepwise_data(soap_items)
    print(f"生成データ: {len(results)}件")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for item in results:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"保存先: {OUTPUT_FILE}")

    # 内訳
    print(f"\n内訳:")
    print(f"  段階的suggest (S/O/A/P単独): {len(soap_items) * 4}件")
    print(f"  途中から続き (OAP/AP):       {len(soap_items) * 2}件")
    print(f"  一括SOAP:                    {len(soap_items)}件")
    print(f"  部分編集 (S続き):             {len(results) - len(soap_items) * 7}件")
