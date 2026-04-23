# 医療特化SLM プロジェクト

> **最終更新: 2026-04-22（Phase 5 訓練中 / post-process 実装完了 / RAG metadata 改修）**  
> /clear 後はこの CLAUDE.md と `/home/junkanki/naka/results_v6/` を読めば状況復帰できる。
> 作業中のサービス稼働状況は下記「現在のサービス」セクション参照。

## 目的
日本語電子カルテ向け医療特化SLM（Small Language Model）の開発。
メイン機能: 患者の問診データを参照し、カルテ記載時のsuggest（文章候補提示）を行う。

---

## 🔥 2026-04-22 Phase 5 作業ログ（最新）

### 現在バックグラウンドで動いているもの

| PID | プロセス | 期待所要 | 完了後の次アクション |
|---|---|---|---|
| 1389586 | `training_phase5.sh` (4B→9B の v3_clean_r32 再学習x4) | 2.5-4h | orchestrate_phase5_post.sh が引き継ぎ |
| 1392191 | `orchestrate_phase5_post.sh` (pipeline 終了後 eval 自動実行) | 上記完了後 +10分 | `results_v6/eval_v3_vs_v2/` にレポ |

監視コマンド: 
```bash
ps aux | grep -E "training_phase5|orchestrate_phase5" | grep -v grep
tail -f /data2/junkanki/naka/logs/phase5.log
tail -f /data2/junkanki/naka/logs/phase5_post.log
```

### Phase 5 で新たに達成したもの

1. **post-process 実装 (`client.go:cleanModelOutput`)**
   - markdown (`**` `###` `---` `*` `-`) → `■` / `・` / 削除
   - 前置き文（「ご提示いただいた〜」型）除去
   - 補足説明ブロック末尾削除（`---\n**補足説明...**` 型）
   - `（※〜）` 括弧注釈削除
   - AI 自己言及メタコメント（「AIとして」「専門医にご相談」等）削除
   - 作成者フッター削除
   - 8ケースの単体テスト全 PASS (`client_test.go:TestCleanModelOutput`)

2. **合成データ Phase 5 増築**
   - admission: 140件 → **300件**（Phase 5 で +160件）
   - soap_full: 235件 → **395件**（Phase 5 で +160件）
   - 領域追加: 消化器緊急、内分泌緊急、希少緊急、悪性腫瘍合併症、血液、透析、周産期、周術期/ICU、高齢転倒骨折、認知症合併、高齢感染症、DNAR、精神神経、皮膚アレルギー、整形、泌尿器、婦人科、小児、健診事後、循環器呼吸器内分泌外来
   - 残留ノイズ 0% (厳格clean を `merge_synth_v3.py` で適用)
   - 出力: `data/sft_admission_summary_v3.jsonl` / `_v3_clean.jsonl` / `sft_soap_full_v3.jsonl` / `_v3_clean.jsonl`

3. **RAG メタデータ改修（コード変更のみ、DB再構築は未実行）**
   - `build_rag_v2.py` の title 抽出ロジックを強化（『〜』型 > ガイドライン含有行 > line1 fallback）
   - `publication_year` 抽出ロジック追加（タイトル内 + 文書頭「発行/改訂/策定」パターン）
   - `rag_server.py` の Pydantic SearchResult に `publication_year: Optional[int]` 追加
   - `RAGEvidencePanel.tsx` で年度を `（2015年）` 表示
   - **DB再構築は未実行**（1-2時間要、Phase 5 学習と GPU 競合を避けるため後回し）

4. **ノートPC検証手順書**
   - `/home/junkanki/naka/docs/SETUP_LAPTOP.md` 新規作成
   - scp 転送、llama.cpp ビルド(Mac/Linux/Win)、EMR起動、よくあるハマりを網羅
   - 推論速度目安: Apple M2 Pro + Metal で 4B 15-25秒、9B 30-45秒

### Phase 4 → Phase 5 のデータ量変化

| データセット | Phase 4 | Phase 5 | 増加率 |
|---|---|---|---|
| admission 訓練用 (raw) | 140件 | 300件 | 2.1倍 |
| admission clean | 140件 | 300件（残留0%） | 2.1倍 |
| soap_full 訓練用 (raw) | 235件 | 395件 | 1.7倍 |
| soap_full clean | 235件 | 395件（残留0%） | 1.7倍 |

