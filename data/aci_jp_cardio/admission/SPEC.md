# ACI-JP-Cardio Benchmark — Schema Specification v0.1

> 日本語循環器特化 visit note 生成ベンチマーク。ACI-Bench (Yim et al., Nature Sci Data 2023, CC-BY 4.0) のスキーマに準拠し、日本語 / 循環器 / 軽量 SLM 評価向けに拡張する。

---

## 0. メタ情報

| 項目 | 値 |
|---|---|
| バージョン | v0.1 (2026-04-27 起草) |
| ライセンス想定 | CC BY 4.0 (将来公開時) |
| 対応モデル評価対象 | Qwen3.5-4B / 9B + LoRA (suggest / soap_v2 / admission_v3_clean)、RAG (Ruri-v3 + ChromaDB)、将来 vLLM/SGLang/MLX |
| 想定使用シーン | (a) 開発時の自動回帰テスト (b) 4B vs 9B / RAG 有無 / 推論エンジン切替の定量比較 (c) 国際会議論文の主要評価表 |

---

## 1. 全体構成

- **11 疾患 × 2 形式 = 22 encounter**
- 各 encounter は 1 つの JSON ファイル: `cases/<encounter_id>.json`
- 統合 JSONL は build script で生成: `cases.jsonl` (eval runner はこちらを読む)
- ACI-Bench 互換 CSV は派生生成: `aci_compat/{cases.csv, metadata.csv}`

### 11 疾患リストと ID

| # | 疾患名 (日本語) | 英略 | code prefix |
|---|---|---|---|
| 1 | 急性心筋梗塞 | AMI | AMI |
| 2 | 心房細動 | AF | AF |
| 3 | 肺塞栓症 | PE | PE |
| 4 | 大動脈解離 | AD | AD |
| 5 | 慢性心不全 | CHF | CHF |
| 6 | 冠攣縮性狭心症 | VSA | VSA |
| 7 | 大動脈弁狭窄症 | AS | AS |
| 8 | 労作性狭心症 | EA | EA |
| 9 | 急性心不全 | AHF | AHF |
| 10 | 心アミロイドーシス | CA | CA |
| 11 | 身体表現性障害 (胸痛) | SCP | SCP |

### encounter_id 形式

`JC-{code}-{format}` (JC = Japan Cardio)

- `format = S` → structured (フォーマル問診)
- `format = V` → voice / STT (音声花子型モノローグ)

例: `JC-AMI-S`, `JC-AMI-V`, `JC-AF-S`, `JC-AF-V`, ... `JC-SCP-V`

合計 11 × 2 = 22 件。

---

## 2. 2 形式の定義 (フォーマット軸)

ACI-Bench の `dataset` 列 (aci/virtassist/virtscribe) に対応する我々の **入力フォーマット軸**。同一疾患・同一患者プロファイルに対し 2 通りの問診入力で 1 ペアを構成しても良いし、別患者にしても良い (Phase 1 で決定)。

### 形式 S: structured (構造化問診)

- 4 セクション完備: 問診記録 / お薬手帳 / 診察所見 / 検査結果
- 文体: 医療者が整理して記録した文。句読点正常、文法正常、医学用語適切
- 既存 seed.go の 山本隆 / 加藤真理 と同形式
- 期待される SLM 挙動: 高品質 SOAP / admission summary 生成 (理想ケース)

### 形式 V: voice / STT (音声花子型モノローグ)

- セクション無し、生のモノローグ 1 ブロック
- 文体: STT 出力風。話者ラベルなし、句読点欠落多、フィラー (「えーと」「あの」) 残存、自己訂正、同時発話混入
- 既存 seed.go の 音声花子 (MRN-0022) と同形式
- 期待される SLM 挙動: フォーマット耐性 / 抽象化能力の検証 (難ケース)

### Reference は 2 形式で同一?

