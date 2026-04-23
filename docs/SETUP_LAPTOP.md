# ノートPC セットアップ手順（M3 Mac, 4B + RAG 構成）

学会会場に持参する想定の **MacBook Pro (M3, 16GB RAM)** で、医療特化 SLM の EMR デモを動かすための手順。

> **Tier 1 構成**（4B + RAG、admission は 4B fallback モード）  
> 9B admission の高品質生成はラボの院内サーバー (Tier 2 / 3) でのみ動作。  
> 学会会場 Wi-Fi に依存しない **完全オフライン動作**。

---

## 全体像

| コンポーネント | プロセス | port | 説明 |
|---|---|---|---|
| 4B llama-server | `llama-server` | 8081 | 3 LoRA: suggest + SOAP + admission fallback |
| RAG server | `rag_server.py` | 8082 | Ruri-v3 + ChromaDB |
| EMR backend | `emr-server` (Go) | 8080 | API ルーティング・DB |
| EMR frontend | Vite (npm dev) | 5173 | ブラウザ UI |
| **9B admission server** | （**未起動**） | - | ノートPC では諦める→ 4B fallback で動作 |

---

## 必要スペック

| 項目 | 推奨 | 最低 |
|---|---|---|
| Mac | M3 / M4 (Apple Silicon) | M1 でも可 |
| RAM | **16GB** | 16GB（必須） |
| ストレージ空き | 15GB | 12GB |
| OS | macOS 14+ | 13+ |

メモリ消費目安（同時稼働時）:
- macOS: 4-6GB
- 4B GGUF (llama-server): 4GB
- Ruri-v3 (RAG): 1.2GB
- ChromaDB mmap: 1-2GB
- Go backend: 100MB
- Vite + ブラウザ: 1-2GB
- **合計 12-15GB** ← 16GB Mac でギリ動く（swap たまに発生）

---

## Step 0: 前提パッケージ（Mac の Homebrew）

```bash
# Homebrew 自体（未インストールなら）
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 必要パッケージ
brew install llama.cpp git go node python@3.11
pip3 install huggingface_hub fastapi uvicorn chromadb sentence-transformers torch
```

`llama.cpp` は brew tap で `llama-server` バイナリが入ります。Apple Silicon 自動検出で Metal バックエンド有効。

---

## Step 1: ソースコード clone

```bash
mkdir -p ~/naka && cd ~/naka

# 訓練・評価スクリプト（このリポ）
git clone git@github.com:inaka0303/medical_slm.git

# EMR アプリ（別リポ）
git clone git@github.com:inaka0303/emr.git
```

SSH keyが未設定なら HTTPS URL でもOK:
```bash
git clone https://github.com/inaka0303/medical_slm.git
git clone https://github.com/inaka0303/emr.git
```

---

## Step 2: モデル DL（Hugging Face Hub）

### 2-1. HF Hub にログイン

```bash
hf auth login
# Web で発行した token (Read で十分) を貼り付け
```

トークン発行: https://huggingface.co/settings/tokens → **Read** タイプで OK。

### 2-2. ベース GGUF（公開、Qwen3.5-4B Q4_K_XL）

```bash
mkdir -p ~/naka-models/loras

hf download unsloth/Qwen3.5-4B-GGUF \
  Qwen3.5-4B-UD-Q4_K_XL.gguf \
  --local-dir ~/naka-models/
# → ~/naka-models/Qwen3.5-4B-UD-Q4_K_XL.gguf  (2.8GB)
```

### 2-3. LoRA × 3（private、token 必要）

```bash
hf download inaka0303/medical-slm-loras \
  --local-dir ~/naka-models/loras/
# → ~/naka-models/loras/sft_4b_nocpt_A_lora.gguf            (82MB)
# → ~/naka-models/loras/sft_soap_full_v2_r64_lora.gguf     (163MB)
# → ~/naka-models/loras/sft_admission_v2_r32_lora.gguf      (82MB)
```

### 2-4. RAG DB（private、tar.gz で配布）

```bash
hf download inaka0303/medical-slm-rag-db \
  rag_db_v2.tar.gz \
  --local-dir ~/naka-models/
cd ~/naka-models && tar xzf rag_db_v2.tar.gz
# → ~/naka-models/rag_db_v2/  (展開後 7.5GB)
rm rag_db_v2.tar.gz   # tar.gz は不要
```

