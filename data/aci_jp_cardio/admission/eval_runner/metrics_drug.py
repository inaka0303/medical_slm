"""
Drug name F1 — extracts drug mentions from generated text and compares against
key_facts.medications_to_start + medications_to_continue.

Synonym dictionary covers the most common cardiology drugs (一般名 / 商品名 /
英語表記). Extend as needed.
"""
import re
from typing import Dict, List, Set


# Canonical name → list of synonyms (common names, brand names, English)
DRUG_SYNONYMS: Dict[str, List[str]] = {
    # Antiplatelet
    "アスピリン": ["アスピリン", "バイアスピリン", "バファリン", "aspirin", "ASA"],
    "クロピドグレル": ["クロピドグレル", "プラビックス", "clopidogrel", "Plavix"],
    "プラスグレル": ["プラスグレル", "エフィエント", "prasugrel"],
    "チカグレロル": ["チカグレロル", "ブリリンタ", "ticagrelor"],

    # Anticoagulants
    "ヘパリン": ["ヘパリン", "未分画ヘパリン", "UFH", "heparin"],
    "エノキサパリン": ["エノキサパリン", "クレキサン", "enoxaparin", "Lovenox"],
    "アピキサバン": ["アピキサバン", "エリキュース", "apixaban", "Eliquis"],
    "リバーロキサバン": ["リバーロキサバン", "イグザレルト", "rivaroxaban", "Xarelto"],
    "エドキサバン": ["エドキサバン", "リクシアナ", "edoxaban", "Lixiana"],
    "ダビガトラン": ["ダビガトラン", "プラザキサ", "dabigatran"],
    "ワルファリン": ["ワルファリン", "ワーファリン", "warfarin"],

    # Statins
    "アトルバスタチン": ["アトルバスタチン", "リピトール", "atorvastatin"],
    "ロスバスタチン": ["ロスバスタチン", "クレストール", "rosuvastatin"],
    "ピタバスタチン": ["ピタバスタチン", "リバロ", "pitavastatin"],
    "プラバスタチン": ["プラバスタチン", "メバロチン", "pravastatin"],

    # Beta blockers
    "ビソプロロール": ["ビソプロロール", "メインテート", "bisoprolol"],
    "カルベジロール": ["カルベジロール", "アーチスト", "carvedilol"],
    "メトプロロール": ["メトプロロール", "セロケン", "ロプレソール", "metoprolol"],
    "ランジオロール": ["ランジオロール", "オノアクト", "landiolol"],
    "エスモロール": ["エスモロール", "esmolol", "ブレビブロック"],

    # ACE-I / ARB / ARNI
    "エナラプリル": ["エナラプリル", "レニベース", "enalapril"],
    "ペリンドプリル": ["ペリンドプリル", "コバシル", "perindopril"],
    "リシノプリル": ["リシノプリル", "ロンゲス", "lisinopril"],
    "オルメサルタン": ["オルメサルタン", "オルメテック", "olmesartan"],
    "カンデサルタン": ["カンデサルタン", "ブロプレス", "candesartan"],
    "テルミサルタン": ["テルミサルタン", "ミカルディス", "telmisartan"],
    "サクビトリルバルサルタン": [
        "サクビトリルバルサルタン", "サクビトリル/バルサルタン",
        "エンレスト", "ARNI", "sacubitril/valsartan", "sacubitril-valsartan",
    ],

    # MRA
    "スピロノラクトン": ["スピロノラクトン", "アルダクトン", "spironolactone"],
    "エプレレノン": ["エプレレノン", "セララ", "eplerenone"],

    # SGLT2-i
    "ダパグリフロジン": ["ダパグリフロジン", "フォシーガ", "dapagliflozin", "Forxiga"],
    "エンパグリフロジン": ["エンパグリフロジン", "ジャディアンス", "empagliflozin"],

    # Diuretics
    "フロセミド": ["フロセミド", "ラシックス", "furosemide", "Lasix"],
    "アゾセミド": ["アゾセミド", "ダイアート", "azosemide"],
    "トルバプタン": ["トルバプタン", "サムスカ", "tolvaptan"],

    # Inotropes / vasodilators
    "ドブタミン": ["ドブタミン", "dobutamine"],
    "ミルリノン": ["ミルリノン", "ミルリーラ", "milrinone"],
    "カルペリチド": ["カルペリチド", "ハンプ", "ANP", "carperitide"],
    "ニトログリセリン": ["ニトログリセリン", "ニトロ", "ミリスロール", "nitroglycerin"],
    "ニカルジピン": ["ニカルジピン", "ペルジピン", "nicardipine"],

    # Ca channel blockers
    "アムロジピン": ["アムロジピン", "ノルバスク", "アムロジン", "amlodipine"],
    "ベニジピン": ["ベニジピン", "コニール", "benidipine"],
    "ジルチアゼム": ["ジルチアゼム", "ヘルベッサー", "diltiazem"],

    # Nitrates
    "一硝酸イソソルビド": ["一硝酸イソソルビド", "アイトロール", "isosorbide mononitrate", "ISMN"],
    "ニコランジル": ["ニコランジル", "シグマート", "nicorandil"],

    # Antiarrhythmics
    "アミオダロン": ["アミオダロン", "アンカロン", "amiodarone"],
    "ピルシカイニド": ["ピルシカイニド", "サンリズム", "pilsicainide"],

    # Diabetes
    "メトホルミン": ["メトホルミン", "メトグルコ", "metformin"],

    # Other
    "アレンドロン酸": ["アレンドロン酸", "フォサマック", "alendronate"],
    "タファミディス": ["タファミディス", "ビンダケル", "ビンマック", "tafamidis"],
    "パチシラン": ["パチシラン", "オンパットロ", "patisiran"],
    "ブトリシラン": ["ブトリシラン", "vutrisiran", "アムヴトラ"],
    "アルテプラーゼ": ["アルテプラーゼ", "アクチバシン", "tPA", "alteplase"],

    # Steroids / antihistamines (PE/造影剤前投薬)
    "ヒドロコルチゾン": ["ヒドロコルチゾン", "ソル・コーテフ", "hydrocortisone"],

    # Mental health (SCP negative control)
    "セルトラリン": ["セルトラリン", "ジェイゾロフト", "sertraline"],
    "エスシタロプラム": ["エスシタロプラム", "レクサプロ", "escitalopram"],

    # Additional drugs found in subagent-generated cases
    "フェンタニル": ["フェンタニル", "fentanyl"],
    "ノルアドレナリン": ["ノルアドレナリン", "ノルエピネフリン", "norepinephrine"],
    "ドパミン": ["ドパミン", "dopamine", "イノバン"],
    "ジゴキシン": ["ジゴキシン", "ジゴシン", "digoxin"],
    "プレガバリン": ["プレガバリン", "リリカ", "pregabalin"],
    "ミドドリン": ["ミドドリン", "メトリジン", "midodrine"],
    "アンピシリン/スルバクタム": ["アンピシリン", "スルバクタム", "ユナシン", "ampicillin", "sulbactam"],
    "シタグリプチン": ["シタグリプチン", "ジャヌビア", "sitagliptin"],
    "メマンチン": ["メマンチン", "メマリー", "memantine"],
    "ドネペジル": ["ドネペジル", "アリセプト", "donepezil"],
    "エルデカルシトール": ["エルデカルシトール", "エディロール", "eldecalcitol"],
    "酸化マグネシウム": ["酸化マグネシウム", "マグミット"],
    "桂枝加竜骨牡蛎湯": ["桂枝加竜骨牡蛎湯"],
    "甘麦大棗湯": ["甘麦大棗湯"],
    "抑肝散": ["抑肝散"],
    "アルプラゾラム": ["アルプラゾラム", "ソラナックス", "alprazolam"],
    "エチゾラム": ["エチゾラム", "デパス", "etizolam"],
    "ロサルタン": ["ロサルタン", "ニューロタン", "losartan"],
}


