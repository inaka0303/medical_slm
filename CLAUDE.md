# 医療特化SLM プロジェクト

> **最終更新: 2026-04-27（次タスク候補議論 - 着手前、コード変更なし）**  
> /clear 後はこの CLAUDE.md と `/home/junkanki/naka/results_v6/` および `docs/M3_FIELD_NOTES.md` を読めば状況復帰できる。
> 作業中のサービス稼働状況は下記「現在のサービス」セクション参照。

## 🚦 2026-04-27 引き継ぎメモ（/clear 後はここから読む）

### 現状

- **コード変更なし**。2026-04-24 に実装した 5 commits (emr 77cf96d..7c7bbb2) + 1 commit (medical_slm dd16104) で push 済、両 GitHub に反映済。
- **稼働サービス確認済**: 4 月 24 日起動した llama-server / emr-server / RAG / vite が 3 日間ずっと走っている (PID 2629395 など)。
- **/home が 99% 使用** (7.5G 残)、`/data2` 89% (415G 残)。`/` は 38% で余裕。
  - 危険水域なので新たに大きいログファイル / モデル成果物を `/home` に出さないこと。
- **llama-server LCP cache** は 3 日アイドルなので LRU で多くのエントリが落ちている可能性あり。次回作業時は `scripts/warmup_demo.sh` を再実行して予熱推奨。

### 議論中: 次に着手するタスク (論文関連は除外、優先順)

ユーザーが "論文検討以外の次のタスクは？" と尋ねた回答として 6 候補提示済み:

| # | タスク | 所要 | 依存 | 価値 |
|---|---|---|---|---|
| **A** | **frontend SSE 再接続 UI** | 1-2h | H100 のみ | 2026-04-24 backend SSE fix を UX として完成。S 編集後に自動 GET /soap-draft で O/A/P 取得する動線 |
| **B** | **短入力 SFT データ合成 (degeneration 根本解決)** | 一晩 subagent | H100 | meta-filter で糊塗した問題を訓練側で根本解決 |
| **C** | **SOAP 4B LoRA 再訓練 (薬剤グラウンド強化)** | ~1h GPU | H100 | 4B 薬剤ハルシネ (アプレキサン等) 根絶。RAG 部分改善に上乗せ |
| **D** | **デモ台本 + 安全患者リスト明文化** (`docs/demo_script.md`) | 30min-1h | - | 学会本番用。音声花子=確実、山本隆=限界提示など |
| **E** | **M3 実機での効果検証** | 1-2h | **M3 + 先生が M3 触れる** | 2026-04-24 改善が現場体感でどれだけ効くか |
| **F** | **RAG DB 再構築 (title/year 改良反映)** | 1-2h GPU | H100 | build_rag_v2.py コード改良済、DB 再構築は未実行 |

### 現時点の推奨 (2026-04-24 時点で提示済)

1. **A (frontend SSE 再接続 UI) を先に**: 今日の SSE fix が backend だけで止まっておりUX 未完成。1-2h で完結し、デモ時に S 却下→O/A/P 消失の再発を防げる。
2. **次に B (短入力 SFT データ合成)**: 夜間 subagent で走らせる案。今日の meta-filter は「empty 返却」という消極的対処、訓練で根本解決すれば「短くても妥当な続き」を出せる。

**ユーザーがどれから着手するかまだ未決定**。次回 /clear 後はこの選択をユーザーに確認するところから。

### サービス再開チェックリスト（必要な場合のみ）

- [ ] 全 5 ポート (8080/8081/8082/8083/5173) 疎通確認 → `ss -tlnp | grep -E ":808[0-9]|:5173"`
- [ ] emr-server バイナリは `/tmp/emr-server-v2` のまま（再起動するなら `cd emr/backend && go build -o /tmp/emr-server-v2 ./cmd/server/`）
- [ ] llama-server LCP cache 予熱: `/home/junkanki/naka/scripts/warmup_demo.sh`

---

## 目的
日本語電子カルテ向け医療特化SLM（Small Language Model）の開発。
メイン機能: 患者の問診データを参照し、カルテ記載時のsuggest（文章候補提示）を行う。

---

## 🚀 配布アーティファクト（2026-04-23 から）

ノートPC や別マシンで動かすための一式は **Hugging Face Hub** に置いてある:

| repo | 種別 | 内容 |
|---|---|---|
| `inaka0303/medical-slm-loras` | model (private) | 4B 用 3 LoRA: suggest / soap_v2_r64 / admission_v2_r32_fallback |
| `inaka0303/medical-slm-rag-db` | dataset (private) | RAG DB (rag_db_v2.tar.gz, 7.5GB 展開後) |
| `unsloth/Qwen3.5-4B-GGUF` | model (public) | ベース (`Qwen3.5-4B-UD-Q4_K_XL.gguf`, 2.8GB) |

ノートPC セットアップ手順: `docs/SETUP_LAPTOP.md`

9B admission GGUF (`sft_admission_9b_v3_clean_r32_lora.gguf`, 112MB) は H100 ローカル運用のみ
（HF にも上げてないので Tier 2 環境を別途用意する場合は scp で転送）。

---

## 🔥 2026-04-24 本日の作業ログ（最新、/clear 後はここから読む）

### M3 field notes (2026-04-23) の ⭐⭐⭐ 即効策を backend 側で実装

#### A. backend/internal/slm/client.go & autocomplete.go
1. **`ChatCompletionRequest` に `RepeatPenalty` 追加**（1.1 固定、degeneration 対策）
   - 効果: 新規太郎型の A/P 反復ループ解消（`急性冠症候群、胸膜炎、心筋梗塞、胸膜炎...` 無限）
2. **autocomplete timeout 15s → 30s**、`max_tokens` 128→48 (A は 96、O は 64)、`temperature` 0.5→0.3
3. **cleanModelOutput 複数行丸括弧メタブロック削除** (`reMetaParenBlock`)
   - 池田里奈型「（問診記録の冒頭にある「自覚症状なし」をそのまま記載するのが適切です。電子カルテでは…）」全削除
4. **autocomplete meta-filter v2**
   - `strongMetaSignatures` + 短入力＋冒頭 `「` 検出 → empty 返却
   - 「動悸」「胸痛」等の短入力時、以前は `「動悸」が主訴として記録されましたね■ パターン1:` のメタ説明を返していたが、現在は empty で正しく補完候補無し扱い

#### B. llama-server に `-fa on -ctk q4_0 -ctv q4_0` 追加（両サーバー）
- KV cache が K+V 合計 2.3 GB に圧縮（以前 ~9 GB）
- flash attention で v-cache 量子化を可能化（必須）
- H100 でも quality 影響は無視できる程度と判断して本番適用
- M3 (Tier 1) でのメモリ余裕確保が主目的、H100 は consistency のみ

#### C. warmup script `/home/junkanki/naka/scripts/warmup_demo.sh`
- デモ患者 (MRN 0022/0021/0020/0010/0007) × autocomplete を一発ずつ撃って LCP cache 予熱
- H100 実測: 2 回目以降の同 patient autocomplete が 839ms → 500ms (約 40% 短縮)
- M3 想定効果: 6-9 秒 → 1 秒以下（field notes の仮説どおり）
- 起動シーケンス末尾に追加（`start_all.sh` 相当）

#### D. emr-server v2 binary にスワップ完了
- `/tmp/emr-server-v2` (16.6 MB) で稼働中
- 既存 18 テストケース + 新規 2 (池田里奈型メタ括弧) = **20/20 PASS**

### 事実確認: llama.cpp LCP prompt cache
- 実装: `tools/server/server-context.cpp:963-1007` (実在機能)
- default: `common/common.h:632` で `slot_prompt_similarity = 0.1f` = **閾値 10%**
- 3 層構造:
  1. per-slot KV cache + `cache_prompt=true` default で前回リクエストとの prefix 自動再利用
  2. `server_prompt_cache` が 8 GB までスロット evict 時の state を保存
  3. `slot_prompt_similarity` で複数スロット間の最適選択
- 本番は `--parallel` 未指定なので slot=1。「前回 prompt との prefix 一致」が実質の cache hit 条件。

### 追加実装完了（同日午後）

5. **SSE キャンセル副作用修正** ✅ (⭐⭐⭐ アーキ)
   - `soap_draft.go StreamGenerate` で clientCtx と genCtx を分離
   - client disconnect で generation は継続、完了時に DB キャッシュ保存
   - frontend が再接続すれば `GET /api/encounters/:id/soap-draft` でキャッシュ取得可能