### Phase 5 完了後にやること（orchestrate_phase5_post.sh が自動でやる部分と手動部分）

**自動（orchestrate_phase5_post.sh）:**
- [x] 4B/9B × admission/soap の LoRA 訓練完了待ち
- [x] GGUF 変換 4 件
- [x] llama-server 14 LoRA 構成で restart
- [x] `eval_v3_vs_v2.py` 実行 → v2_r32 (Phase4 本番) vs v3_clean_r32 (Phase5 新) の直接比較
- [x] 結果を `results_v6/eval_v3_vs_v2/summary_*.md` に保存

**次に私（Claude）が起動されたら手動でやること:**
1. `eval_v3_vs_v2.py` の結果を目視 → v3 が上回っていれば:
   - `emr/backend/internal/slm/client.go` の `LoRAAdmissionID = 12` / `LoRASOAPFullID = 13` に更新
   - backend rebuild + restart
   - ブラウザで山本隆 (MRN-0007、2026-04-18 入院) の admission サマリを試して目視確認
2. 9B v3 の比較: 別の llama-server を GPU 1 で port 8083 に立てて、`eval_v3_vs_v2.py` を URL/LoRA_ID 書き換えで再実行
3. `results_v6/eval_v3_vs_v2/discussion_{日付}.md` に所感まとめ
4. 良い結果だったら CLAUDE.md の現状セクション更新
5. （時間あれば）RAG DB 再構築: `python3 /data2/junkanki/naka/build_rag_v2.py` を GPU 1 で実行（1-2時間）

### 現本番 LoRA と新候補 LoRA

| 用途 | Phase 4 本番 | Phase 5 候補 | GGUF |
|---|---|---|---|
| admission 4B | `sft_admission_v2_r32` (100件) | `sft_admission_v3_clean_r32` (300件) | `/data2/junkanki/naka/gguf_models/` |
| soap 4B | `sft_soap_full_v2_r32` (185件) | `sft_soap_full_v3_clean_r32` (395件) | 同上 |
| admission 9B | `sft_admission_9b_v2_r32` (100件) | `sft_admission_9b_v3_clean_r32` (300件) | 同上 |
| soap 9B | `sft_soap_full_9b_v2_r32` (185件) | `sft_soap_full_9b_v3_clean_r32` (395件) | 同上 |

---

## 🔥 2026-04-21 v6フェーズ 大改修まとめ

### アーキテクチャ変更点
1. **LoRA hot-swap 動作確定**: llama.cppの `--prefill-assistant` デフォルト有効、per-request `lora` フィールドで scale切替可能
2. **単一llama-server に 4 LoRA ロード**: suggest / 既存admission / admission_v2 / soap_full_v2 → リクエストで id指定
3. **Assistant Prefill方式採用**: `messages` の末尾を assistant ロールで `S: {ユーザー入力}` とプリフィルし、続きを生成。入力 echo・セクションラベル混入の構造的解消
4. **4セクション カルテUI**: 問診記録 / お薬手帳 / 診察所見 / 検査結果 の縦スタック。医学ワークフローと情報源で分離
5. **RAG サーバー独立稼働**: Python FastAPI (port 8082) で Ruri-v3 + ChromaDB を HTTP 化、EMR backend が proxy
6. **SOAPドラフトDBキャッシュ**: `soap_drafts` テーブルで encounter_id単位キャッシュ、初回9秒 → 2回目以降 0.04秒
7. **SSE セクション逐次ストリーミング**: S→O→A→P をセクション完了ごとにイベント送出

### 新 LoRA（v2、合成データで追加訓練）
| 用途 | 既存件数 | v2件数 | 保存先 |
|---|---|---|---|
| admission_summary | 30 | **100**（＋70合成） | `gguf_models/sft_admission_v2_lora.gguf` |
| soap_full | 40 | **125**（＋85合成） | `gguf_models/sft_soap_full_v2_lora.gguf` |

合成データ（Phase 2 完了分）:
- `/data2/junkanki/naka/data/synth_v1/admission/`  (cardio/resp/neuro/infection/psychiatric、7ファイル)
- `/data2/junkanki/naka/data/synth_v1/soap_full/`   (gynecology/orthopedic/dermatology/ent/urology/pediatric_general、6ファイル)
- マージ済み: `/data2/junkanki/naka/data/sft_admission_summary_v2.jsonl` / `sft_soap_full_v2.jsonl`