**いいえ、別々**。形式 S と形式 V は別 encounter 扱いで、それぞれに reference SOAP + reference admission summary を持つ。患者プロファイル (年齢・性別・既往) は **同一にしてペア構成すると問診情報量の差分のみ評価できる** が、異なる患者にして「疾患カバレッジを 22 件に拡大する」のもアリ。

**Phase 1 で決定**: MI 2 例を作るときに、同一患者で形式違い vs 別患者を両方試してどちらが評価に適切か判断する。

---

## 3. JSONL schema

各 case file は以下の構造:

```json
{
  "encounter_id": "JC-AMI-S",
  "format": "structured",
  "disease_label": "acute_myocardial_infarction",
  "disease_label_jp": "急性心筋梗塞",

  "patient": {
    "age": 68,
    "gender": "男性",
    "blood_type": "A",
    "comorbidities": ["高血圧", "2型糖尿病", "脂質異常症"],
    "current_medications": ["アムロジピン 5mg 1錠/日", "メトホルミン 500mg 2錠/日"],
    "family_history": ["父: 心筋梗塞 (60歳代)"],
    "social_history": "20本×40年 (Brinkman 800)、機会飲酒"
  },

  "encounter": {
    "department": "循環器内科",
    "encounter_type": "外来初診",
    "chief_complaint": "突然の胸部圧迫感",
    "secondary_complaints": ["冷汗", "左肩への放散痛"],
    "encounter_date": "2026-04-15"
  },

  "interview_text": {
    "raw_text": "...問診本文...",
    "medication_list": "...持参薬...",
    "exam_findings": "...身体所見...",
    "lab_results": "..."
  },

  "interview_text_voice": null,

  "reference_soap": {
    "S": "...",
    "O": "...",
    "A": "...",
    "P": "..."
  },

  "reference_admission_summary": "...",

  "key_facts": {
    "diagnoses": ["急性前壁心筋梗塞", "Killip分類 II"],
    "medications_to_start": ["アスピリン 100mg", "クロピドグレル 75mg", "アトルバスタチン 20mg", "ビソプロロール 2.5mg"],
    "medications_to_continue": ["アムロジピン 5mg", "メトホルミン 500mg"],
    "vitals": {"BP_sys": 152, "BP_dia": 94, "HR": 98, "SpO2": 96, "RR": 20, "BT": 36.7},
    "labs": {"Tnl": 12.4, "CK": 845, "CK_MB": 78, "BNP": 280, "Cr": 0.92},
    "ecg_findings": ["V1-V4 ST 上昇", "II/III/aVF 鏡像変化"],
    "echo_findings": ["前壁中隔 hypokinesis", "LVEF 42%"],
    "scores": {"GRACE": 142, "TIMI": 4, "Killip": 2},
    "procedures": ["冠動脈造影 (CAG)", "経皮的冠動脈形成術 (PCI)"]
  },

  "rag_citations": [
    {"guideline": "JCS 2018 急性冠症候群ガイドライン", "section": "STEMI 初期治療", "key_point": "発症 12 時間以内は primary PCI が第一選択"}
  ],

  "format_pair_id": "JC-AMI-PAIR-01",
  "is_negative_control": false,
  "difficulty": "typical",
  "notes_for_reviewer": "標準的な前壁 STEMI 症例。fibrinolytic 適応外。"
}
```

### フィールド役割定義

| フィールド | 用途 | 必須? |
|---|---|---|
| `encounter_id` | 一意識別子 | ✅ |
| `format` | `structured` or `voice` | ✅ |
| `disease_label`, `disease_label_jp` | 集計・層別解析 | ✅ |
| `patient.*` | プロンプトに注入される患者属性 (existing `buildPatientHeader` 互換) | ✅ |
| `encounter.*` | 受診コンテキスト | ✅ |
| `interview_text.*` | **形式 S の入力**。4 セクション。形式 V のときは全部 `null` | S のみ必須 |
| `interview_text_voice` | **形式 V の入力**。生モノローグ 1 文字列 | V のみ必須 |
| `reference_soap.{S,O,A,P}` | SOAP 評価の正解 | ✅ |
| `reference_admission_summary` | admission summary 評価の正解 (形式 S のみ。V は `null` 可) | S 必須 |
| `key_facts` | **薬剤・診断・数値の機械抽出ベース F1 計算用** (= MEDCON 代替) | ✅ |
| `rag_citations` | RAG 評価でガイドラインヒット率を測る | 任意 |
| `format_pair_id` | 同一プロファイル S/V ペアの ID。別患者ペアなら無し | 任意 |
| `is_negative_control` | true なら「典型疾患でない」例 (SCP がここ)。鑑別力評価用 | ✅ (default false) |
| `difficulty` | `typical` / `atypical` / `borderline`。鑑別力評価用 | ✅ |
| `notes_for_reviewer` | 先生レビュー時のヒント | 任意 |

