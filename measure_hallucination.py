#!/usr/bin/env python3
"""
ハルシネーション定量計測スクリプト

推論結果ファイル（results/, results_phase2/）を解析し、
モデルごとのハルシネーション率を定量的に計測する。

計測手法:
  1. 薬剤名検証: 既知の薬剤辞書との照合
  2. 検査値検証: 臨床的にあり得ない値の検出
  3. 文字化け/捏造検出: 非日本語・非英語の異常文字列
  4. (オプション) LLM評価: Claude APIによる医学的正確性評価

Usage:
  python3 measure_hallucination.py --results_dir results/ results_phase2/
  python3 measure_hallucination.py --results_dir results/ --verbose
  python3 measure_hallucination.py --results_dir results_phase2/ --llm  # Claude API使用
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

# ==============================================================================
# 1. 薬剤名辞書（一般名 + 主要商品名）
#    厚労省薬価基準収載品目ベース、主要な処方薬を網羅
# ==============================================================================
KNOWN_DRUGS = {
    # --- 降圧薬 ---
    "アムロジピン", "ニフェジピン", "アゼルニジピン", "シルニジピン", "ベニジピン",
    "エナラプリル", "リシノプリル", "ペリンドプリル", "イミダプリル", "テモカプリル",
    "カンデサルタン", "バルサルタン", "テルミサルタン", "オルメサルタン", "イルベサルタン", "アジルサルタン", "ロサルタン",
    "サクビトリルバルサルタン", "エンレスト",
    "ビソプロロール", "カルベジロール", "メトプロロール", "アテノロール", "プロプラノロール", "ネビボロール",
    "ヒドロクロロチアジド", "トリクロルメチアジド", "インダパミド",
    "スピロノラクトン", "エプレレノン", "エサキセレノン", "フィネレノン",
    "ドキサゾシン", "プラゾシン",
    # --- 糖尿病治療薬 ---
    "メトホルミン", "グリメピリド", "グリクラジド", "グリベンクラミド",
    "シタグリプチン", "ビルダグリプチン", "アログリプチン", "リナグリプチン", "テネリグリプチン", "サキサグリプチン", "トレラグリプチン",
    "エンパグリフロジン", "ダパグリフロジン", "カナグリフロジン", "イプラグリフロジン", "トホグリフロジン", "ルセオグリフロジン",
    "ピオグリタゾン",
    "リラグルチド", "セマグルチド", "デュラグルチド", "エキセナチド", "リキシセナチド",
    "チルゼパチド",
    "ミグリトール", "ボグリボース", "アカルボース",
    "インスリンリスプロ", "インスリンアスパルト", "インスリングルリジン",
    "インスリングラルギン", "インスリンデグルデク", "インスリンデテミル",
    "レパグリニド", "ナテグリニド", "ミチグリニド",
    # --- 脂質異常症 ---
    "ロスバスタチン", "アトルバスタチン", "ピタバスタチン", "プラバスタチン", "シンバスタチン", "フルバスタチン",
    "エゼチミブ", "フェノフィブラート", "ベザフィブラート", "ペマフィブラート",
    "エボロクマブ", "アリロクマブ",
    "イコサペント酸エチル", "EPA",
    # --- 抗血小板・抗凝固 ---
    "アスピリン", "クロピドグレル", "プラスグレル", "チカグレロル", "シロスタゾール",
    "ワルファリン", "ダビガトラン", "リバーロキサバン", "アピキサバン", "エドキサバン",
    "ヘパリン", "エノキサパリン", "フォンダパリヌクス",
    # --- 循環器その他 ---
    "フロセミド", "トルバプタン", "アゾセミド", "トラセミド", "ブメタニド",
    "ジゴキシン", "アミオダロン", "フレカイニド", "ピルシカイニド", "ソタロール", "ベラパミル", "ジルチアゼム",
    "ニトログリセリン", "硝酸イソソルビド", "ニコランジル",
    "カルペリチド", "ミルリノン", "ドブタミン", "ドパミン", "ノルアドレナリン", "アドレナリン",
    "ランジオロール",
    # --- 呼吸器 ---
    "サルブタモール", "プロカテロール", "ホルモテロール", "サルメテロール", "インダカテロール", "ビランテロール", "オロダテロール",
    "チオトロピウム", "グリコピロニウム", "ウメクリジニウム", "アクリジニウム",
    "ブデソニド", "フルチカゾン", "モメタゾン", "シクレソニド", "ベクロメタゾン",
    "モンテルカスト", "プランルカスト",
    "テオフィリン", "アミノフィリン",
    "デキストロメトルファン", "コデイン",
    "カルボシステイン", "アンブロキソール", "ブロムヘキシン",
    # --- 抗菌薬 ---
    "アモキシシリン", "アンピシリン", "ピペラシリン", "ピペラシリンタゾバクタム",
    "セファゾリン", "セフトリアキソン", "セフォタキシム", "セフェピム", "セフメタゾール", "セフジニル", "セフカペン", "セフジトレン",
    "メロペネム", "イミペネム", "ドリペネム",
    "アジスロマイシン", "クラリスロマイシン", "エリスロマイシン",
    "レボフロキサシン", "モキシフロキサシン", "シプロフロキサシン",
    "バンコマイシン", "テイコプラニン", "リネゾリド", "ダプトマイシン",
    "クリンダマイシン", "メトロニダゾール",
    "スルファメトキサゾール・トリメトプリム", "ST合剤",
    "ミノサイクリン", "ドキシサイクリン",
    "ゲンタマイシン", "アミカシン", "トブラマイシン",
    # --- 消化器 ---
    "オメプラゾール", "ランソプラゾール", "ラベプラゾール", "エソメプラゾール", "ボノプラザン",
    "ファモチジン", "ラニチジン", "ニザチジン",
    "スクラルファート", "レバミピド", "テプレノン", "ミソプロストール",
    "メサラジン", "サラゾスルファピリジン",
    "アザチオプリン", "メルカプトプリン",
    "インフリキシマブ", "アダリムマブ", "ゴリムマブ", "セルトリズマブ", "ウステキヌマブ", "ベドリズマブ",
    "メトクロプラミド", "ドンペリドン", "モサプリド",
    "センノシド", "酸化マグネシウム", "ルビプロストン", "リナクロチド", "エロビキシバット", "ラクツロース", "ナルデメジン",
    # --- 精神科・神経 ---
    "エスシタロプラム", "セルトラリン", "パロキセチン", "フルボキサミン",
    "デュロキセチン", "ベンラファキシン", "ミルナシプラン",
    "ミルタザピン", "トラゾドン", "アミトリプチリン", "ノルトリプチリン", "クロミプラミン",
    "アリピプラゾール", "オランザピン", "クエチアピン", "リスペリドン", "ブレクスピプラゾール", "パリペリドン",
    "バルプロ酸", "カルバマゼピン", "ラモトリギン", "レベチラセタム", "ラコサミド",
    "リチウム",
    "ゾルピデム", "エスゾピクロン", "スボレキサント", "レンボレキサント", "ラメルテオン",
    "ロラゼパム", "ジアゼパム", "クロナゼパム", "エチゾラム", "アルプラゾラム", "ブロマゼパム", "ニトラゼパム", "フルニトラゼパム", "トリアゾラム",
    "ドネペジル", "ガランタミン", "リバスチグミン", "メマンチン",
    "レボドパ", "カルビドパ", "ベンセラジド", "エンタカポン", "オピカポン",
    "プラミペキソール", "ロピニロール", "ロチゴチン", "アポモルヒネ",
    "セレギリン", "ラサギリン", "サフィナミド",
    "ゾニサミド", "イストラデフィリン", "アマンタジン", "ドロキシドパ",
    "スマトリプタン", "リザトリプタン", "エレトリプタン", "ゾルミトリプタン",
    "ラスミジタン", "ガルカネズマブ", "フレマネズマブ", "エレヌマブ",
    "ロメリジン", "バルプロ酸",
    # --- 整形・疼痛 ---
    "ロキソプロフェン", "ジクロフェナク", "セレコキシブ", "メロキシカム", "ナプロキセン", "インドメタシン", "エトドラク",
    "アセトアミノフェン",
    "トラマドール", "トラマドール・アセトアミノフェン配合", "ブプレノルフィン", "フェンタニル", "モルヒネ", "オキシコドン", "ヒドロモルフォン", "タペンタドール",
    "プレガバリン", "ミロガバリン", "ガバペンチン",
    "メトトレキサート", "MTX",
    "レフルノミド", "イグラチモド", "サラゾスルファピリジン", "ブシラミン", "タクロリムス",
    "エタネルセプト", "トシリズマブ", "アバタセプト", "サリルマブ", "バリシチニブ", "トファシチニブ", "ウパダシチニブ", "フィルゴチニブ", "ペフィシチニブ",
    "デノスマブ", "テリパラチド", "ロモソズマブ", "アレンドロネート", "リセドロネート", "ミノドロン酸", "ゾレドロン酸", "イバンドロネート",
    "エルデカルシトール", "アルファカルシドール",
    "ヒアルロン酸",
    "コルヒチン", "フェブキソスタット", "アロプリノール", "トピロキソスタット", "ベンズブロマロン", "ドチヌラド",
    # --- 腎臓・内分泌 ---
    "チラーヂン", "レボチロキシン", "リオチロニン",
    "チアマゾール", "プロピルチオウラシル",
    "ダルベポエチン", "エポエチン", "ロキサデュスタット", "バダデュスタット", "エナロデュスタット",
    "セベラマー", "炭�ite カルシウム", "ランタン", "スクロオキシ水酸化鉄", "クエン酸第二鉄",
    "カルシトリオール", "マキサカルシトール", "シナカルセト", "エボカルセト", "エテルカルセチド",
    "カリメート", "ジルコニウムシクロケイ酸ナトリウム",
    "トルバプタン",
    # --- ステロイド ---
    "プレドニゾロン", "メチルプレドニゾロン", "デキサメタゾン", "ベタメタゾン", "ヒドロコルチゾン",
    # --- その他頻用 ---
    "ヘパリン", "ワルファリン",
    # 追加（偽陽性修正）
    "シクロホスファミド", "Cyclophosphamide", "cyclophosphamide",
    "リツキシマブ", "イバブラジン", "ナファモスタット",
    "フルティフォーム",  # ICS/LABA配合剤
    "イプラトロピウム",  # 抗コリン吸入薬
    "ガスター", "タケプロン", "タケキャブ", "ネキシウム",
    "ムコスタ", "セルベックス",
    "ノルバスク", "ブロプレス", "ミカルディス", "ディオバン",
    "メトグルコ", "ジャヌビア", "フォシーガ", "ジャディアンス",
    "クレストール", "リピトール",
    "プラビックス", "エリキュース", "イグザレルト", "リクシアナ",
    "リリカ", "タリージェ", "トラムセット", "サインバルタ",
}

# 一部パターンマッチで許容する薬剤名の部分文字列
DRUG_FRAGMENTS = {
    "インスリン", "ステロイド", "抗菌薬", "抗生物質", "抗生剤", "利尿薬", "利尿剤",
    "降圧薬", "降圧剤", "吸入薬", "吸入ステロイド", "点滴", "注射",
    "β遮断薬", "ACE阻害薬", "ARB", "CCB", "DPP-4阻害薬", "SGLT2阻害薬", "GLP-1",
    "PPI", "H2ブロッカー", "NSAIDs", "NSAID", "ICS", "LABA", "LAMA",
    "bDMARDs", "csDMARDs", "JAK阻害薬",
    "IVIg", "免疫グロブリン", "血漿交換",
}

# ==============================================================================
# 2. 検査値の正常範囲（異常値検出用）
# ==============================================================================
LAB_RANGES = {
    # (パターン, 単位パターン, 最小あり得る値, 最大あり得る値)
    "BNP": (r"BNP\s*[\d,.]+\s*(?:pg/mL)?", 0, 50000),
    "NT-proBNP": (r"NT-proBNP\s*[\d,.]+", 0, 100000),
    "HbA1c": (r"HbA1c\s*[\d.]+\s*%?", 3.0, 20.0),
    "eGFR": (r"eGFR\s*[\d.]+", 0, 200),
    "Cr": (r"Cr\s*[\d.]+\s*(?:mg/dL)?", 0.1, 30.0),
    "CRP": (r"CRP\s*[\d.]+\s*(?:mg/dL)?", 0, 50.0),
    "WBC": (r"WBC\s*[\d,]+(?:/μL)?", 500, 200000),
    "Hb": (r"Hb\s*[\d.]+\s*(?:g/dL)?", 2.0, 25.0),
    "Plt": (r"Plt\s*[\d.]+\s*(?:万)?", 0.1, 200),
    "AST": (r"AST\s*[\d]+\s*(?:U/L)?", 1, 10000),
    "ALT": (r"ALT\s*[\d]+\s*(?:U/L)?", 1, 10000),
    "Na": (r"Na\s*[\d]+\s*(?:mEq/L)?", 100, 180),
    "K": (r"K\s*[\d.]+\s*(?:mEq/L)?", 1.0, 10.0),
    "EF": (r"(?:EF|LVEF)\s*[\d]+\s*%?", 5, 85),
    "SpO2": (r"SpO2\s*[\d]+\s*%?", 50, 100),
    "BP_sys": (r"BP\s*(\d+)/\d+", 40, 300),
    "BP_dia": (r"BP\s*\d+/(\d+)", 20, 200),
    "HR": (r"HR\s*[\d]+\s*(?:bpm)?", 20, 300),
}

# ==============================================================================
# 3. 捏造パターン検出
# ==============================================================================
# 既知の捏造用語（evaluation_sheet_claude.txtで特定済み）
KNOWN_FABRICATIONS = [
    "Pankštaj", "インシデント型", "ネブライザー様糖尿病",
    "エフォシトキシン", "アジスフロキサシン", "LDPLL", "SPC",
    "オドキサバン", "LacRQ", "相対的濾過率（PoR）",
    "クローヌスクリーニング", "抗水晶体薬", "CRP-Ag",
    "炎性細胞浸潤型AIR", "pMM", "無菌性免疫療法",
]

# 文字化け・非意図的文字列のパターン
GARBLED_PATTERNS = [
    r"[ěščřžýáíéůúóďťň]{2,}",     # チェコ語等の文字が混入
    r"[àâäãåæ]{2,}",               # 北欧文字の連続
    r"[^\x00-\x7F\u3000-\u9FFF\uF900-\uFAFF\u30A0-\u30FF\u3040-\u309F\uFF00-\uFFEF]{3,}",  # 日本語・英語以外の連続
    r"(?<![A-Z])[A-Z]{6,}(?![A-Z])",  # 6文字以上の不明な大文字略語（APACHE,TRACP等の医療略語を除外するため閾値を上げる）
]


# ==============================================================================
# 解析関数
# ==============================================================================

def parse_results_file(filepath):
    """推論結果ファイルをパースして、モデル名→出力テキストの辞書を返す"""
    models = {}
    current_model = None
    current_text = []
    prompt_id = None
    category = None
    prompt_text = None

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")

            if line.startswith("Prompt ID:"):
                prompt_id = line.split(":", 1)[1].strip()
            elif line.startswith("Category:"):
                category = line.split(":", 1)[1].strip()
            elif line.startswith("Prompt:"):
                prompt_text = line.split(":", 1)[1].strip()
            elif line.startswith("--- ") and line.endswith(" ---"):
                if current_model and current_text:
                    models[current_model] = "\n".join(current_text).strip()
                current_model = line.strip("- ")
                current_text = []
            elif line.startswith("=" * 10):
                if current_model and current_text:
                    models[current_model] = "\n".join(current_text).strip()
                    current_model = None
                    current_text = []
            else:
                if current_model:
                    current_text.append(line)

    if current_model and current_text:
        models[current_model] = "\n".join(current_text).strip()

    return prompt_id, category, prompt_text, models


def parse_phase2_file(filepath):
    """Phase2結果ファイルをパースして、プロンプト→出力テキストの辞書を返す"""
    results = {}
    current_prompt = None
    current_text = []
    model_name = None

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("Model:"):
                model_name = line.split(":", 1)[1].strip()
            elif line.startswith("--- ") and line.endswith(" ---"):
                if current_prompt and current_text:
                    results[current_prompt] = "\n".join(current_text).strip()
                current_prompt = line.strip("- ")
                current_text = []
            elif line.startswith("Prompt:"):
                pass  # skip prompt line
            elif line.startswith("=" * 10) or line.startswith("Path:"):
                if current_prompt and current_text:
                    results[current_prompt] = "\n".join(current_text).strip()
                    current_prompt = None
                    current_text = []
            else:
                if current_prompt:
                    current_text.append(line)

    if current_prompt and current_text:
        results[current_prompt] = "\n".join(current_text).strip()

    return model_name, results


def extract_drug_like_names(text):
    """テキストから薬剤名らしき文字列を高精度で抽出

    薬剤名特有の語尾パターンに限定して抽出することで偽陽性を低減。
    一般的なカタカナ語（アルブミン、サイトカイン等）は対象外。
    """
    candidates = set()

    # 薬剤名特有の語尾パターン（カタカナ）
    # -プリル(ACEi), -サルタン(ARB), -ジピン(CCB), -ロール(βB),
    # -スタチン(statin), -グリフロジン(SGLT2i), -グリプチン(DPP4i),
    # -チド(GLP1), -マブ(抗体), -チニブ(kinase), -プラゾール(PPI),
    # -マイシン(抗菌), -シリン(ペニシリン), -キサシン(quinolone),
    # -フェナク(NSAID), -プロフェン(NSAID), -ゾラム(BZD),
    # -ピデム(Z-drug), -セトロン(5HT3), -プラミン(TCA)
    drug_suffix_pattern = (
        r"[ァ-ヴー]{2,}"
        r"(?:プリル|サルタン|ジピン|ロロール|プロロール|スタチン|フロジン|グリプチン|"
        r"グルチド|ルチド|パチド|セチド|マブ|ズマブ|ニブ|チニブ|プラゾール|ラゾール|"
        r"マイシン|シリン|キサシン|フェナク|プロフェン|コキシブ|ゾラム|ピデム|クロン|"
        r"セトロン|プラミン|パリン|キサバン|ガトラン|ファリン|"
        r"ニジン|リドン|ザピン|ラジン|ピラゾール|リチド|"
        r"ゾリド|プチン|ルビシン|フォスファミド|"
        r"フロキサシン|トレキサート|ペネム|セファム|"
        r"スタット|ブロマロン|プリノール|ロキソスタット)"
    )
    for match in re.finditer(drug_suffix_pattern, text):
        candidates.add(match.group())

    # 英語の薬剤名パターン（語尾ベース）
    eng_drug_pattern = (
        r"\b[A-Z][a-z]+"
        r"(?:pril|sartan|dipine|olol|statin|flozin|gliptin|glutide|"
        r"mab|zumab|nib|tinib|prazole|mycin|cillin|floxacin|"
        r"fenac|profen|coxib|azepam|pidem|setron|pramine|"
        r"parin|xaban|gatran|farin|done|pine|zole|mide|amide)\b"
    )
    for match in re.finditer(eng_drug_pattern, text):
        candidates.add(match.group())

    return candidates


def check_drug_hallucinations(text):
    """薬剤名のハルシネーションを検出（高精度版）

    薬剤名らしき語尾パターンを持つ単語のみ抽出し、
    既知薬剤辞書にない場合にハルシネーションとして報告。
    """
    hallucinations = []
    candidates = extract_drug_like_names(text)

    for candidate in candidates:
        # 既知の薬剤辞書に完全一致
        if candidate in KNOWN_DRUGS:
            continue
        # 部分一致チェック（辞書の薬剤名がcandidateに含まれる）
        if any(drug in candidate for drug in KNOWN_DRUGS if len(drug) >= 4):
            continue
        # candidateが辞書の薬剤名の部分文字列
        if any(candidate in drug for drug in KNOWN_DRUGS if len(candidate) >= 4):
            continue
        # 薬剤カテゴリ名への部分一致
        if any(frag in candidate for frag in DRUG_FRAGMENTS):
            continue
        # ここまで通過 = 未知の薬剤名パターン → ハルシネーション疑い
        hallucinations.append(candidate)

    return hallucinations


def check_fabricated_terms(text):
    """既知の捏造用語を検出"""
    found = []
    for term in KNOWN_FABRICATIONS:
        if term in text:
            found.append(term)
    return found


def check_garbled_text(text):
    """文字化け・異常文字列を検出"""
    found = []
    for pattern in GARBLED_PATTERNS:
        matches = re.findall(pattern, text)
        for m in matches:
            if len(m) >= 2:
                found.append(m)
    return found


def check_lab_values(text):
    """臨床的にあり得ない検査値を検出"""
    anomalies = []

    # 数値付きの検査値を抽出して範囲チェック
    patterns = {
        "HbA1c": (r"HbA1c\s*([\d.]+)", 3.0, 20.0),
        "eGFR": (r"eGFR\s*([\d.]+)", 0, 200),
        "Cr": (r"Cr\s*([\d.]+)", 0.1, 30.0),
        "CRP": (r"CRP\s*([\d.]+)", 0, 100.0),
        "BNP": (r"BNP\s*([\d,]+)", 0, 50000),
        "EF": (r"(?:EF|LVEF)\s*([\d]+)", 5, 85),
        "SpO2": (r"SpO2\s*([\d]+)", 50, 100),
        "K": (r"[^A-Za-z]K\s*([\d.]+)\s*(?:mEq|mmol)", 1.0, 10.0),
        "Na": (r"Na\s*([\d]+)\s*(?:mEq|mmol)", 100, 180),
    }

    for name, (pattern, min_val, max_val) in patterns.items():
        for match in re.finditer(pattern, text):
            try:
                val = float(match.group(1).replace(",", ""))
                if val < min_val or val > max_val:
                    anomalies.append(f"{name}={val} (range: {min_val}-{max_val})")
            except ValueError:
                pass

    # カルペリチド用量チェック（μg/kg/minが正常、mg/kgは異常）
    if "カルペリチド" in text:
        if re.search(r"カルペリチド\s*\d+\s*mg", text):
            anomalies.append("カルペリチド用量異常（mg単位、正常はμg/kg/min）")

    return anomalies


def analyze_text(text):
    """テキストの全ハルシネーション指標を計測"""
    results = {
        "drug_hallucinations": check_drug_hallucinations(text),
        "fabricated_terms": check_fabricated_terms(text),
        "garbled_text": check_garbled_text(text),
        "lab_anomalies": check_lab_values(text),
    }
    results["total_issues"] = sum(len(v) for v in results.values())
    return results


# ==============================================================================
# LLM評価（オプション、Claude API使用）
# ==============================================================================

LLM_EVAL_PROMPT = """あなたは医療情報の正確性を評価する専門家です。
以下のモデル出力テキストに含まれるハルシネーション（事実と異なる情報）を全て列挙してください。