Phase 3 進行中（2026-04-21）: admission 消化器緊急 / soap 4section循環器 / soap 4section内分泌 / soap 短文メモ問診 を subagent で合成中。

### 3大バグ解消の経緯（実地テスト済み）
- S「自覚」→「自覚症状自覚症状なし…」重複 ← prefillで解消
- O「血圧146/92」→「…O: 血糖…」ラベル混入 ← prefillで解消
- A「高血圧」→「高血圧高血圧…」重複 ← prefillで解消
- 短文入力時のmeta-commentary「※AIとして…」 ← 後処理で18パターン除去

---

## 現在のサービス（2026-04-23 更新、Phase 5 eval 後の本番構成）

| port | サービス | GPU | VRAM | ロード LoRA |
|---|---|---|---|---|
| 5173 | Vite frontend (React) | - | - | - |
| 8080 | EMR backend (Go/Echo) | - | - | - |
| **8081** | **4B llama-server (suggest + soap + admission fallback)** | GPU 2 | ~4GB | 3 LoRA |
| **8083** | **9B llama-server (admission 専用)** | GPU 3 | ~7GB | 1 LoRA |
| 8082 | RAG server (FastAPI, Ruri-v3) | GPU 1 | ~2GB | - |

### 起動コマンド（2026-04-23 版、3-LoRA + 9B 分離構成）

```bash
# 1. 4B llama-server (3 LoRA のみロード、起動 ~5秒)
cd /data2/junkanki/naka
CUDA_VISIBLE_DEVICES=2 nohup llama.cpp/build/bin/llama-server \
  -m gguf_models/Qwen3.5-4B-UD-Q4_K_XL.gguf \
  --lora gguf_models/sft_4b_nocpt_A_lora.gguf \
  --lora gguf_models/sft_soap_full_v2_r64_lora.gguf \
  --lora gguf_models/sft_admission_v2_r32_lora.gguf \
  --port 8081 -ngl 99 \
  --chat-template-kwargs '{"enable_thinking":false}' \
  > /data2/junkanki/naka/logs/llama_server_slim.log 2>&1 &

# 2. 9B llama-server (admission 専用)
CUDA_VISIBLE_DEVICES=3 nohup llama.cpp/build/bin/llama-server \
  -m gguf_models/Qwen3.5-9B-UD-Q4_K_XL.gguf \
  --lora gguf_models/sft_admission_9b_v3_clean_r32_lora.gguf \
  --port 8083 -ngl 99 \
  --chat-template-kwargs '{"enable_thinking":false}' \
  > /data2/junkanki/naka/logs/llama_server_9b_admission.log 2>&1 &

# 3. RAG server (Python)
CUDA_VISIBLE_DEVICES=1 HF_HOME=/data2/junkanki/.cache/huggingface \
  nohup python3.11 /data2/junkanki/naka/rag_server.py --port 8082 --host 127.0.0.1 \
  > /data2/junkanki/naka/logs/rag_server.log 2>&1 &

# 4. EMR backend (Go) — 両方の SLM サーバーを env で指定
cd /home/junkanki/naka/emr/backend
export PATH=/data2/junkanki/go/bin:$PATH GOROOT=/data2/junkanki/go
go build -o /tmp/emr-server ./cmd/server/
SLM_API_URL=http://localhost:8081 \
SLM_ADMISSION_URL=http://localhost:8083 \
  nohup /tmp/emr-server > /data2/junkanki/naka/logs/emr_backend.log 2>&1 &

# 5. Vite frontend
cd /home/junkanki/naka/emr/frontend
nohup npm run dev -- --host 0.0.0.0 --port 5173 \
  > /data2/junkanki/naka/logs/vite_dev.log 2>&1 &
```

### LoRA ID マッピング（本番 3+1 構成、2026-04-23 確定）

**port 8081 (4B):**
```
id 0: sft_4b_nocpt_A_lora            ← suggest/SOAPストリーミング(4-call)
id 1: sft_soap_full_v2_r64_lora      ← SOAP全体 単一呼出 (Phase5 eval best, md=68)
id 2: sft_admission_v2_r32_lora      ← admission 4B fallback (9B未接続時のみ)
```