### 2-5. Ruri-v3 embedder（自動 DL 1.2GB）
RAG server を初回起動した時に sentence-transformers が自動 DL するので**事前準備不要**。

---

## Step 3: 4B llama-server を起動

```bash
llama-server \
  -m ~/naka-models/Qwen3.5-4B-UD-Q4_K_XL.gguf \
  --lora ~/naka-models/loras/sft_4b_nocpt_A_lora.gguf \
  --lora ~/naka-models/loras/sft_soap_full_v2_r64_lora.gguf \
  --lora ~/naka-models/loras/sft_admission_v2_r32_lora.gguf \
  --port 8081 -ngl 99 \
  --chat-template-kwargs '{"enable_thinking":false}' &
```

**LoRA ID マッピング（順序厳守）:**
| ID | LoRA | 用途 |
|---|---|---|
| 0 | sft_4b_nocpt_A | suggest（インライン補完・SOAPストリーミング 4-call） |
| 1 | sft_soap_full_v2_r64 | SOAP全体（単一呼出、本番 4B best） |
| 2 | sft_admission_v2_r32 | admission fallback（9B未接続時に使われる） |

動作確認:
```bash
curl -s http://localhost:8081/v1/models | head -c 200
# → {"data":[{...}]} が返れば OK
```

---

## Step 4: RAG server を起動

```bash
cd ~/naka/medical_slm

# RAG_DB_DIR 環境変数で Mac 上のパスを指定（rag_server.py が読み取る）
RAG_DB_DIR=~/naka-models/rag_db_v2 \
  python3.11 rag_server.py --port 8082 --host 127.0.0.1 &
# 初回は Ruri-v3 自動DL (1.2GB) で 1-2分かかる
# "Loading Ruri-v3..." → "ChromaDB loaded" が出れば起動完了
```

動作確認:
```bash
curl -s http://localhost:8082/health
# → {"status":"ok"} 等
```

---

## Step 5: EMR backend を起動

```bash
cd ~/naka/emr/backend
go build -o /tmp/emr-server ./cmd/server/

# SLM_ADMISSION_URL は設定しない → admission は 4B fallback (id=2) が動く
# UI で「品質低下モード」警告バーが表示される
SLM_API_URL=http://localhost:8081 /tmp/emr-server &
# → :8080 で待ち受け
```

動作確認:
```bash
curl http://localhost:8080/health
# → {"status":"ok"}
```

ログで以下が出れば SLM 接続OK:
```
INFO  SLM推論サーバー接続成功 url=http://localhost:8081
```
（admission サーバーは未指定なので関連ログは出ない）

---

## Step 6: EMR frontend を起動

```bash
cd ~/naka/emr/frontend
npm install   # 初回のみ、5分程度
npm run dev -- --host 0.0.0.0
# → http://localhost:5173/
```

ブラウザで http://localhost:5173/ を開く。

---

## デモシナリオ

### A. 音声花子（MRN-0022）で voice-input → SOAP 動作確認

> 学会向けの目玉症例。**音声認識生出力風の問診** を SLM がどう構造化するかを見せる。

1. 患者リストから「**音声 花子**」を選択
2. 2026-04-23 の循環器内科 encounter（主訴: 動悸）を開く
3. 問診タブを見る:
   - **問診記録**: 音声 STT 風（フィラー、自己訂正、同時発話混在）
   - お薬手帳/診察所見/検査結果: 通常記述
4. **SOAP ドラフト** ボタン → 7-12 秒で 4 セクション生成
5. **入院時サマリ** ボタン → 「**⚠ 品質低下モード（4B admission LoRA）**」警告が出る  
   （これが Tier 1 の制約を示すデモポイント）

### B. 新規太郎（MRN-0021）で空白からの入力フロー

1. 患者リストから「**新規 太郎**」を選択
2. 進行中の encounter（2026-04-20）を開く
3. 問診を**自分で入力**（4セクション全て or 一部）
4. SOAP ドラフト生成 → suggest LoRA + soap_full LoRA の動きを確認
5. ブラウザリロードで自動リセット（`/api/test-patient/reset` が走る）

### C. RAG 確認

1. 任意の症例で「**根拠を確認**」ボタンが出るところをクリック
2. 関連ガイドラインが表示されれば RAG server 動作 OK

---

## トラブルシュート

### llama-server が起動しない
- `ps aux | grep llama-server` で残骸確認 → `pkill llama-server`
- ポート競合 → `lsof -i :8081` で他プロセス確認
- メモリ不足 → `-ngl 50` 等に下げる（GPU offload 層数）

