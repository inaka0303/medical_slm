# ノートPC セットアップ手順 — 9B 3-LoRA hot-swap 実験版

**MacBook Pro (M3, 16GB RAM)** で 9B GGUF + 3 LoRA hot-swap を試すための手順。

> **目的**: 9B モデルを M3 ローカルで動かし、suggest / SOAP / admission 各 LoRA の切替テストを行う。
> **想定**: 既存の `SETUP_LAPTOP.md` (4B + RAG 構成) はそのまま使える。本書は 9B を**追加で**動かす際の差分手順。
> **本番デモ**: 9B は本番デモには使わず、研究実験用 (M3 性能評価、LoRA 切替効果の主観評価)。

---

## 1. 全体像

| コンポーネント | プロセス | port | 備考 |
|---|---|---|---|
| **9B llama-server** | `llama-server` | **8083** | 3 LoRA: suggest + SOAP + admission |
| 4B llama-server | `llama-server` | 8081 | 既存 (`SETUP_LAPTOP.md` 参照) |
| RAG / EMR backend / Vite | - | 8082 / 8080 / 5173 | 既存 (4B 構成と共通) |

9B は **port 8083 で 4B (port 8081) と並列稼働可能**。両方同時に起動すると M3 16GB ではメモリ逼迫するので、**9B 実験中は 4B を停止**するのが現実的。

---

## 2. 必要スペック・メモリ見積もり

| 項目 | 推奨 | 最低 |
|---|---|---|
| Mac | M3 / M4 (Apple Silicon) | M2 (M1 だと TG が遅い) |
| RAM | **16GB** | 16GB (8GB は不可) |
| ストレージ空き (9B 単独) | +6 GB (base + 3 LoRA) | +6 GB |

### メモリ消費目安 (9B 単独稼働時)

| 何 | 容量 |
|---|---|
| macOS + アプリ | 4-6 GB |
| 9B GGUF (Q4_K_XL) | 5.6 GB |
| 9B LoRA × 3 (loaded) | 0.34 GB |
| KV cache (2048 ctx, K/V q4_0 量子化) | ~0.7 GB |
| llama-server 自体 | 0.2 GB |
| **合計** | **~12 GB** |

→ M3 16GB に余裕で収まる。**4B (port 8081) との同時稼働は ~17 GB 必要となり swap 発生**するので、9B 実験時は 4B を `kill` 推奨。

### 速度想定

| 指標 | 期待値 (M3 16GB) |
|---|---|
| 起動 (3 LoRA load) | 5-10 秒 |
| TG 速度 (LoRA 切替後の最初のリクエスト) | **5-12 token/s** |
| LCP cache hit 時 | 上記 + cache 効果で TTFT 短縮 |
| LoRA hot-swap overhead | per-request `lora` field で **数十 ms**、無視できる |

---

## 3. Step 0-1: 共通手順 (既存 doc 参照)

下記は `SETUP_LAPTOP.md` と完全に同じなので、未実施なら先にそちらを完了させる:

- Homebrew + 必要パッケージ (`llama.cpp git python@3.11` 等)
- ソースコード clone (`medical_slm`, `emr`)
- HF Hub login (`hf auth login`)

---

## 4. Step 2: 9B 用モデルダウンロード

### 2-1. ベース GGUF (公開、Qwen3.5-9B Q4_K_XL)

```bash
mkdir -p ~/naka-models/loras_9b

hf download unsloth/Qwen3.5-9B-GGUF \
  Qwen3.5-9B-UD-Q4_K_XL.gguf \
  --local-dir ~/naka-models/
# → ~/naka-models/Qwen3.5-9B-UD-Q4_K_XL.gguf  (5.6 GB)
```

### 2-2. 9B LoRA × 3 (private、token 必要)

`inaka0303/medical-slm-loras` の `9b/` サブディレクトリから:

```bash
hf download inaka0303/medical-slm-loras \
  --include "9b/*" \
  --local-dir ~/naka-models/loras_9b/
# → ~/naka-models/loras_9b/9b/sft_9b_nocpt_ep8_lora.gguf                    (112 MB)
# → ~/naka-models/loras_9b/9b/sft_soap_full_9b_v3_clean_r32_lora.gguf       (112 MB)
# → ~/naka-models/loras_9b/9b/sft_admission_9b_v3_clean_r32_lora.gguf       (112 MB)
```