**port 8083 (9B):**
```
id 0: sft_admission_9b_v3_clean_r32_lora  ← admission 本番 (Phase5 eval md=87 最良)
```

**fallback 動作:** 9B が未接続/死亡時、admission は 4B (id=2) で自動生成、レスポンスに `server:"4B-fallback"` が入り frontend が警告バー表示。9B 復帰は backgroundHealthCheck (60秒間隔) が検知して自動切替。

**旧 14-LoRA 構成からの変更理由 (2026-04-23):**
eval 用に積んでいた 11 個の比較用 LoRA (v2_r16, v2_r64 admission, v2p4, v2_clean 各種, v3_clean) は本番で使わないため撤去。VRAM ~900MB 節約、起動時間 20秒→5秒。比較再評価が必要なら一時的に 14-LoRA 構成で起動可。

### LoRA ID マッピング（旧 14-LoRA 構成、参考）
```
id 0: sft_4b_nocpt_A (suggest)          ← インライン補完、SOAPドラフト(4回呼出)
id 1: sft_admission_summary_4b (旧)      ← 比較用、本番非使用
id 2: sft_admission_v2 (新100件訓練)     ← 入院時サマリ 本番候補
id 3: sft_soap_full_v2 (新125件訓練)     ← SOAP全体 本番候補（suggest 4回と比較中）
```

### アプリの主要エンドポイント（EMR backend）
```
# 問診（4セクション対応、upsert）
GET  /api/encounters/:id/interviews       → raw_text/medication_list/exam_findings/lab_results
POST /api/encounters/:id/interviews       → 4フィールド受信、1 encounter = 1 note

# SOAP ドラフト（DB キャッシュ + SSE）
POST /api/encounters/:id/soap-draft       → キャッシュ優先、force:true で再生成
POST /api/encounters/:id/soap-draft/stream → SSE、S→O→A→P逐次
DELETE /api/encounters/:id/soap-draft     → キャッシュ無効化

# 入院時サマリ（DB 永続化）
GET/POST /api/encounters/:id/admission-summary

# インライン補完（suggest LoRA、prefill方式）
POST /api/slm/autocomplete                → {text, context, interview_text, prior_sections}

# RAG
POST /api/rag/search                      → Ruri-v3 で 検索、title + 引用文

# デモ用リセット
POST /api/test-patient/reset              → MRN-0021 (新規太郎) のみ削除、毎回ブラウザリロードで自動実行
```

### カルテUIの4セクション構造（2026-04-21 新設計）
医学ワークフローと情報源で分離:
- **問診記録**: 患者から聞く（主訴・現病歴・既往・家族歴・社会歴・アレルギー）
- **お薬手帳**: 持参薬の正確な薬名・用量
- **診察所見**: 医師の視触聴診
- **検査結果**: バイタル、採血、画像

バックエンドは 4フィールドを `【問診記録】...【お薬手帳より】...` 形式に結合して SLM に渡す（訓練データ形式と一致）。

---

## ベースモデル
- `unsloth/Qwen3.5-0.8B-Base`, `2B-Base`, `4B-Base`, `9B-Base`
- 4B/9Bが主力。0.8B/2Bは小モデルの限界検証用

## ベースモデル
- `unsloth/Qwen3.5-0.8B-Base`, `2B-Base`, `4B-Base`, `9B-Base`
- 4B/9Bが主力。0.8B/2Bは小モデルの限界検証用

## アーキテクチャ
```
ノートPC上の最終構成:
  Qwen3.5-4B GGUF (Q4_K_XL, 2.8GB) ← 常駐
    + suggestアダプター (82MB)     ← カルテ記載タスク
    + RAG (Ruri-v3 + ChromaDB)     ← 知識/ガイドライン検索
  
  llama-server (localhost:8081)    ← ローカルAPIサーバー
    --chat-template-kwargs '{"enable_thinking": false}'
```

## 学習パイプライン
1. **CPT（継続事前学習）**: 医療コーパスでLoRA学習 → `train_unsloth_cpt.py`
2. **SFT（Instruction Tuning）**: LoRAで指示追従学習 → `train_sft.py`
3. **GGUF変換**: LoRAアダプターをGGUF形式に変換 → llama.cpp `convert_lora_to_gguf.py`

