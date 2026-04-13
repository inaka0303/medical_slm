# 医療特化SLM プロジェクト

## 目的
日本語電子カルテ向け医療特化SLM（Small Language Model）の開発。
メイン機能: 患者の問診データを参照し、カルテ記載時のsuggest（文章候補提示）を行う。

## ベースモデル
- `unsloth/Qwen3.5-0.8B-Base`

## 学習パイプライン
1. **CPT（継続事前学習）**: 医療コーパスでLoRA学習 → `train_unsloth_cpt.py`
2. **SFT（Instruction Tuning）**: CPT済みモデルにLoRAで指示追従学習 → `train_sft.py`

## ディレクトリ構成
```
data/
  corpus.txt           # CPT用コーパス（ガイドライン2,257件+カルテ6,242件, 240MB）
  sft_data_2.jsonl     # SFT用データ（messages形式, 3,194件）※本番用
  sft_data_1.jsonl     # SFT用データ（instruction形式）※参考用
  sft_soap_stepwise.jsonl  # 段階的SOAPデータ単体（120件）

output/                # 学習済みモデル（各実験名/merged/ にマージ済みモデル）
logs/                  # 学習ログ
results/               # Phase1 推論結果（CPTモデル6つ）
results_phase2/        # Phase2 推論結果（CPT R7/R8 + SFT全モデル）
```

## 主要スクリプト
| ファイル | 用途 |
|---|---|
| `train_unsloth_cpt.py` | CPT学習（LoRA） |
| `train_sft.py` | SFT学習（LoRA、ChatML形式） |
| `orchestrator.py` | R1用オーケストレーター |
| `run_r2_r6.py` | R2〜R6 CPT一括実行 |
| `run_phase1_and_sft.py` | R7/R8 CPT + SFT 11モデル一括実行 |
| `inference.py` | 単一モデル推論 |
| `compare_models.py` | 複数モデル一括比較推論 |
| `generate_stepwise_soap.py` | 段階的SOAPデータ生成 |
| `analyze_evaluation.py` | 評価シート分析 |

## 実験履歴

### CPT（継続事前学習）
全32実験完了。LoRA rank, 学習率, エポック数, alpha/r比率を探索。

**上位モデル（人間評価ベース）:**
| モデル | r | alpha | lr | epochs | CPT loss | 備考 |
|---|---|---|---|---|---|---|
| r8_r128_lr7e5_5ep | 128 | 128 | 7e-5 | 5 | 1.20 | CPT R8ベスト |
| exp4_large_stable | 128 | 128 | 5e-5 | 3 | 1.73 | 知識正確性トップ |
| r6_r64_5ep_aggressive | 64 | 64 | 7e-5 | 5 | 1.57 | カルテsuggestベスト |

**重要な知見:**
- Lossと出力品質は相関しない（loss最低≠品質最高）
- r=128が知識の正確性に最も寄与
- lr=5e-5〜7e-5が安定帯
- 7epochは過学習傾向、5epochが最適
- alpha=rank（比率1.0）が最適。alpha過大は有害

### SFT（Instruction Tuning）
11モデルにSFT実施。データは sft_data_2.jsonl（3,194件）。
SFT設定: r=16, alpha=16, lr=2e-5, 3ep（共通）

**SFT後の改善点:**
- カルテ形式の出力能力が向上（CPT平均~1.5 → SFT平均~3.0）

**SFT後も残る課題:**
- 問診にない検査値の捏造
- ガイドライン引用の不正確さ（ハルシネーション）
- 実用化にはRAG等の事実制約が必要

## 別マシンでのセットアップ

### 1. クローン
```bash
git clone https://github.com/inaka0303/medical_slm.git
cd medical_slm
```

### 2. データの配置
GitHubには含まれないファイル:
- `data/corpus.txt`（240MB、CPT用）→ DGXから scp で転送
- `output/`（学習済みモデル）→ 必要なモデルのみ scp で転送

```bash
# DGXからデータ転送
scp junkanki@<DGX_IP>:/home/junkanki/naka/data/corpus.txt data/
# 必要なモデルだけ転送（例: exp4_large_stable）
scp -r junkanki@<DGX_IP>:/home/junkanki/naka/output/exp4_large_stable/merged output/exp4_large_stable/merged
```

### 3. 依存パッケージ
```bash
pip install unsloth transformers datasets trl jinja2>=3.1.0
```

### 4. 推論テスト
```bash
CUDA_VISIBLE_DEVICES=0 python3 inference.py --model exp4_large_stable --prompt "糖尿病の治療において"
```

## DGXサーバー情報
- ホスト: junkanki-DGX-Station-A100
- GPU: NVIDIA A100-SXM4-80GB × 4台（CUDA 0,1,2,4）+ DGX Display（CUDA 3, 使用不可）
- CUDA index 0,1,2,3 で4台のA100にアクセス可能（GPU3=DGX Displayだがnohup経由では問題なし）