def _build_reverse_index() -> Dict[str, str]:
    """Lower-cased synonym -> canonical name."""
    idx = {}
    for canonical, syns in DRUG_SYNONYMS.items():
        idx[canonical.lower()] = canonical
        for s in syns:
            idx[s.lower()] = canonical
    return idx


_REVERSE_IDX = _build_reverse_index()


def extract_drugs(text: str) -> Set[str]:
    """Find all canonical drug names mentioned in the text."""
    if not text:
        return set()
    found = set()
    text_lower = text.lower()
    # Match each synonym as a substring (drug names rarely overlap)
    for syn, canonical in _REVERSE_IDX.items():
        if syn in text_lower:
            found.add(canonical)
    return found


def normalize_keyfacts_drugs(med_list: List[str]) -> Set[str]:
    """Convert key_facts.medications_to_start entries (which include doses)
    into a set of canonical drug names."""
    drugs = set()
    for entry in med_list or []:
        # Each entry might be like "アスピリン 100mg/日" or "ヘパリン (減量投与)"
        for syn, canonical in _REVERSE_IDX.items():
            if syn in entry.lower():
                drugs.add(canonical)
                break
    return drugs


def compute_drug_f1(generated_text: str, gold_drugs: Set[str]) -> Dict[str, float]:
    """Return precision / recall / F1 over canonical drug names.

    Note: this is HIT/MISS over the synonym dictionary. A drug not in the
    dictionary is invisible to both sides; mark such cases via the unknown_count.
    """
    pred = extract_drugs(generated_text)

    if not gold_drugs:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0,
                "tp": 0, "fp": len(pred), "fn": 0,
                "predicted": sorted(pred), "gold": []}

    tp = pred & gold_drugs
    fp = pred - gold_drugs
    fn = gold_drugs - pred

    p = len(tp) / len(pred) if pred else 0.0
    r = len(tp) / len(gold_drugs)
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return {
        "precision": round(p, 3),
        "recall": round(r, 3),
        "f1": round(f1, 3),
        "tp": len(tp),
        "fp": len(fp),
        "fn": len(fn),
        "predicted": sorted(pred),
        "gold": sorted(gold_drugs),
        "false_positives": sorted(fp),
        "missing": sorted(fn),
    }