## ディレクトリ構成

### /home/junkanki/naka/（gitリポジトリ）
```
data/
  corpus.txt              # CPT用コーパス（ガイドライン+カルテ, 318MB, 2658文書）
  sft_suggest.jsonl        # suggestタスク特化データ（512件, 8診療科×64シナリオ×8カットポイント）
  sft_data_2.jsonl         # 汎用SFTデータ（3,194件, ガイドラインQ&A中心）
  sft_soap_stepwise.jsonl  # 段階的SOAPデータ（120件, 15シナリオ×8パターン）
  rag_eval_qa.jsonl        # RAG評価用QAデータ（100問, ガイドラインから作成）
  mix_A_suggest_only.jsonl # データA: suggest512件のみ
  mix_B_suggest_soap.jsonl # データB: suggest512+stepwise120=632件

results_v2/    # v2実験結果（24モデル×8問）
results_v3/    # v3実験結果（22モデル×8問）
results_v4/    # v4実験結果（33モデル×23問）
results_v5/    # v5実験結果（RAGグリッドサーチ+SOAP SFT+GGUF+RAG E2E）
eval_prompts_by_task.json  # suggestタスク評価プロンプト（17問+模範解答）
```

### /data2/junkanki/naka/（メインワークスペース）
```
output/        # 学習済みモデル（各実験名/merged/ と /lora/）
gguf_models/   # GGUFベース + LoRAアダプター（変換済み）
rag_db_v2/     # RAGベクトルDB（ChromaDB, Ruri-v3-310m）
logs/          # 学習・推論ログ
```

## 主要スクリプト
| ファイル | 用途 | 場所 |
|---|---|---|
| `train_unsloth_cpt.py` | CPT学習（LoRA, --model_name で4B/9B対応） | /data2 |
| `train_sft.py` | SFT学習（LoRA, --sft_data でデータ切替） | /data2 |
| `infer_v4.py` | タスク別評価推論（--task suggest/knowledge/all） | /data2 |
| `build_rag_v2.py` | RAG DB構築（Parent-Child + Ruri-v3） | /data2 |
| `rag_grid_search.py` | RAGパラメータグリッドサーチ | /data2 |
| `rag_e2e_eval.py` | RAG+SLMエンドツーエンド評価 | /data2 |
| `gguf_lora_eval.py` | GGUF+LoRA推論テスト | /data2 |
| `measure_hallucination.py` | ハルシネーション定量計測 | /home |
| `orchestrator_v2〜v5.py` | 各フェーズの自動実行制御 | /data2 |

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

### suggestアダプター最終結果

4B/9Bのsuggestタスク（途中→続き、S/O/A/P各セクション記載）に特化したLoRAアダプター。
v2〜v5で70+実験を実施し、以下が現時点のベスト:

| サイズ | ベストアダプター | 設定 | データ | GGUF変換 |
|--------|-----------------|------|--------|---------|
| 4B | sft_4b_nocpt_A | r=16, lr=2e-5, 5ep | データA (suggest 512件) | ✅済 |
| 9B | sft_9b_nocpt_ep8 | r=16, lr=2e-5, 8ep | データA (suggest 512件) | ✅済 |

**確立した知見:**
- 4B/9BではCPTは不要（noCPTが最安定。控えめCPT r=16,lr=1e-5,2epでも改善なし）
- データA(suggest512件)で十分。stepwise120件の追加効果はsuggestタスクでは限定的
- r=16が安定。r=32はloss最低だがSOAP構造を完走しない傾向
- lr=2e-5が最適。lr=1e-5は学習不足、lr=5e-5は差なし
- 4Bは5ep、9Bは8epが最適
- Lossと出力品質は相関しない（CPTと同じ傾向がSFTでも確認）
- P記載で4Bは架空薬剤名を生成する → RAGで解決済み
- 9Bは全タスクで実用レベル（P記載も実在薬で出力、ただしGGUFでやや精度低下）
- SOAP全体生成は別アダプター（別データ）が必要（今後の課題）

### RAG（検索拡張生成）

**構成:** Parent-Child Retriever + Ruri-v3-310m + ChromaDB