2. **SOAP 単発呼出 parse 安定化** ✅ (⭐⭐⭐ アーキ)
   - 根本原因: `■ S` が `■ SOAP 形式カルテ記載案` と誤マッチ / `■ 【S - Subjective】` 形式未対応
   - fix: (a) `■ SOAP` 等の skipHeaderPrefixes で章見出し行を skip
     (b) `■ 【S - Subjective】` / `■ 【S】` / `■ 【S：` 等の marker 追加
     (c) bare-letter marker (`■ S`, `S:`) は完全一致 check を先行
   - 効果: **22s → 13s** (fallback 回避で 40% 短縮)、raw_preview log 追加
   - 新テスト 6 ケース全 PASS (`parser_test.go`)
3. **RAG 自動注入** ✅ (⭐⭐ アーキ)
   - `slm/rag_client.go` 新規、`Client.SetRAGClient()` で有効化
   - `GenerateSOAP` + `GenerateAdmissionSummary` 時に interview を query として RAG 叩く
   - 上位 3 件を `【参考ガイドライン】` ブロックとして system prompt に注入
   - overhead: RAG 呼出 ~250-400ms + prompt 拡大で +1s 程度
   - 効果限定的: CHA2DS2-VASc スコア計算などは正確化したが 4B の薬剤ハルシネーションは残存
   - 環境変数: `RAG_API_URL` (default http://localhost:8082), `RAG_API_URL=` で明示無効化
4. **Cross-encounter 要約レイヤー** ✅ scaffold 実装 (⭐⭐ アーキ)
   - `service/patient_history.go` 新規 `PatientHistoryService`
   - `BuildCrossEncounterSummary` rule-based 実装: 直近 5 encounter × date+dept+主訴+A+P 要約
   - SOAP / SSE handler で `prependCrossEncounterHistory` 経由で interview に prepend
   - 環境変数: `ENABLE_CROSS_ENCOUNTER_SUMMARY=false` で無効化
   - TODO (本番化): LoRA 要約モデル訓練、薬剤履歴トラッキング、診療科横断

### 未着手（次回 /clear 後ここから）

- **要約 LoRA 訓練**: 現状 rule-based の cross-encounter 要約を LoRA summarization に置換
- **M3 実機での効果検証**: 今日の変更が M3 上でどれだけ体感改善するか測定
  - 特に LCP warmup 後の autocomplete 2 回目以降の latency
  - SOAP 単発呼出 parse 成功率 (fallback 発動率)
  - 短入力メタ化が empty 返却でどう UX に現れるか（"候補無し" 状態が許容可能か）
- **4B 薬剤ハルシネーション完全解決**: RAG 注入で部分改善したが 4B は依然として架空薬名を生成
  - 選択肢: (a) 9B に SOAP も移行 (b) soap LoRA 再訓練で薬剤グラウンド強化
- **論文方針議論の再開**: 2026-04-23 夜に中断した Nature Sci Data vs 2 本立ての分岐判断
- **frontend 側の SSE 再接続ロジック**: backend は切断耐性を付けたが、frontend が S 編集後に自動で cache を fetch する動線が必要

### コード変更ファイル (2026-04-24 分)

```
emr/backend/internal/slm/client.go          (ChatCompletionRequest.RepeatPenalty, SetRAGClient, cleanModelOutput 拡張)
emr/backend/internal/slm/autocomplete.go    (timeout 30s, max_tokens 48, meta-filter v2, 池田里奈/動悸型対応)
emr/backend/internal/slm/parser.go          (■ 【S - Subjective】 対応, ■ SOAP skip, bare-letter 完全一致)
emr/backend/internal/slm/rag_client.go      (新規)
emr/backend/internal/slm/client_test.go     (池田里奈メタ括弧 2 ケース追加)
emr/backend/internal/slm/parser_test.go     (新規 6 ケース)
emr/backend/internal/handler/soap_draft.go  (SSE context decouple, cross-encounter prepend)
emr/backend/internal/service/patient_history.go (新規)
emr/backend/cmd/server/main.go              (RAG + historySvc wiring)
```

---

## 🔥 2026-04-23 の作業ログ

### 完了したこと（**主要マイルストーン**）

#### A. Phase 5 完了 → ベスト LoRA 確定
全 18 条件評価（4B/9B × admission/soap × 6+3 variants × 3 cases）→ `results_v6/eval_all_models/summary_1776927344.md`

| タスク | 4B ベスト | 9B ベスト | **本番採用** |
|---|---|---|---|
| **admission** | v2p4_r16 (md=141) | **v3_clean_r32 (md=87)** | **9B v3_clean_r32** ⭐ |
| **soap** | **v2_r64 (md=68)** ⭐ | v2_r32 (md=88) | **4B v2_r64** ⭐ |
| **suggest** | nocpt_A | nocpt_ep8 | **4B nocpt_A** (UX上速度優先) |

主要知見:
- **タスク依存サイズ効果**: admission は 9B 明確勝、soap は 4B が逆転勝（9B の薬剤ハルシネーション増）
- **データ量プラトー**: soap は 185→395件で改善せず、データ質>量の事例
- **rank 効果**: 4B soap で r=64 が r=32/16 圧勝（-17% md）

#### B. 本番 3+1 LoRA 構成への切替
- `port 8081` (4B): 14 LoRA → **3 LoRA に削減**（VRAM ~900MB節約、起動 20s→5s）
  - id 0: `sft_4b_nocpt_A`（suggest / SOAPストリーミング 4-call）
  - id 1: `sft_soap_full_v2_r64_lora`（SOAP 全体 単一呼出）★
  - id 2: `sft_admission_v2_r32_lora`（admission 4B fallback）
- `port 8083` (9B): **新設、admission 専用サーバー**
  - id 0: `sft_admission_9b_v3_clean_r32_lora` ★
- `setActiveLoRA` の **nLoras ハードコード bug 修正**（動的化）
- backend env: `SLM_API_URL=http://localhost:8081` + `SLM_ADMISSION_URL=http://localhost:8083`

#### C. EMR backend 改修（emr リポ commit `55a2c05`）
- `Client.SetAdmissionServer()` 追加 → admission を別 URL にルーティング
- 9B 呼出失敗時に 4B fallback へ即 retry（`backgroundHealthCheck` 60s を待たず）
- `AdmissionSummary` に `Server` field 追加（`"9B"` / `"4B-fallback"`）
- frontend `AdmissionSummaryDrafter`: **fallback時に「⚠ 品質低下モード」警告バー表示**
- SOAP を `GenerateSOAP` 単一呼出 (LoRASOAPFullID=1) に変更
  - parser.go: 半角括弧マーカー追加 (`S (Subjective)` 等)
  - パース失敗時は 4-call suggest fallback
  - SSE streaming 版 (`GenerateSOAPStreaming`) は 4-call suggest 維持

#### D. post-process 強化（cleanModelOutput）
- 既存 8 ケース + 新規 8 ケース = **16 ケース全 PASS**
- 新パターン:
  - **`【解説】` 前置きブロック削除**（ヘルパー関数、RE2 lookahead 非対応のため）
  - **`■ 補足・注意点` 末尾ブロック削除**（`---` 無し版）
  - 残留 `**` `***` 安全網
  - インライン italic / backticks / strikethrough / 行末装飾 *
  - 末尾 `補足:` プレーンテキスト
- ファイル: `emr/backend/internal/slm/client.go` + `client_test.go`

#### E. 患者属性自動注入（4B の性別誤認バグ解消）
- `handler/patient_header.go` 新規 → `buildPatientHeader(p, encounterDate)` で `【患者情報】62歳 女性\n` 生成
- SOAP draft handler / SLM handler (`/api/slm/suggest/admission`): encounter_id → patient lookup → interviewText 先頭に注入
- 効果検証済: **4B が女性患者を「男性」と誤認 → 解消**（音声花子 SOAP でテスト）
- frontend: `suggestAdmissionSummary(text, encounterId?)` に拡張

#### F. seed: 音声花子 (MRN-0022) 追加
- 62歳 女性、循環器内科、動悸主訴、AF + LA 軽度拡大 + BNP 145 + LVEF 58% シナリオ
- **問診記録は STT 生出力風**: 話者ラベルなし、句読点欠、フィラー、自己訂正、同時発話混在
- encounter ID 37、`/api/test-patient/reset` 対象外（永続）
- 将来の音声入力モジュール接続テスト用、4B 抽象化耐性検証材料
- 動作検証済: 4B v2_r64 で 7.8s に SOAP 4 セクション完全生成、音声特有の難所もクリア

#### G. HF Hub に配布アーティファクト upload 完了
- `inaka0303/medical-slm-loras` (model, private): 3 LoRA + README、合計 327MB
- `inaka0303/medical-slm-rag-db` (dataset, private): `rag_db_v2.tar.gz` 4.7GB（展開後 7.5GB）
- `unsloth/Qwen3.5-4B-GGUF` (public): ベース GGUF
- `rag_server.py` を環境変数対応化（`RAG_DB_DIR`）→ git repo にコピー
- `docs/SETUP_LAPTOP.md` 全面書き換え（M3 16GB 向け、HF Hub 経由）

### git push 状況（commit ハッシュ）

| repo | 最新 commit | 内容 |
|---|---|---|
| medical_slm | `85223e8` | docs: SETUP_LAPTOP.md + HF Hub 対応 + rag_server.py |
| medical_slm | `c9b81f5` | docs: 2026-04-23 構成へ更新（CLAUDE.md） |
| emr | `55a2c05` | feat: 3-LoRA 分離 + 9B admission 専用化 + post-process + 患者属性 |

---

## 📋 次のセッション (/clear 後) への引き継ぎ

### A. 現状の本番構成（再起動コマンドは下記「現在のサービス」）
- 4B llama-server (port 8081, GPU 2): 3 LoRA
- 9B admission llama-server (port 8083, GPU 3): 1 LoRA
- RAG server (port 8082, GPU 1)
- EMR backend (port 8080, env で SLM_API_URL + SLM_ADMISSION_URL 必要)
- frontend (port 5173)

### B. 未着手 / 今後やること（優先順）

#### 1. 論文方針の議論（**今日途中で中断**）
未返答事項:
- データセット公開の是非（公開するなら Nature Sci Data 狙い、しないなら JAMIA 等）
- ACI-Bench (Nature Sci Data 2023, Yim et al.) の JSON schema 借用
- 対話形式データを追加で作るか
- IRB と被験者数（10 vs 30）
- **戦略分岐: 1本論文 vs 「開発論文 + 臨床試験論文」2本立て**

参考リソース:
- ACI-Bench: https://doi.org/10.1038/s41597-023-02487-3 (英語、CC-BY、対話→診察記録)
- 我々の差別化: 日本語 × 循環器特化 × 軽量 SLM × ACI-Bench 相当

循環器学会発表設計:
- 3軸評価: 自動指標 (BERTScore/Opus judge) / 盲検クオリティ (専門医・学生) / 時間短縮 RCT
- 疾患選定: 11→10 推奨（心アミロイドーシス か 冠攣縮性を落とす）、1疾患2例=20例
- クロスオーバー RCT、ラテン方格、対応のあるt検定 / Wilcoxon

Tier 戦略（学会発表で打ち出す）:
- Tier 1（個人クリニック）: ノートPC + 4B + RAG
- Tier 2（中規模病院）: 院内 WS + 4B + 9B + RAG
- Tier 3（大学病院）: H100 + 上記 + 拡張
- 「commodity hardware で動く Japanese-medical-specialized SLM」が論文の主張

#### 2. ノートPC で SETUP_LAPTOP.md の手順実証
先生の M3 Mac 16GB で実際にセットアップ → 詰まった点を docs に追記。

#### 3. 性別注入のさらなる改善余地
現状は年齢・性別のみ。追加で:
- 既往歴・服薬歴も患者プロファイルから自動付与？
- 受診目的（chief_complaint）はすでに encounter にある → 注入検討
- ただし冗長になりすぎると suggest UX が悪化するので要バランス

#### 4. 残るハルシネーション対策
- 4B の薬剤名ハルシネーション（「アプレキサン」「リバスタン」等架空）
- → RAG 検索結果を P 生成プロンプトに注入する実装（現状 RAG は手動「根拠を確認」のみ）

#### 5. 9B SOAP / 9B suggest の評価
今日 9B admission のみ専用サーバー化。9B の SOAP/suggest LoRA も評価済（results_v6/eval_all_models）。

#### 6. RAG DB 再構築（保留）
build_rag_v2.py の title 抽出 + publication_year 改良はコード反映済だが、DB 自体の再構築は未実行（1-2時間 GPU 必要）。

### C. 試したいシナリオ（次回ブラウザで）

1. **音声花子 (MRN-0022, encounter 37)**: STT 風入力 → SOAP 確認、admission で 9B サーバー使用確認 + 性別注入の効果
2. **新規太郎 (MRN-0021)**: 空白問診から手入力、suggest LoRA の挙動
3. **山本隆 (MRN-0007, 2026-04-18 入院)**: admission 9B v3_clean_r32 で本番品質確認
4. **fallback テスト**: 9B サーバーを止めて admission 試行 → 警告バー表示確認

### D. 知っておくべき罠 / TIPS

1. **9B サーバーの kill/restart**: 60s の `backgroundHealthCheck` を待たず、HTTP失敗で即 4B fallback に retry する設計。即座に使えなくなる Window はゼロ。
2. **post-process は全 SLM 経路で適用**（cleanModelOutput in callChatCompletionWithLoRA、新規太郎 / 音声花子 / 任意 patient で同様）。
3. **emr repo の SLM client は `nLoras` を Client 起動時に動的決定**（旧コードの 12 ハードコード bug は修正済）。
4. **RAG server は `RAG_DB_DIR` env で DB パス上書き可**（H100 のフルパス決め打ちではなくなった）。
5. **音声花子の interview note encounter_id は 37**（seed の順序で決まる、MRN-0021 が enc 36 だったため）。
6. **HF Hub repo 全部 private**: download に token 必須、share する時は read token を発行する。

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

## 現在のサービス（2026-04-24 更新、-fa + KV q4_0 + emr v2 適用）

| port | サービス | GPU | VRAM | ロード LoRA | 備考 |
|---|---|---|---|---|---|
| 5173 | Vite frontend (React) | - | - | - | - |
| 8080 | EMR backend v2 (Go/Echo) | - | - | - | repeat_penalty=1.1 / meta-filter v2 / 30s timeout |
| **8081** | **4B llama-server (suggest + soap + admission fallback)** | GPU 2 | ~4GB | 3 LoRA | -fa on / -ctk q4_0 / -ctv q4_0 |
| **8083** | **9B llama-server (admission 専用)** | GPU 3 | ~7GB | 1 LoRA | -fa on / -ctk q4_0 / -ctv q4_0 |
| 8082 | RAG server (FastAPI, Ruri-v3) | GPU 1 | ~2GB | - | - |

### 起動コマンド（2026-04-24 版、-fa + KV q4_0 追加）

**2026-04-24 変更点**:
- `-fa on` (flash attention 明示有効化)
- `-ctk q4_0 -ctv q4_0` (KV cache を q4_0 量子化、メモリ 1/4)
  - 効果: K+V 合計 2.3 GB (以前 ~9 GB)、M3 では熱・メモリ余裕確保
  - H100 でも適用、quality への影響は無視できる程度と判断
- warmup script `/home/junkanki/naka/scripts/warmup_demo.sh` を起動後に実行推奨

```bash
# 1. 4B llama-server (3 LoRA のみロード、起動 ~5秒)
cd /data2/junkanki/naka
CUDA_VISIBLE_DEVICES=2 nohup llama.cpp/build/bin/llama-server \
  -m gguf_models/Qwen3.5-4B-UD-Q4_K_XL.gguf \
  --lora gguf_models/sft_4b_nocpt_A_lora.gguf \
  --lora gguf_models/sft_soap_full_v2_r64_lora.gguf \
  --lora gguf_models/sft_admission_v2_r32_lora.gguf \
  --port 8081 -ngl 99 -fa on -ctk q4_0 -ctv q4_0 \
  --chat-template-kwargs '{"enable_thinking":false}' \
  > /data2/junkanki/naka/logs/llama_server_slim.log 2>&1 &

# 2. 9B llama-server (admission 専用)
CUDA_VISIBLE_DEVICES=3 nohup llama.cpp/build/bin/llama-server \
  -m gguf_models/Qwen3.5-9B-UD-Q4_K_XL.gguf \
  --lora gguf_models/sft_admission_9b_v3_clean_r32_lora.gguf \
  --port 8083 -ngl 99 -fa on -ctk q4_0 -ctv q4_0 \
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

# 6. 全サーバー起動完了後: warmup script (LCP prompt cache を予熱)
#    M3 field notes 2026-04-23 の発見: cache 未登録患者は 6-9 秒 or timeout。
#    本 script で各デモ患者の interview と共に autocomplete を 1 回ずつ叩くと
#    LCP cache が埋まり、以降のリクエストは 1 秒以下で応答。
sleep 5
/home/junkanki/naka/scripts/warmup_demo.sh
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
