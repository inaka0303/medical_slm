# ACI-JP-Cardio Outpatient Benchmark — Schema Specification v0.2

> 日本語循環器特化 **外来カルテ生成** ベンチマーク (22 例)。ACI-Bench (Yim et al., Nature Sci Data 2023) に倣い、初診 walk-in と再診/紹介状受診の 2 シナリオを並立させる。

## 0. メタ情報

| 項目 | 値 |
|---|---|
| バージョン | v0.2 (2026-04-29 起草) |
| 上位プロジェクト | ACI-JP-Cardio (`data/aci_jp_cardio/`) |
| 別 track | `admission/` (入院・本格治療版、既存 22 例) |
| ライセンス想定 | CC BY 4.0 (将来公開時) |
| 対応モデル | Qwen3.5-4B / 9B + 各種 LoRA、RAG、将来 vLLM/SGLang/MLX |

## 1. 設計の本質

実臨床の 2 つの典型シナリオを別々に評価する:

| シナリオ | 受診形態 | 入力 | 持っている情報 | reference SOAP | 評価軸 |
|---|---|---|---|---|---|
| **A: 紹介状/再診** | 紹介患者 or 経過観察 | 医師サマリ (Pattern A) | お薬手帳・診察所見・バイタル・前医所見・前回検査値 すべてあり | **確定診断 + 詳細治療計画** | 薬剤・治療方針の網羅性 |
| **B: 初診 walk-in** | 飛び込み初診 | 口語対話 (Pattern B) | 主訴 + 患者自己申告 + 受付測定値のみ。診察所見・採血・画像は **null** | **triage 型** (暫定診断 + 鑑別 + 次の手) | 鑑別力 + must-not-miss + 適切な triage 判断 |

→ **同一疾患でも別患者** を割り当てて、入力情報量と reference の性質を独立させる。

## 2. 22 例の構成

11 疾患 × 2 シナリオ:

| 疾患 (code) | A: 紹介状/再診 | B: 初診 walk-in |
|---|---|---|
| 急性心筋梗塞 (AMI) | PCI 後 6-8 週外来フォロー (二次予防確認) | 持続性胸痛で walk-in、ECG 前段階 |
| 心房細動 (AF) | 健診で AF 指摘の紹介状受診 | 動悸主訴で walk-in |
| 肺塞栓症 (PE) | DVT/PE 治療後 3 ヶ月再診、息切れ再燃 | 突然の呼吸困難で walk-in |
| 大動脈解離 (AD) | 大動脈疾患外来再診 (薬物管理 Stanford B 慢性期) | 引き裂かれるような胸背部痛で walk-in |
| 慢性心不全 (CHF) | HFrEF 安定期再診 (薬剤調整目的) | 浮腫・息切れで walk-in |
| 冠攣縮性狭心症 (VSA) | VSA 確定後再診 (発作日記持参) | 夜間胸痛で walk-in |
| 大動脈弁狭窄症 (AS) | 中等度 AS 経過観察再診 | 失神・労作時息切れで walk-in |
| 労作性狭心症 (EA) | 安定狭心症 6 ヶ月フォロー再診 | **持続胸痛で walk-in (実データベース)** |
| 急性心不全 (AHF) | CHF 急性増悪後退院 4 週フォロー | 急性発症の呼吸困難で walk-in |
| 心アミロイドーシス (CA) | wt-ATTR 確定後の tafamidis 導入再診 | red-flag 主訴 (HFpEF + 手根管) で精査依頼受診 |
| 身体表現性障害 (SCP) | 心療内科再診で循環器コンサルト | 胸痛繰り返しで walk-in (鑑別目的) |

### encounter_id 形式

`JC-{code}-{scenario}`、scenario ∈ {A, B}

例: `JC-AMI-A`, `JC-AMI-B`, `JC-AF-A`, `JC-AF-B`, ..., `JC-SCP-B`

## 3. 難度多様性

22 例で typical / atypical / borderline をミックスする:

| 難度 | 説明 | 想定割合 |
|---|---|---|
| typical | 教科書的所見、診断・治療方針が明快 | 9 例程度 |
| atypical | 高齢・女性・併存疾患・無痛性虚血等の非典型呈示 | 8 例程度 |
| borderline | 鑑別困難、複数疾患合併、SDM 必要 | 5 例程度 |

各 case の `difficulty` field に明記。

## 4. JSONL schema

```json
{
  "encounter_id": "JC-EA-B",
  "scenario": "shoshin_walkin",
  "disease_label": "stable_angina",
  "disease_label_jp": "労作性狭心症 (atypical 持続性胸痛)",
  "difficulty": "atypical",

  "patient": {
    "age": 53,
    "gender": "男性",
    "blood_type": "A",
    "comorbidities": ["高血圧 (内服中)"],
    "current_medications": ["ロサルタンカリウム 50mg 1錠 朝食後"],
    "allergies": ["特記なし"],
    "family_history": ["特記なし"],
    "social_history": "喫煙 元喫煙者 (禁煙 1 年未満)、機会飲酒、デスクワーク、ジョギング 30 分/日、睡眠 8 時間以上、ストレス少"
  },

  "encounter": {
    "type": "外来初診",
    "department": "循環器内科",
    "encounter_date": "2026-03-23",
    "chief_complaint": "胸が痛い (2 週間持続)",
    "secondary_complaints": ["息苦しさ", "冷や汗", "心拍速感"]
  },

  "reception_vitals": {
    "BP_sys": 142, "BP_dia": 86, "HR": 88, "SpO2": 98, "RR": 18, "BT": 36.5
  },

  "input_pattern_A": null,
  "input_pattern_B": "[医師] 今日はどのような症状でいらっしゃいましたか?\n[患者] あの、2 週間ほど前から胸が痛くて...締め付けられるような感じで...\n[医師] 痛みは何分くらい続きますか?\n[患者] ずっと続いているような感じです、よくはなったり悪くなったりしますけど...\n...",

  "reference_soap": {
    "S": "53 歳男性、2 週間前から胸部の締め付け感 (NRS 6/10) が持続的に出現。安静で軽減傾向だが完全消失なし、息苦しさ・冷や汗・心拍速感を伴う。腕・背中・顎への放散なし。嘔気なし。運動・安静で大きな変動なし。既往: 高血圧 (ロサルタン内服中)。元喫煙 (禁煙 1 年未満)、デスクワーク、ジョギング毎日 30 分。家族歴特記なし。",
    "O": "受付バイタル: BP 142/86 mmHg、HR 88/min、SpO2 98% RA、RR 18、BT 36.5℃。意識清明。\n*診察前段階で身体所見・採血・画像なし。優先取得項目: 12 誘導 ECG、トロポニン I、CK-MB、SpO2 経時、聴診、胸部 X-p。*",
    "A": "# 1. 持続性胸痛 (2 週間)、心血管リスク因子 (HTN・元喫煙・デスクワーク) 集積。\n  鑑別: 不安定狭心症、安定狭心症 (持続パターンは非典型)、肋間神経痛・胸壁筋肉痛、逆流性食道炎、心因性胸痛。\n  心拍速感は AF 等の不整脈合併も考慮。\n# Must rule out: 急性冠症候群 (不安定狭心症 / NSTEMI)、大動脈解離、肺塞栓症。",
    "P": "1. 12 誘導 ECG を直ちに記録。ST-T 変化・虚血性変化を確認。\n2. 採血: トロポニン I・CK-MB・BNP・D-dimer・電解質・腎機能。\n3. SpO2 経時モニター。\n4. 胸部 X-p で大動脈陰影・肺野評価。\n5. ECG または採血で ACS 強疑なら循環器コンサルト + 必要に応じ救急搬送 (CAG プロトコル)。\n6. ECG・採血が陰性かつ症状安定なら、循環器外来で運動負荷 ECG または冠動脈 CT を予定。\n7. ロサルタン継続、血圧手帳記録の徹底。\n8. 喫煙再開しないよう指導継続。\n9. 症状増悪 (痛み増強・継続時間延長・冷汗増悪・失神) あれば即救急搬送するよう本人・家族に説明。"
  },

  "reference_admission_summary": null,

  "key_facts": {
    "expected_triage": "外来精査",
    "alternative_acceptable_triage": ["緊急搬送 (ECG 陽性時)"],
    "differential_diagnoses": [
      "不安定狭心症", "安定狭心症", "肋間神経痛", "胸壁筋肉痛", "心因性胸痛", "逆流性食道炎"
    ],
    "must_not_miss": ["急性冠症候群 (不安定狭心症 / NSTEMI)", "大動脈解離", "肺塞栓症"],
    "appropriate_next_tests": [
      "12 誘導 ECG", "トロポニン I", "CK-MB", "BNP", "D-dimer", "胸部 X-p", "SpO2 モニター"
    ],
    "diagnoses_provisional": ["持続性胸痛 (鑑別中)", "急性冠症候群疑い"],
    "medications_to_start": [],
    "medications_to_continue": ["ロサルタンカリウム 50mg/日"],
    "medications_to_stop": [],
    "vitals": {"BP_sys": 142, "BP_dia": 86, "HR": 88, "SpO2": 98, "RR": 18, "BT": 36.5},
    "labs": null,
    "ecg_findings": null,
    "echo_findings": null,
    "scores": null,
    "procedures": null,
    "disposition": "外来精査 (即時 ECG・採血)"
  },

  "rag_citations": [
    {"guideline": "JCS 2018 急性冠症候群ガイドライン", "section": "ACS 初期評価", "key_point": "持続性胸痛 + リスク因子集積では ACS をルールアウトするまで他疾患と決めつけない"},
    {"guideline": "JCS 2018 安定冠動脈疾患の診断と治療ガイドライン", "section": "外来初診時の評価", "key_point": "胸痛主訴では心血管リスクスコアと ECG・トロポニンで初期 triage"}
  ],

  "is_negative_control": false,
  "notes_for_reviewer": "ユーザーから提供された AI 問診サンプル (2026-03-23) を Pattern B に変換した。SLM 評価ポイント: (a) 持続性 2 週間 + リスク因子から ACS をルールアウトする判断、(b) 受付バイタルだけで「外来精査」を選べるか (緊急搬送は ECG 待ち)、(c) 鑑別リストの網羅性 (不安定狭心症 / 解離 / PE が must_not_miss にある)、(d) 不要な検査 (心エコー先行・心筋シンチ即時) を出さない。"
}
```