合計 **5.6 + 0.34 = 約 6 GB** を新規 DL。

---

## 5. Step 3: 9B llama-server を起動

### 5-1. (必要なら) 4B サーバーを停止

```bash
# 8081 を listen している PID を確認して停止
lsof -ti:8081 | xargs -r kill
```

### 5-2. 9B サーバー起動 (3 LoRA hot-swap、port 8083)

```bash
llama-server \
  -m ~/naka-models/Qwen3.5-9B-UD-Q4_K_XL.gguf \
  --lora ~/naka-models/loras_9b/9b/sft_9b_nocpt_ep8_lora.gguf \
  --lora ~/naka-models/loras_9b/9b/sft_soap_full_9b_v3_clean_r32_lora.gguf \
  --lora ~/naka-models/loras_9b/9b/sft_admission_9b_v3_clean_r32_lora.gguf \
  --port 8083 -ngl 99 \
  -fa on -ctk q4_0 -ctv q4_0 \
  --chat-template-kwargs '{"enable_thinking":false}' &
```

**フラグの意味**:
- `-ngl 99`: 全層 GPU offload (M3 で Metal を使う)
- `-fa on`: flash attention 有効化 (KV q4_0 量子化に必須)
- `-ctk q4_0 -ctv q4_0`: KV cache を q4_0 に量子化、メモリ 1/4 に削減
- `--chat-template-kwargs '{"enable_thinking":false}'`: Qwen3 の thinking モード無効化

### 5-3. LoRA ID マッピング (順序厳守)

`--lora` フラグの**指定順**で id 0/1/2 が割り当てられる:

| ID | LoRA | 用途 |
|---|---|---|
| 0 | `sft_9b_nocpt_ep8_lora.gguf` | suggest (autocomplete + SOAP 4-call ストリーミング) |
| 1 | `sft_soap_full_9b_v3_clean_r32_lora.gguf` | SOAP 単一呼出 |
| 2 | `sft_admission_9b_v3_clean_r32_lora.gguf` | 入院時サマリ |

順番を変えると EMR backend の LoRA ID 指定とずれて誤動作するので注意。

---

## 6. Step 4: 動作確認

### 6-1. LoRA がロードされているか

```bash
curl -s http://localhost:8083/lora-adapters | python3 -m json.tool
```

期待出力:
```json
[
    {"id": 0, "path": "...sft_9b_nocpt_ep8_lora.gguf", "scale": 1.0, ...},
    {"id": 1, "path": "...sft_soap_full_9b_v3_clean_r32_lora.gguf", "scale": 0.0, ...},
    {"id": 2, "path": "...sft_admission_9b_v3_clean_r32_lora.gguf", "scale": 0.0, ...}
]
```

(デフォルトでは id=0 のみ scale=1.0)

### 6-2. 3 LoRA を切り替えて動作テスト

```bash
# LoRA id=0 (suggest) を有効化したリクエスト
curl -s http://localhost:8083/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen-medical-9b",
    "messages": [
      {"role":"system","content":"あなたは日本語の電子カルテ記載を支援する医療AIアシスタントです。"},
      {"role":"user","content":"50歳男性、胸痛で来院。SOAP 形式で簡潔に記載してください。"}
    ],
    "max_tokens": 256, "temperature": 0.3,
    "lora": [{"id":0,"scale":1.0},{"id":1,"scale":0.0},{"id":2,"scale":0.0}],
    "chat_template_kwargs": {"enable_thinking": false}
  }' | python3 -m json.tool
```

`lora` field の `id`/`scale` を変えて id=1 (SOAP)、id=2 (admission) も同様に試す。

### 6-3. EMR backend 経由で 9B を使う (任意)

EMR backend を 9B 向けに切り替えるには:

```bash
# 4B サーバーを停止し、9B を 4B 用 LoRA mapping で代替させる
SLM_API_URL=http://localhost:8083 \
SLM_ADMISSION_URL=http://localhost:8083 \
  ./emr-server &
```

`SLM_ADMISSION_URL` も 9B サーバーに向ければ、admission も suggest/SOAP も 9B で生成される。

---

## 7. パフォーマンス計測 (任意、研究用)

### 7-1. 単発推論の TTFT / TG 速度