## 評価カテゴリ:
1. **捏造薬剤名**: 実在しない薬剤名
2. **誤った用量**: 実在する薬剤だが用量が臨床的にあり得ない
3. **捏造医学用語**: 実在しない医学用語・疾患名
4. **誤った医学的事実**: 疾患の病態・診断基準・治療方針の誤り
5. **捏造引用**: 実在しない著者名・論文・ガイドライン
6. **文脈的矛盾**: 提示された症例情報と矛盾する記述

## プロンプト:
{prompt}

## モデル出力:
{output}

## 出力形式（JSON）:
{{
  "hallucinations": [
    {{"category": "カテゴリ名", "text": "該当箇所の引用", "explanation": "何が間違いか"}}
  ],
  "total_count": 数値,
  "severity": "low/medium/high/critical"
}}
"""


def llm_evaluate(prompt, output, model="claude-sonnet-4-20250514"):
    """Claude APIでハルシネーション評価（要 anthropic パッケージ）"""
    try:
        import anthropic
    except ImportError:
        print("Error: pip install anthropic が必要です", file=sys.stderr)
        return None

    client = anthropic.Anthropic()
    message = client.messages.create(
        model=model,
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": LLM_EVAL_PROMPT.format(prompt=prompt, output=output)
        }]
    )
    try:
        # レスポンスからJSON部分を抽出
        text = message.content[0].text
        json_match = re.search(r"\{[\s\S]*\}", text)
        if json_match:
            return json.loads(json_match.group())
    except (json.JSONDecodeError, IndexError):
        pass
    return {"raw_response": message.content[0].text}


# ==============================================================================
# メイン処理
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="ハルシネーション定量計測")
    parser.add_argument("--results_dir", nargs="+", default=["results", "results_phase2"],
                        help="結果ディレクトリ（複数指定可）")
    parser.add_argument("--verbose", "-v", action="store_true", help="詳細出力")
    parser.add_argument("--llm", action="store_true", help="Claude APIによるLLM評価も実行")
    parser.add_argument("--output", "-o", default=None, help="結果をJSONファイルに保存")
    args = parser.parse_args()

    all_results = {}  # model_name -> {prompt_id -> analysis}
    model_summaries = defaultdict(lambda: defaultdict(int))

    for results_dir in args.results_dir:
        if not os.path.exists(results_dir):
            print(f"Warning: {results_dir} not found, skipping")
            continue

        for filename in sorted(os.listdir(results_dir)):
            if not filename.endswith(".txt"):
                continue
            filepath = os.path.join(results_dir, filename)

            if results_dir == "results":
                # Phase1: 1ファイルに複数モデルの結果
                prompt_id, category, prompt_text, models = parse_results_file(filepath)
                for model_name, output_text in models.items():
                    if model_name not in all_results:
                        all_results[model_name] = {}
                    analysis = analyze_text(output_text)
                    all_results[model_name][prompt_id] = {
                        "category": category,
                        "analysis": analysis,
                        "text_length": len(output_text),
                    }
                    for key in ["drug_hallucinations", "fabricated_terms", "garbled_text", "lab_anomalies"]:
                        model_summaries[model_name][key] += len(analysis[key])
                    model_summaries[model_name]["total_issues"] += analysis["total_issues"]
                    model_summaries[model_name]["total_outputs"] += 1

                    if args.verbose and analysis["total_issues"] > 0:
                        print(f"\n[{model_name}] {prompt_id} ({category})")
                        for key, items in analysis.items():
                            if isinstance(items, list) and items:
                                print(f"  {key}: {items}")

            else:
                # Phase2: 1ファイル1モデル
                model_name, outputs = parse_phase2_file(filepath)
                if model_name is None:
                    model_name = filename.replace(".txt", "")
                if model_name not in all_results:
                    all_results[model_name] = {}

                for prompt_id, output_text in outputs.items():
                    analysis = analyze_text(output_text)
                    all_results[model_name][prompt_id] = {
                        "analysis": analysis,
                        "text_length": len(output_text),
                    }
                    for key in ["drug_hallucinations", "fabricated_terms", "garbled_text", "lab_anomalies"]:
                        model_summaries[model_name][key] += len(analysis[key])
                    model_summaries[model_name]["total_issues"] += analysis["total_issues"]
                    model_summaries[model_name]["total_outputs"] += 1

                    if args.verbose and analysis["total_issues"] > 0:
                        print(f"\n[{model_name}] {prompt_id}")
                        for key, items in analysis.items():
                            if isinstance(items, list) and items:
                                print(f"  {key}: {items}")

    # ==== サマリー出力 ====
    print("\n" + "=" * 90)
    print("ハルシネーション計測サマリー")
    print("=" * 90)
    print(f"{'モデル':<35} {'出力数':>5} {'薬剤':>5} {'捏造語':>5} {'文字化':>5} {'検査値':>5} {'合計':>5} {'率':>8}")
    print("-" * 90)

    for model_name in sorted(model_summaries.keys()):
        s = model_summaries[model_name]
        n = s["total_outputs"]
        rate = s["total_issues"] / n if n > 0 else 0
        print(f"{model_name:<35} {n:>5} {s['drug_hallucinations']:>5} "
              f"{s['fabricated_terms']:>5} {s['garbled_text']:>5} "
              f"{s['lab_anomalies']:>5} {s['total_issues']:>5} {rate:>7.2f}/出力")

    print("-" * 90)

    # JSON出力
    if args.output:
        output_data = {
            "summaries": {k: dict(v) for k, v in model_summaries.items()},
            "details": {
                model: {
                    pid: {
                        "text_length": data["text_length"],
                        "issues": {
                            k: v for k, v in data["analysis"].items()
                            if isinstance(v, list)
                        },
                        "total_issues": data["analysis"]["total_issues"],
                    }
                    for pid, data in prompts.items()
                }
                for model, prompts in all_results.items()
            }
        }
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        print(f"\n詳細結果を {args.output} に保存しました")


if __name__ == "__main__":
    main()