```
コーパス(2658文書) → Parent(1500文字)に分割 → Child(400文字)にさらに分割
                                                  ↓ Ruri-v3でEmbedding
クエリ → Ruri-v3 Embedding → Childで類似検索(精度高い)
                              → ヒットしたChildの親Parent(文脈広い)をLLMに渡す
```

**最適パラメータ:** (32設定のグリッドサーチで確定)
| パラメータ | 値 | 備考 |
|-----------|-----|------|
| Child chunk size | 400文字 | 検索精度用の小チャンク |
| Parent chunk size | 1500文字 | LLMに渡す大チャンク |
| n_parent | 5 | 返却するParent数 |
| Embedding | Ruri-v3-310m | 日本語特化, 768次元 |
| Recall@5 | **0.970 (97/100)** | ガイドラインQA100問での検索精度 |

**エンドツーエンド評価結果:**

| モデル | RAGなし正答率 | RAGあり正答率 | 改善幅 |
|--------|-------------|-------------|--------|
| **4B** | 75% (75/100) | **92% (92/100)** | **+17pt** |
| **9B** | 77% (77/100) | **95% (95/100)** | **+18pt** |

カテゴリ別（9B RAGあり）:
- 治療方針: **100%** (30/30)
- 薬剤・用量: **100%** (20/20)
- 診断基準: **100%** (20/20)
- 疫学・病態: 73%
- その他: 93%

**P記載のハルシネーション:** RAGあり9Bで実在薬のみ出力（カプトプリル、カンデサルタン、カルベジロール、ダパグリフロジン）

### GGUF量子化 + LoRA推論

**構成:** 公開GGUF (unsloth) + 学習済みLoRA → llama-server (API)

| 項目 | 4B GGUF Q4_K_XL | 9B GGUF Q4_K_XL |
|------|-----------------|-----------------|
| ファイルサイズ | 2.8GB | 5.6GB |
| LoRAサイズ | 82MB | 112MB |
| 推論速度 (H100) | 1.7s/問 | 2.0s/問 |
| 推論速度 (API) | 1.2s/問 | 1.1s/問 |
| S/O/A記載品質 | ◎ 16bitと同等 | ◎ 16bitと同等 |
| P記載（薬剤名） | △ 架空薬あり→RAG必須 | △ GGUFでやや精度低下→RAG必須 |
| Thinking問題 | `enable_thinking:false`で解決 | 同左 |

**推論方法:**
```bash
# llama-serverでローカルAPIサーバー起動（外部通信なし、完全ローカル）
llama-server -m Qwen3.5-4B-UD-Q4_K_XL.gguf \
  --lora sft_4b_nocpt_A_lora.gguf \
  --port 8081 -ngl 99 \
  --chat-template-kwargs '{"enable_thinking": false}'

# APIで推論
curl http://localhost:8081/v1/chat/completions \
  -d '{"messages":[{"role":"user","content":"..."}]}'
```

### モデルサイズ別の最終評価

| サイズ | suggestタスク | 知識タスク | CPT効果 | ノートPC速度 | 推奨用途 |
|--------|-------------|-----------|---------|------------|---------|
| 0.8B | △ 反復ループ多発 | ✗ | 必要 | 超サクサク | 非推奨 |
| 2B | ○ CPT+SFTで使える | △ | 効果あり | 超サクサク | タスク特化なら可 |
| **4B** | **◎ S/O/A実用的** | ○ RAGで補完 | 不要 | **サクサク** | **ノートPC推奨** |
| **9B** | **◎ 全タスク最高** | ◎ | 不要 | 許容範囲 | 品質最優先時 |

### SOAP全体アダプター + 入院時サマリアダプター（進行中）

suggestアダプター（途中→続き）とは別に、SOAP全体出力と入院時サマリ生成用のアダプターを学習。

| アダプター | データ | 件数 | 4B | 9B |
|-----------|--------|------|-----|-----|
| sft_soap_full | 問診→SOAP全文 | 40 | ✅完了 | ✅学習中(GPU0) |
| sft_admission_summary | 詳細問診→入院時サマリ | 30 | ✅完了+GGUF済 | ✅完了+GGUF済 |

**注意:** データ件数がまだ少ない（40件/30件）。品質確認後、追加生成が必要かもしれない。

### EMRアプリ統合（完了）

