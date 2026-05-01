# ACI-JP-Cardio Benchmark

> 日本語循環器特化 visit-note 生成ベンチマーク (22 例)。ACI-Bench (Yim et al., Nature Sci Data 2023) のスキーマに準拠。

## 構成

| ファイル | 内容 |
|---|---|
| `SPEC.md` | スキーマ仕様書 (必読) |
| `cases/JC-*.json` | 22 例の個別 case ファイル (11 疾患 × 2 形式) |
| `cases.jsonl` | 22 例を結合した JSONL (eval_runner が読む) |
| `aci_compat/{cases,metadata}.csv` | ACI-Bench 互換 CSV ビュー |
| `review.html` | 先生レビュー用 single-file HTML viewer |
| `eval_runner/` | ベンチマーク runner と各メトリクス |
| `results/` | eval_runner の実行結果 |

## 22 例の内訳

11 疾患 × 2 形式 (S = structured / V = voice STT):

| 疾患 | encounter_id | 内容 |
|---|---|---|
| 急性心筋梗塞 | JC-AMI-S, JC-AMI-V | 前壁 STEMI / 高齢女性 atypical 下壁 STEMI |
| 心房細動 | JC-AF-S, JC-AF-V | 新規発症 / 高齢無症候 SDM |
| 肺塞栓症 | JC-PE-S, JC-PE-V | 飛行後 submassive / 術後 massive shock |
| 大動脈解離 | JC-AD-S, JC-AD-V | Stanford A 緊急 OP / Stanford B 薬物管理 |
| 慢性心不全 | JC-CHF-S, JC-CHF-V | HFrEF fantastic four / HFpEF 社会的入院 |
| 冠攣縮性狭心症 | JC-VSA-S, JC-VSA-V | ACh 負荷陽性 / ER 反復受診 |
| 大動脈弁狭窄症 | JC-AS-S, JC-AS-V | TAVI workup / frailty SDM |
| 労作性狭心症 | JC-EA-S, JC-EA-V | CCS II 待機 PCI / 糖尿病 silent ischemia |
| 急性心不全 | JC-AHF-S, JC-AHF-V | chronic decompensated / takotsubo 鑑別 |
| 心アミロイドーシス | JC-CA-S, JC-CA-V | wt-ATTR tafamidis / 遺伝性 ATTRv siRNA |
| **身体表現性障害** (陰性対照) | JC-SCP-S, JC-SCP-V | 若年女性不安障害 / 中年男性 doctor shopping |

## 使い方

### 1. cases.jsonl 再生成

```bash
python3 eval_runner/build_jsonl.py
```

### 2. 先生レビュー UI を再生成 (cases 編集後)

```bash
python3 eval_runner/build_review_ui.py
# 出力: review.html (ブラウザで開くだけ、サーバー不要)
```

### 3. ベンチマーク実行

```bash
# 4B SOAP
python3.11 eval_runner/eval_cardio.py \
  --cases cases.jsonl --target soap --model 4b_soap_full \
  --output results/run_4b_soap.json

# 9B 入院時サマリ
python3.11 eval_runner/eval_cardio.py \
  --cases cases.jsonl --target admission --model 9b_admission \
  --output results/run_9b_admission.json

# 4B 入院時サマリ (fallback)
python3.11 eval_runner/eval_cardio.py \
  --cases cases.jsonl --target admission --model 4b_admission \
  --output results/run_4b_admission.json
```

オプション:
- `--skip-bertscore`: BERTScore モデル (cl-tohoku/bert-base-japanese-v3) のロードを省略 (CPU で 30-60s 短縮)
- `--limit N`: 最初の N 例のみ
- `--include-negative-control`: SCP も admission 対象に含める (デフォルトは skip)

### 4. 結果を集計・比較

```bash
python3 eval_runner/aggregate.py results/*.json --output results/comparison.md
```

## メトリクス

| 名前 | 何を測るか | 典拠 |
|---|---|---|
| ROUGE-L | n-gram 類似度 (MeCab 分かち書き) | ACI-Bench 互換 |
| BERTScore F1 | 意味類似度 (cl-tohoku/bert-base-japanese-v3) | ACI-Bench 互換 |
| **drug_f1** | 薬剤名 F1 (一般名・商品名・英語表記の同義語辞書) | MEDCON (UMLS F1) の代替 |
| **diagnosis_f1** | 診断名 F1 (循環器シノニム辞書) | 我々の追加 |
| **vitals_match** | バイタル/検査値 ±10% 一致率 | 我々の追加 |
| **opus_judge** | 5 軸 rubric (medical / completeness / naturalness / hallucination / format) | 我々の追加 |

最終 composite スコア = (ROUGE-L + BERTScore + drug_f1 + diagnosis_f1 + vitals_match) / 5

## Opus-as-judge (subagent 経由)

`eval_runner/opus_judge.py` は judging プロンプトの JSONL を生成。Claude Code の subagent (Opus 4.7) を 1 行 1 件で起動して採点する想定。

```python
from opus_judge import write_judge_prompts
# results/judge_prompts.jsonl を生成 → 別 stage で subagent 並列実行
```

## ACI-Bench 互換性

`aci_compat/` に英語 ACI-Bench と同じ CSV 構造 (dataset / encounter_id / dialogue / note) で派生ビューを生成。論文で「ACI-Bench に倣って構築した日本語循環器版」と書ける。

## ライセンス

将来公開予定: CC BY 4.0 (ACI-Bench と同条件)
公開時のリポジトリ案: `inaka0303/aci-jp-cardio`