### フィールド役割

| フィールド | 用途 | 必須? |
|---|---|---|
| `encounter_id` | 一意 ID。`-A` or `-B` 接尾辞でシナリオ判別 | ✅ |
| `scenario` | `referral_or_revisit` or `shoshin_walkin` | ✅ |
| `disease_label`, `disease_label_jp` | 集計・層別 | ✅ |
| `difficulty` | typical / atypical / borderline | ✅ |
| `patient.*` | プロンプトに注入される患者属性 | ✅ |
| `encounter.*` | 受診コンテキスト | ✅ |
| `reception_vitals` | 受付測定値、両シナリオで持つ | ✅ |
| `input_pattern_A` | 医師サマリ (シナリオ A のみ。B は null) | A のみ必須 |
| `input_pattern_B` | 口語対話 (シナリオ B のみ。A は null) | B のみ必須 |
| `reference_soap.{S,O,A,P}` | 評価用正解 SOAP。シナリオ別の特性に従う | ✅ |
| `reference_admission_summary` | 入院時サマリ。**outpatient track では基本 null**。Aシナリオで「再診結果として入院判断」した場合のみ | 任意 |
| `key_facts.expected_triage` | 期待される triage 判断 (緊急搬送/外来精査/帰宅/専門科紹介) | ✅ |
| `key_facts.differential_diagnoses` | 鑑別候補リスト | ✅ |
| `key_facts.must_not_miss` | 「見逃すと死ぬ」必須鑑別 | ✅ |
| `key_facts.appropriate_next_tests` | 推奨追加検査 | ✅ |
| `key_facts.medications_to_start/continue/stop` | 薬剤情報 | ✅ |
| `is_negative_control` | true なら鑑別重視ケース (SCP-B 等) | ✅ |
| `notes_for_reviewer` | 先生レビュー時のヒント、SLM 評価ポイント | 任意 |