EMRアプリ (https://github.com/inaka0303/emr.git) のSLM接続を実装済み。

| API | エンドポイント | 状態 | レスポンス |
|-----|-------------|------|-----------|
| autocomplete | POST /api/slm/autocomplete | ✅ SLM接続済み | 500ms |
| SOAP suggest | POST /api/slm/suggest/soap | ✅ SLM接続済み | ~5秒 |
| Summary | POST /api/slm/suggest/summary | ✅ SLM接続済み | 450-780ms |
| Health | GET /api/slm/health | ✅ | - |

実装ファイル:
- `emr/backend/internal/slm/autocomplete.go` — SLM接続+モック辞書フォールバック
- `emr/backend/internal/slm/client.go` — OpenAI互換APIクライアント
- `emr/backend/internal/slm/parser.go` — SOAP/Summary自然文パーサー
- `emr/backend/internal/slm/client_compat.go` — callChatCompletion互換ラッパー

### 今後の課題
- **SOAP全体/サマリアダプターの品質評価** — SFT完了済みだが推論品質の確認がまだ
- **データ拡充** — SOAP全体40件/サマリ30件は少なめ。品質次第で追加生成
- **ノートPC実測** — 4B GGUF+LoRA+RAGの統合動作確認
- **RAGの高度化** — リランキング、HyDE等の追加テクニック
- **アプリのフロントエンドテスト** — ブラウザでの実際の操作確認
- **評価の拡充** — 医療者による人手評価
- **論文化** — スケーリング比較、RAG効果、CPT効果のデータが揃っている

## 次のセッションへの引き継ぎ

### 環境の起動方法

```bash
# 1. llama-server起動（SLMのローカルAPIサーバー）
cd /data2/junkanki/naka
CUDA_VISIBLE_DEVICES=2 llama.cpp/build/bin/llama-server \
  -m gguf_models/Qwen3.5-4B-UD-Q4_K_XL.gguf \
  --lora gguf_models/sft_4b_nocpt_A_lora.gguf \
  --port 8081 -ngl 99 \
  --chat-template-kwargs '{"enable_thinking": false}'

# 2. EMR backend起動
export PATH=/data2/junkanki/go/bin:$PATH
export GOROOT=/data2/junkanki/go
cd /home/junkanki/naka/emr/backend
SLM_API_URL=http://localhost:8081 go run ./cmd/server/

# 3. SFT学習を走らせる場合
cd /data2/junkanki/naka
HF_HOME=/data2/junkanki/.cache/huggingface \
CUDA_VISIBLE_DEVICES=0 python3.11 train_sft.py \
  --base_model unsloth/Qwen3.5-4B-Base \
  --exp_name <実験名> \
  --sft_data data/<データファイル>.jsonl \
  --lora_r 16 --lora_alpha 16 --lr 2e-5 --epochs 5 \
  --batch_size 2 --grad_accum 16
```

### 作業のコツ

1. **python3.11を使う**（python3はシステムの3.10でunslothが動かない）
2. **HF_HOME=/data2/junkanki/.cache/huggingface を必ず設定**（/homeが満杯のため）
3. **ログは /data2/junkanki/naka/logs/ に出す**（/tmpは危険）
4. **GPU 4枚あるが共用マシン**。全GPU独占は避け、一部を空ける
5. **gitはSSH経由** — `git@github-inaka:inaka0303/emr.git`（~/.ssh/configで設定済み）
6. **Go 1.23+が必要** — `/data2/junkanki/go/bin/go` を使う（システムのgoは1.20で古い）
7. **Qwen3.5はVLM**（ビジョン言語モデル）なので推論時に注意:
   - unslothでの推論: `tokenizer(None, input_text, ...)` とNoneを渡す
   - messagesのcontent: `[{"type":"text","text":"..."}]` 形式
   - GGUFでのthinking: `--chat-template-kwargs '{"enable_thinking":false}'` 必須

### 実験結果の場所

| フォルダ | 内容 |
|---------|------|
| `/home/junkanki/naka/results_v2/` | 初回24モデル比較（v2、JSONにメタデータ付き） |
| `/home/junkanki/naka/results_v3/` | 2B CPT + 控えめCPT + アダプター（JSONにメタデータ付き） |
| `/home/junkanki/naka/results_v4/` | v4全33モデル × 23問推論（JSONにメタデータ付き） |
| `/home/junkanki/naka/results_v5/` | RAGグリッドサーチ + GGUF比較 + RAG E2E + SOAP SFT探索 |
| `/home/junkanki/naka/data/sft_datasets/` | SFT学習データ一覧 |
| `/home/junkanki/naka/data/eval_data/` | 評価用データ（プロンプト + RAG QA） |

### GGUFアダプター一覧

```
/data2/junkanki/naka/gguf_models/
├── Qwen3.5-4B-UD-Q4_K_XL.gguf          (2.8GB) ← 4Bベース
├── Qwen3.5-9B-UD-Q4_K_XL.gguf          (5.6GB) ← 9Bベース
├── sft_4b_nocpt_A_lora.gguf             (82MB)  ← 4B suggestベスト★
├── sft_9b_nocpt_ep8_lora.gguf           (112MB) ← 9B suggestベスト★
├── adapter_4b_soap_lora.gguf            (82MB)  ← 4B SOAP(データB)
├── sft_admission_summary_4b_lora.gguf   (82MB)  ← 4B 入院時サマリ
├── sft_admission_summary_9b_lora.gguf   (112MB) ← 9B 入院時サマリ
├── sft_soap_full_4b_lora.gguf           (予定)  ← 4B SOAP全体
└── sft_soap_full_9b_lora.gguf           (予定)  ← 9B SOAP全体
```

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

## サーバー情報

### H100サーバー (gsv-h100) — メイン開発環境
- ホスト: gsv-h100
- GPU: NVIDIA H100 NVL × 4台（各95GB VRAM）
- CUDA: 12.8, PyTorch: 2.10.0
- Python: 3.11（unsloth用）、3.10（システム）
- ストレージ:
  - `/home` (397GB): ほぼ満杯。**大きいファイルを置かない**
  - `/data2` (3.5TB NVMe): **メインワークスペース** `/data2/junkanki/naka/`
  - `/` (480GB): `/tmp`を含む。**一時ファイルに注意（後述）**
- HuggingFaceキャッシュ: `/data2/junkanki/.cache/huggingface`（HF_HOME環境変数で指定）
- llama.cpp: `/data2/junkanki/naka/llama.cpp/`（CUDA対応ビルド済み）
- GGUFモデル: `/data2/junkanki/naka/gguf_models/`

### DGXサーバー (junkanki-DGX-Station-A100) — 旧環境
- GPU: NVIDIA A100-SXM4-80GB × 4台
- CUDA index 0,1,2,3 で4台のA100にアクセス可能

## ⚠️ 安全ルール（インシデント対策）

### ディスク容量に関するルール

**背景:** llama.cppのテスト時にログファイルが301GBに膨張し、`/`パーティションが満杯になるインシデントが発生した（2026-04-16）。

1. **`/tmp`や`/`配下にログをリダイレクトしない**
   - `/tmp`は`/`パーティション上にある（480GB共有）
   - ログ出力先は必ず `/data2/junkanki/naka/logs/` を使う
   ```bash
   # ❌ 危険
   nohup command > /tmp/test.log 2>&1 &
   # ✅ 安全
   nohup command > /data2/junkanki/naka/logs/test.log 2>&1 &
   ```

2. **llama.cppは`llama-completion`を使う（`llama-cli`ではない）**
   - `llama-cli`はデフォルトで対話モード → 無限生成 → ログ爆発
   - `llama-completion`はワンショットで終了する
   ```bash
   # ❌ 対話モード（無限ループ）
   llama.cpp/build/bin/llama-cli -m model.gguf ...
   # ✅ ワンショット
   llama.cpp/build/bin/llama-completion -m model.gguf -n 128 ...
   ```

3. **バックグラウンドプロセスは必ず管理する**
   - 起動時にPIDを記録
   - テスト完了後は即座にkill
   - `ps aux | grep python3.11` で残留プロセスを確認
   - 長時間放置するプロセスには `timeout` コマンドを付ける

4. **ファイル削除後もディスクが空かない場合**
   - プロセスがファイルを掴んでいる可能性がある
   - `lsof +L1 | grep deleted` で確認し、該当プロセスをkill

5. **定期的にディスク容量を確認**
   ```bash
   df -h / /home /data2
   ```