---

## 4. Reference 作成方針

### Phase 1: 心筋梗塞 2 例 (gold reference)

私 (Claude) がハンドメイドで完成させる。これを以降の subagent few-shot のテンプレートにする。

### Phase 2: 残り 10 疾患 × 2 形式 = 20 例

subagent (Opus 4.7) を 11 並列で起動。各 subagent に渡すもの:
- SPEC.md (本ファイル)
- Phase 1 の MI 2 例 (gold)
- 該当疾患の **JCS / 関連学会ガイドライン** 抽出 (RAG DB から検索)
- 出力指示: `cases/JC-{code}-S.json` + `cases/JC-{code}-V.json`

各 subagent は自分の疾患の症例を 2 形式生成、key_facts まで埋める。

### Phase 3: 先生レビュー (バッチ)

- 22 例を一気に読む
- 修正は markdown コメント or 直接 JSON 編集
- 私が修正を反映してファイル更新

---

## 5. メトリクス定義

### ベース指標 (ACI-Bench 互換)

| 指標 | 実装 | 用途 |
|---|---|---|
| **ROUGE-L** | `rouge-score` Python パッケージ、日本語は MeCab 分かち書き前処理 | n-gram 一致 |
| **BERTScore** | `bert-score` パッケージ、`cl-tohoku/bert-base-japanese-v3` | 意味類似度 |

### 我々の追加指標

| 指標 | 実装 | 用途 |
|---|---|---|
| **薬剤名 Recall / Precision / F1** | `key_facts.medications_to_start` + `medications_to_continue` を正解集合とし、生成テキストから正規表現＋同義語辞書 (HF: MANBYO 薬剤辞書 + 商品名↔一般名表) で抽出。**架空薬名は automatic FP** | 4B 薬剤ハルシネーション検出の決定打 |
| **診断名 Recall / Precision / F1** | `key_facts.diagnoses` を正解集合 | 主病名の取りこぼし検出 |
| **数値抽出一致率** | `key_facts.vitals` + `labs` の数値を生成から regex 抽出し ±10% 許容で一致判定 | バイタル誤記検出 |
| **Opus-as-judge (5 軸 rubric)** | Claude Code の subagent (Opus 4.7) を使って 5 軸 5 段階 rubric 評価。軸: ①医学的妥当性 ②情報網羅性 ③日本語自然さ ④ハルシネーション ⑤フォーマット遵守 | 自動指標で測れない総合品質 |

### 集計指標

ACI-Bench に倣って:

```
final_score = (rouge_l + bertscore + drug_f1 + diagnosis_f1 + opus_judge_avg) / 5
```

の単純平均。重み付けは Phase 5 のベースライン後に再検討。

### 層別解析

- 形式別 (S vs V)
- 疾患別 (11 個)
- difficulty 別 (typical / atypical / borderline)
- is_negative_control = true (SCP) のみで FP 率

---

## 6. Eval Runner I/O 仕様

### 入力

```bash
python3 eval_runner/eval_cardio.py \
  --cases /home/junkanki/naka/data/aci_jp_cardio/cases.jsonl \
  --target soap                    # or admission
  --model 4b_v2_r64                # LoRA ID
  --slm_url http://localhost:8081
  --rag_url http://localhost:8082  # optional
  --output results/run_<timestamp>.json
```