### RAG server が "ChromaDB loaded" まで進まない
- `rag_server.py` の `DB_DIR` パスが正しいか確認
- `ls ~/naka-models/rag_db_v2/` に `chroma.sqlite3` が見えるか
- Ruri-v3 DL が遅い場合は HF への接続を確認

### EMR backend が "SLM unreachable" を吐く
- llama-server が立っているか `curl http://localhost:8081/v1/models`
- 環境変数 `SLM_API_URL` が渡っているか確認
- 起動順序: llama-server → RAG → backend → frontend

### admission に「警告バー」が出ない／消したい
- 警告は **`server="4B-fallback"`** がレスポンスに入っている時に出る
- 9B サーバー（Tier 2）に接続したい場合は `SLM_ADMISSION_URL=http://...:8083` を設定
- Mac 単独運用では基本的に **常に警告が出る**（仕様）

### マークダウン残留
- post-process で 16 パターンを除去するが、訓練データ起因で稀に漏れる
- 漏れたパターンを `client.go:cleanModelOutput` の正規表現に追加
- 既存テスト: `go test ./internal/slm/... -run TestCleanModelOutput -v`

### メモリ不足で swap 多発
- ブラウザを Safari → Chrome は重い、Safari 推奨
- 不要アプリを閉じる
- それでもダメなら RAG server を停止（P が劣化するが他は動く）

---

## 起動・停止スクリプト例

`~/naka/start_all.sh`:
```bash
#!/bin/bash
set -e
cd ~/naka

# 1. llama-server
llama-server \
  -m ~/naka-models/Qwen3.5-4B-UD-Q4_K_XL.gguf \
  --lora ~/naka-models/loras/sft_4b_nocpt_A_lora.gguf \
  --lora ~/naka-models/loras/sft_soap_full_v2_r64_lora.gguf \
  --lora ~/naka-models/loras/sft_admission_v2_r32_lora.gguf \
  --port 8081 -ngl 99 \
  --chat-template-kwargs '{"enable_thinking":false}' \
  > /tmp/llama_server.log 2>&1 &
echo "llama-server PID: $!"

# 2. RAG server
RAG_DB_DIR=~/naka-models/rag_db_v2 \
  python3.11 ~/naka/medical_slm/rag_server.py --port 8082 --host 127.0.0.1 \
  > /tmp/rag_server.log 2>&1 &
echo "rag_server PID: $!"

# 3. EMR backend
cd ~/naka/emr/backend
go build -o /tmp/emr-server ./cmd/server/
SLM_API_URL=http://localhost:8081 /tmp/emr-server \
  > /tmp/emr_backend.log 2>&1 &
echo "backend PID: $!"

# 4. frontend (フォアグラウンドで)
cd ~/naka/emr/frontend
npm run dev -- --host 0.0.0.0
```

`~/naka/stop_all.sh`:
```bash
#!/bin/bash
pkill -f "llama-server" || true
pkill -f "rag_server.py" || true
pkill -f "/tmp/emr-server" || true
pkill -f "vite" || true
echo "All stopped."
```

---

## 学会発表時の運用 Tips

- **電源**: M3 でもフル稼働で発熱、AC アダプタ必須
- **Wi-Fi 切断推奨**: 完全オフライン動作で「インターネット要らない」を見せる
- **デモ前準備**: 起動 → ブラウザで 1 度患者リスト → SOAP 生成までキャッシュ温める
- **トラブル対応**: 全プロセスを kill → start_all.sh で再起動が一番早い

---

## 9B admission を試したい場合（Tier 2 移行）

ノートPC では諦め、**院内 GPU サーバー（H100 / A100 / RTX 4090）が利用可能**な環境で:

```bash
# H100 上で 9B admission 専用 server を起動
CUDA_VISIBLE_DEVICES=N llama-server \
  -m Qwen3.5-9B-UD-Q4_K_XL.gguf \
  --lora sft_admission_9b_v3_clean_r32_lora.gguf \
  --port 8083 -ngl 99 \
  --chat-template-kwargs '{"enable_thinking":false}'

# Mac 側 backend を起動する時に環境変数を追加
SLM_API_URL=http://localhost:8081 \
SLM_ADMISSION_URL=http://<H100のIP>:8083 \
/tmp/emr-server
```

→ admission は **9B**（高品質）に切り替わり、UI 警告バーは消える。