```bash
# 各 LoRA で simple な推論を 5 回ずつ実行し、latency を記録
for lora_id in 0 1 2; do
  for i in 1 2 3 4 5; do
    /usr/bin/time -p curl -s -o /dev/null http://localhost:8083/v1/chat/completions \
      -H "Content-Type: application/json" \
      -d "$(jq -n --arg id $lora_id '{
        model: "qwen-medical-9b",
        messages: [
          {role:"system", content:"あなたは医療 AI です。"},
          {role:"user", content:"50歳男性 胸痛で来院。S/O/A/P で記載。"}
        ],
        max_tokens: 256, temperature: 0.3,
        lora: [
          {id:0, scale: ($id|tonumber)==0 | tostring | if . == "true" then 1.0 else 0.0 end},
          {id:1, scale: ($id|tonumber)==1 | tostring | if . == "true" then 1.0 else 0.0 end},
          {id:2, scale: ($id|tonumber)==2 | tostring | if . == "true" then 1.0 else 0.0 end}
        ]
      }')" 2>&1 | grep real
  done
done
```

期待値 (M3 16GB):
- 1 回目: ~30-60 秒 (cold cache)
- 2 回目以降: 10-20 秒 (LCP cache hit)

### 7-2. ベンチマーク runner による定量評価 (H100 と同条件)

H100 で構築した `data/aci_jp_cardio/` ベンチマークを M3 で走らせると、**4B / 9B 全乗せ / 9B + RAG 等の構成差を定量比較**できる:

```bash
cd ~/naka/medical_slm/data/aci_jp_cardio/admission
python3.11 eval_runner/eval_cardio.py \
  --cases cases.jsonl --target soap --model 9b_admission \
  --slm-url http://localhost:8083 \
  --output results/m3_9b_soap.json --skip-bertscore
```

(eval runner は 9B 向け model 指定が必要。4B/9B 切替の cli フラグはまだ整備されていないので、必要なら slm_client.py の `MODEL_CONFIGS` を拡張する。)

---

## 8. Troubleshooting

### 8-1. 「メモリが足りない」と言われて起動しない

- 4B サーバーが残ってないか確認: `lsof -i:8081`
- ブラウザのタブ閉じる
- `Activity Monitor` で大物プロセスを確認 (Chrome や VSCode で 5GB 食ってると詰む)
- それでも厳しければ `-ctk q8_0 -ctv q8_0` (KV q8、若干メモリ増だが quality 維持)、または `--ctx-size 1024` で context 半分

### 8-2. LoRA が反映されていない感じがする

- `curl /lora-adapters` で各 LoRA の `scale` が期待通りか確認
- per-request `lora` field を渡したリクエストの response が空または同じ → llama.cpp バージョンが古いかも (Apple Homebrew の llama.cpp は最新を維持しているが念のため `brew upgrade llama.cpp`)

### 8-3. 9B の TG が遅すぎる

- M3 でも 9B Q4_K_XL は **5-10 token/s** が普通。これより極端に遅い場合は:
  - GPU offload が効いているか: 起動時のログに `offloaded XXX/XXX layers to GPU` が出ているか
  - Activity Monitor の Memory pressure が黄/赤になっていないか (なってたら swap で大幅減速)
  - `-fa on -ctk q4_0 -ctv q4_0` を必ず付ける (without だと KV cache が ~9GB に膨れて swap 直行)

### 8-4. EMR から接続したいが unhealthy になる

- backend の `backgroundHealthCheck` は 60 秒間隔。9B サーバー起動から 1 分待つ
- それでも繋がらなければ `curl http://localhost:8083/health` で直接確認

---

## 9. 9B から 4B 構成に戻すには

```bash
# 9B サーバー停止
lsof -ti:8083 | xargs -r kill

# 4B サーバー起動 (SETUP_LAPTOP.md の Step 3 を実行)
llama-server \
  -m ~/naka-models/Qwen3.5-4B-UD-Q4_K_XL.gguf \
  --lora ~/naka-models/loras/sft_4b_nocpt_A_lora.gguf \
  --lora ~/naka-models/loras/sft_soap_full_v2_r64_lora.gguf \
  --lora ~/naka-models/loras/sft_admission_v2_r32_lora.gguf \
  --port 8081 -ngl 99 -fa on -ctk q4_0 -ctv q4_0 \
  --chat-template-kwargs '{"enable_thinking":false}' &
```

EMR backend は `SLM_API_URL=http://localhost:8081` で 4B 単独に戻る。