### 出力 (JSON)

```json
{
  "run_id": "run_1714100000",
  "timestamp": "2026-04-28T10:00:00Z",
  "config": {"model": "4b_v2_r64", "rag": false, ...},
  "per_case": [
    {
      "encounter_id": "JC-AMI-S",
      "generated": {"S":"...","O":"...","A":"...","P":"..."},
      "metrics": {
        "rouge_l": 0.45,
        "bertscore_f1": 0.81,
        "drug_recall": 0.75,
        "drug_precision": 0.60,
        "drug_f1": 0.667,
        "diagnosis_f1": 0.83,
        "vitals_match_rate": 0.92,
        "opus_judge": {"medical":4,"completeness":3,"naturalness":5,"hallucination":3,"format":5,"avg":4.0}
      }
    }
  ],
  "aggregate": {
    "by_format": {"S": {...}, "V": {...}},
    "by_disease": {...},
    "overall_final_score": 0.72
  }
}
```

---

## 7. ファイル / ディレクトリ構造

```
data/aci_jp_cardio/
├── SPEC.md                         # 本ファイル
├── README.md                       # 利用者向けクイックスタート (Phase 5 後に書く)
├── cases/                          # 22 例の JSON 個別ファイル
│   ├── JC-AMI-S.json
│   ├── JC-AMI-V.json
│   ├── JC-AF-S.json
│   ├── JC-AF-V.json
│   ├── ... (22 files)
│   └── JC-SCP-V.json
├── cases.jsonl                     # build script で全 case を結合
├── aci_compat/                     # ACI-Bench 互換 CSV ビュー (派生)
│   ├── cases.csv
│   └── metadata.csv
├── eval_runner/
│   ├── eval_cardio.py              # メインエントリ
│   ├── metrics_rouge.py
│   ├── metrics_bertscore.py
│   ├── metrics_drug_f1.py          # 薬剤同義語辞書ロード + F1
│   ├── metrics_opus_judge.py       # subagent 経由 Opus 判定
│   └── build_jsonl.py              # cases/*.json → cases.jsonl
└── results/                        # eval 実行結果
    └── run_<timestamp>.json
```

---

## 8. ACI-Bench との互換ビュー

将来 ACI-Bench の英語チームと比較したい場合のため、CSV 派生を生成:

### `aci_compat/metadata.csv`

```csv
dataset,encounter_id,id,doctor_name,patient_gender,patient_age,patient_firstname,patient_familyname,cc,2nd_complaints
acijpcardio,JC-AMI-S,1,,男性,68,匿名,匿名,突然の胸部圧迫感,冷汗;左肩への放散痛
...
```

### `aci_compat/cases.csv`

```csv
dataset,encounter_id,dialogue,note
acijpcardio,JC-AMI-S,"【問診記録】...","S: ...\nO: ...\nA: ...\nP: ..."
...
```

注: 形式 S は 4 セクション結合 → `dialogue` 列、形式 V は生モノローグ → `dialogue` 列。`note` 列は SOAP を 4 ブロックの平文で。

---

## 9. オープンクエスチョン (Phase 1 で決定)

1. **形式 S/V の患者プロファイル共有 vs 独立** — 同一プロファイルで入力フォーマットだけ変えるか、別患者にするか
2. **encounter_date の置き方** — 22 例全部 `2026-04-XX` で統一するか、季節性を入れるか (PE は long flight 後など)
3. **`reference_admission_summary` を形式 V でも持つか** — STT 入力からも admission summary 生成は要求するか
4. **Opus judge の rubric 文言** — 5 軸の各段階の語句を Phase 4 で確定

---

## 10. ライセンス・公開計画

- 本データセットは将来 **CC BY 4.0** で公開予定 (HF Hub / Figshare / Zenodo)
- 公開時に必要: IRB 不要 (合成データ宣言)、引用情報 (Yim et al. 2023 + 我々の論文)
- 公開時のリポジトリ名候補: `inaka0303/aci-jp-cardio`