## 5. シナリオ別 reference SOAP の設計指針

### シナリオ A (紹介状/再診)

| section | 書く内容 |
|---|---|
| S | 主訴 + 経過 + 既往 + 服薬 + 社会歴 + (紹介状の場合) 前医所見要約 |
| O | バイタル + 身体診察 + (再診の場合) 前回検査値推移 + 必要なら新規所見 |
| A | **確定診断**または「○○ 確定、現在 ○○期」のような明確なステージング、合併症評価 |
| P | 具体的薬剤調整 (用量変更含む)、追加検査オーダー、次回再診日、患者教育 |

### シナリオ B (初診 walk-in)

| section | 書く内容 |
|---|---|
| S | 主訴 + HPI + 既往 + 服薬 + 社会歴 (患者自己申告のみ、確認不能なものは "本人申告" と明記) |
| O | **受付バイタルのみ**。「診察前段階で身体所見・採血・画像なし」と明記。優先取得項目を列挙 |
| A | **暫定診断 + 鑑別リスト**。"○○疑い、>○○・○○ も鑑別" 形式。Must-not-miss を必ず含める |
| P | **次の手のみ**: 即時 ECG・採血等の緊急検査、triage 判断 (救急搬送 / 入院判定 / 専門科紹介 / 外来精査 / 帰宅)、家族への説明、Red flag 症状での再来指示 |

## 6. メトリクス

### 既存指標 (admission track と共通)

- ROUGE-L、BERTScore F1
- Drug F1 / Diagnosis F1 / Vitals match rate

### outpatient track 固有の追加指標

- **Triage F1**: SLM の P から triage 判断を抽出 (緊急搬送/外来精査/帰宅/紹介) → `key_facts.expected_triage` と一致するか
- **Differential Recall**: SLM の A セクションに含まれる鑑別が `key_facts.differential_diagnoses` をどれだけカバーするか
- **Must-not-miss Recall**: `key_facts.must_not_miss` を SLM が漏らさず A に含めているか (=安全性指標)
- **Inappropriate test FP**: SLM が出した検査オーダーのうち `appropriate_next_tests` にないものの数 (例: 眼科症状で心エコー指示 = FP)

最終 composite (シナリオ B):

```
final_score_B = (rouge_l + bertscore + drug_f1 + triage_f1 + diff_recall + mnm_recall) / 6
```

シナリオ A は admission track と同じ式。

## 7. ファイル / ディレクトリ構造

```
data/aci_jp_cardio/outpatient/
├── SPEC.md                    # 本ファイル
├── README.md
├── cases/                     # 22 例の JSON
│   ├── JC-AMI-A.json
│   ├── JC-AMI-B.json
│   ├── ... (22 files)
│   └── JC-SCP-B.json
├── cases.jsonl                # 結合 JSONL
├── eval_runner/               # 改訂版 runner (triage / must-not-miss メトリクス追加)
└── results/                   # 評価結果
```

## 8. 既存 admission track との関係

| 比較軸 | admission track (既存) | outpatient track (新規) |
|---|---|---|
| シナリオ | 入院・本格治療 | 紹介状/再診 + 初診 |
| 例数 | 22 (S=11, V=11) | 22 (A=11, B=11) |
| 入力形式 | structured (4 セクション) / voice STT モノローグ | 医師サマリ / 口語対話 |
| reference SOAP | 確定診断 + 詳細治療 + admission_summary | 確定診断 (A) / 暫定+鑑別 (B) |
| 評価指標 | ROUGE-L + BS + drug F1 + diag F1 + vitals | 上記 + triage / must-not-miss / diff recall |
| 想定使用シーン | 入院後カルテ生成、退院サマリ | 外来初診/再診カルテ生成 |
| 学会発表における位置 | 「入院・治療パス」評価 | 「初診 triage / 再診」評価 |

両者は **直交した臨床ワークフロー** を測るので、論文では「2 トラック」と並列で報告できる。
