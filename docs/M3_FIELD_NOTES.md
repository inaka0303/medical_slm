# M3 MacBook 実機フィールドノート & 改良案

> **実施日**: 2026-04-23  
> **検証環境**: Apple M3 MacBook 16GB, macOS 14, llama.cpp (brew, Metal backend)  
> **対象構成**: Tier 1 = 4B + 3 LoRA + RAG（SETUP_LAPTOP.md 準拠）  
> **目的**: 学会デモ用ノートPC での動作検証と、実機で発見された問題の整理・改良案

このドキュメントは、SETUP_LAPTOP.md の手順で実際に M3 16GB にフル構成を展開し、**新規太郎・音声花子・加藤真理・山本隆・池田里奈**などのデモ患者で suggest / SOAP ドラフト / admission サマリを動かして体感した挙動から得られた **現場知見 + 改良案**の記録。

---

## エグゼクティブサマリ

**動いた（学会デモで使える）:**
- ✅ 4B GGUF + 3 LoRA の Metal 推論は起動 1 秒、全 33 層オフロード
- ✅ RAG server は Ruri-v3 自動 DL 込み 58 秒で起動
- ✅ SOAP 生成品質は**臨床的に妥当**（音声花子で AF 同定、CHA2DS2-VASc 自動算出、実在薬のみ、性別注入あり）
- ✅ DB キャッシュ 30ms 応答は完璧

**予想より悪かった:**
- ❌ SOAP 初回生成 **2 分強**（SETUP_LAPTOP.md の 7-12s 想定の 10-15 倍）
- ❌ autocomplete 初回 **7-9 秒**（Copilot 体感に程遠い、15s timeout で失敗するケースも）
- ❌ SOAP 単発呼出は parse 失敗で **4-call fallback が常発動**（5 倍の計算コスト）
- ❌ 新規太郎型の短入力で **A/P が反復ループ**に陥る（repeat_penalty 未設定）
- ❌ SSE で S を却下すると **O/A/P 以降が停止**（UX バグ）

**最大の発見:**
- 🔍 **llama-server の LCP 類似度 prompt cache が UX 体感を支配**。過去リクエストが cache に入っている患者は「一瞬で動く」、未登録の患者は「動かない」ように見える。インタビューサイズや患者属性は二次要因だった。

---

## 1. パフォーマンス実測

### M3 Metal 実効スループット

```
decode 速度:   ~17 tok/s  (理論上限 ~40 tok/s の 42%)
prompt 処理:   ~50-100 tok/s
KV cache:     256 MB  (-c 8192 設定時、デフォルトは 6 GB で Metal を圧迫)
モデル load:  2.77 GB (Q4_K_XL) + LoRA 324 MB、全 33 層 Metal offload
```

### H100 との差は "思ったより小さい"

```
memory bandwidth:  M3 base ~100 GB/s  vs H100 SXM ~3000 GB/s  (30x 差)
実測 decode:       M3 17 tok/s        vs H100 200-400 tok/s   (15-25x 差)
```

理論差の半分に縮まる理由:
- **バッチ=1 デコードは memory-bandwidth bound**、compute は両方とも余ってる
- H100 の FLOPs 優位は単一ユーザー対話では活かせない
- llama.cpp ランタイムオーバーヘッドが両方に乗る固定コスト
- Q4 量子化で帯域律速がさらに顕著に

**論文での主張として成立**: "commodity hardware で動く Japanese-medical-specialized SLM" は memory-bandwidth bound 特性の結果として理論的にも裏付けられる。

### タイミング分解（4B + M3 + interview_text ~1000 chars）

```
interview_text (1000 chars = ~700 tok) prompt 処理:  8-12s
system prompt + prefill (~100 tok):                1-2s
生成 (48-128 tok):                                 3-8s
合計:                                              12-22s
```

→ autocomplete の 15s timeout 境界と一致。**山本隆（1019 chars）が timeout するのはこの境界超えが原因**と最初は考えたが、後述の prompt cache が実態の支配要因。

---

## 2. 🔍 最大の発見: Prompt Cache が UX を支配する

### 観察

ユーザー体感: 「**音声花子は一瞬で suggest 動く、加藤真理は全然動かない。でも加藤真理の方が interview 短い**」

- 音声花子: 941 chars → 一瞬
- 加藤真理: 267 chars → 動かない
- 山本隆: 1019 chars → 動かない

サイズ相関では説明できない。

### llama-server ログから判明

```
cache state: 38 prompts, 5980.710 MiB (limits: 8192.000 MiB, 8192 tokens)
slot get_availabl: id 0 | selected slot by LCP similarity, 
  sim_best = 0.745 (> 0.100 thold), f_keep = 0.170
```

**llama.cpp server の LCP (Longest Common Prefix) 類似度 prompt cache が本犯人。**

仕組み:
1. サーバーは過去の全 prompt を最大 8 GB まで KV cache として保持
2. 新リクエスト時、cache 内の全スロットと先頭文字列の一致率 (LCP similarity) を計算
3. 閾値 0.1 (10%) 以上なら一致部分の prefill を**完全スキップ**
4. 差分だけ prefill → 生成へ

### なぜ患者で差が出るか

| 患者 | 体感 | 真因 |
|---|---|---|
| 音声花子 (0022) | ⚡ 一瞬 | 開発者が SOAP 生成テストで叩いた → cache 登録 → 後続 autocomplete が prefill skip |
| 新規太郎 (0021) | ✅ 速い | 空 interview = prompt 短い + 触った履歴あり |
| 加藤真理 (0010) | ❌ 動かない | 未テスト → cache miss → full prefill → 6-8s or timeout |
| 山本隆 (0007) | ❌ 動かない | cache miss + 長い interview の二重苦 |

つまり「**上の患者は動く、下は動かない**」の正体は MRN 順でも interview サイズでもなく、**過去にリクエストが飛んで cache に登録されているかどうか**。

### デモへの示唆

デモ開始前に対象患者全員に 1 回 autocomplete を投げれば cache 登録され、本番で全員 fast response。

```bash
# warmup スクリプト
for ENC in 37 36 22 18 10; do
  curl -s -X POST http://localhost:8080/api/slm/autocomplete \
    -H "Content-Type: application/json" \
    -d "{\"text\":\"w\",\"context\":\"soap_subjective\",\"encounter_id\":$ENC}" > /dev/null
done
```

ただし cache は 8 GB 上限で LRU っぽい挙動。**本番は warmup 直後〜30 分が最安定**。

---

## 3. 発見した具体的バグ・品質問題

### 3-1. SOAP 反復ループ（degeneration）

**症例**: 新規太郎、手入力された短い問診で A/P が
```
A: ...急性冠症候群、肺栓塞、胸膜炎、心筋梗塞、胸膜炎、胸膜炎、
   心筋梗塞、胸膜炎、胸膜炎、心筋梗塞、胸膜炎、心筋梗塞...（無限ループ）
```

**原因**: `backend/internal/slm/client.go:205` の `ChatCompletionRequest` 構造体に **`repeat_penalty` / `frequency_penalty` / `presence_penalty` のいずれも含まれていない**。llama-server はデフォルト `repeat_penalty=1.0` (= 無効) で動くため、生成が局所最適にハマると抜けられない。

**症例ごとの差の理由**: 訓練データ分布（具体的検査値付きケース中心）から外れた短入力ほど degenerate しやすい。音声花子（長文・具体検査値あり）はループしにくい、新規太郎（短い問診・検査ほぼなし）はループする。

### 3-2. S セクションにメタコメント混入

**症例**: 池田里奈
```
S: 自覚症状なし。
（問診記録の冒頭にある「自覚症状なし」をそのまま記載するのが適切です。
電子カルテでは、問診で確認した主観的情報として簡潔に記録します。）
```

**原因**: `cleanModelOutput` の 16 パターン網にこの形式（作業説明の括弧書き）が無い。

### 3-3. SSE キャンセル副作用

**症状**: SOAP ストリーミング中に S を却下して編集開始 → O/A/P の生成が停止。

**原因**: SSE 直列生成 + frontend EventSource が編集時に切断 → backend が client 切断検知で残り generation を中止。

ユーザーが期待する挙動: S 編集中も O/A/P は並行生成継続（部分承認モデル）。

### 3-4. SOAP 単発呼出の parse 失敗 → 4-call fallback 常発動

ログ上、`/v1/chat/completions` が SOAP 1 件の生成で **5 回**呼ばれる:
1. SOAP 単発 (LoRA id=1) → 何らかの理由でパース失敗？
2-5. suggest LoRA (id=0) の 4-call fallback (S/O/A/P)

期待: 単発 1 回で済むはず。5x の計算コストが live demo を現実的でなくしている主因。

### 3-5. autocomplete 初回 timeout

Model warmup の 1 回目は 15s 以内に返らず context deadline exceeded → mock fallback。以降は 6-9s。

---

## 4. メモリ・熱・UX 劣化

### メモリ逼迫の実態（稼働 30-60 分後）

```
PhysMem:      15 GB used / 16 GB    (65 MB unused, 1% 余裕)
compressor:   5.0 GB                  (圧縮で延命中)
swapins:      ~400 万                 (激しく発生)
swapouts:     ~600 万
llama-server: prompt cache 6 GB + model 2.8 GB + KV 256 MB = 9 GB
RAG server:   Ruri-v3 1.2 GB + Chroma mmap 2 GB = 3 GB
```

### 熱の原因 3 点

1. llama-server の Metal GPU 持続全稼働
2. メモリ圧縮器の CPU 常時消費
3. swap I/O の SSD 書き込み熱

筐体体感温度が上昇、`pmset -g therm` は警告出さないが OS 閾値超えていないだけで主観的には明確に熱い。

---

## 5. 改良案（優先度順）

### A. 即効策（< 1 day、ノートPC 側 + backend 簡単修正）

| 優先 | 案 | 期待効果 | 対象問題 |
|---|---|---|---|
| ⭐⭐⭐ | **start_all.sh に prompt cache warmup 呼出を追加** | 全デモ患者で初回 1 秒応答を実現 | cache miss 型全症例 |
| ⭐⭐⭐ | `ChatCompletionRequest` に `RepeatPenalty` フィールド追加、SOAP で 1.1 設定 | degeneration 解消 | 新規太郎型 |
| ⭐⭐⭐ | autocomplete timeout 15s → 30s、長 interview_text の自動圧縮 | 山本隆型の "諦め" 解消 | 長文 interview |
| ⭐⭐ | llama-server に `--cache-type-k q4 --cache-type-v q4` 追加 | KV cache 1/4、メモリ余裕 | 熱・メモリ |
| ⭐⭐ | autocomplete `max_tokens` 128 → 48、`temperature` 0.5 → 0.3 | 2-3x 速化 | autocomplete UX |
| ⭐⭐ | `cleanModelOutput` に `（.*記載するのが適切.*）` `（.*カルテでは.*）` `■ 提案` 追加 | メタコメント・説明書き除去 | 池田里奈型、autocomplete |
| ⭐ | autocomplete `interview_text` を冒頭のみ送るモード | prompt 短縮 → 速度 | 長 interview 対応 |

### B. アーキテクチャ改善（1-3 day、backend + frontend）

| 優先 | 案 | 期待効果 | 対象問題 |
|---|---|---|---|
| ⭐⭐⭐ | **SSE キャンセル時に backend の generation を継続、cache に保存**（B 案 or A 案） | S 編集で O/A/P が消えなくなる | UX バグ |
| ⭐⭐⭐ | SOAP 単発呼出 (LoRA id=1) の parse 安定化 → 4-call fallback 回避 | 5x 速化（2m → 30s）、live demo 可能 | パース失敗 |
| ⭐⭐ | **Encounter 横断の interview 要約レイヤー** | 山本隆型の多 encounter 症例対応、長期療養・多診療科への拡張性 | 長文履歴 |
| ⭐⭐ | RAG を SOAP 生成プロンプトへ **自動注入** | 薬剤ハルシネーション対策、RAG 活用 | P 記載品質、idle RAG |
| ⭐ | SOAP の各セクション独立 HTTP リクエスト化（C 案、SSE 廃止） | UX 根本改善、部分編集耐性、並列化可能 | UX バグの根本 |
| ⭐ | **リソース監視ダッシュボード or UI 警告**（メモリ / 熱） | 劣化検知、自動機能縮退の可能性 | 熱・メモリ |

### C. 訓練・データ側（H100、重い）

| 優先 | 案 | 期待効果 |
|---|---|---|
| ⭐⭐⭐ | soap LoRA の **短入力ケース SFT データ拡充** | 新規太郎型の degeneration を根本解消 |
| ⭐⭐ | 長文履歴から **自動要約を生成する LoRA** | 多 encounter 症例対応 |
| ⭐⭐ | SFT データから「作業説明の括弧書き」除去 or 明示的にラベル付きで除外 | メタコメント漏れの根本対応 |
| ⭐ | 4B で SOAP LoRA を **決定的出力（label-aware）** になるよう再 SFT | parse 失敗率低減、4-call fallback 不要化 |

### D. 運用・デモ戦略

| 優先 | 案 | 備考 |
|---|---|---|
| ⭐⭐⭐ | **デモ台本と安全患者リストを明文化** | 音声花子 / 新規太郎 / 池田里奈 = 確実動作ゾーン、山本隆 = 意図的に限界を見せる症例 |
| ⭐⭐ | **warmup スクリプトを起動の一部に組み込み** | `start_all.sh` 末尾で各患者を 1 発ずつ叩く |
| ⭐⭐ | RAG を **デモで使わないならメモリ圧迫源として停止** | Tier 1 で RAG 自動注入してないなら 3-4 GB 解放 |
| ⭐ | **SSD バックアップ**: HF Hub から再 DL するより爆速復旧 | 学会会場 Wi-Fi 不安対策 |

---

## 6. 論文・学会発表への示唆

### 主張の裏付けになる知見

- **Memory-bandwidth bound の LLM デコードは commodity hardware でも実用的**
  - M3 16GB で 17 tok/s、4B Q4 で 100% オフライン動作を実証
  - GPU の compute 優位 (30x FLOPs) は単一ユーザー対話で活かしきれない
  - 論文の Methods / Discussion セクションで技術的根拠として主張可能

- **Tier 戦略の妥当性**
  - Tier 1 (ノートPC、4B + RAG): SOAP 生成は臨床的に妥当、admission は品質低下警告で誠実に提示
  - Tier 2 (院内 GPU、9B 併用): admission 品質向上の明確な理由あり
  - Tier 3 (大学病院、H100 全構成): 研究・開発用

### 誠実に開示すべき限界

- M3 での SOAP 生成は 2 分、キャッシュ済みでも 7-12s を下回らない → "待ち時間がゼロのシステム" とは謳えない
- degeneration、メタコメント、長文履歴対応は**モデル＋パイプラインの現在の限界**
- これらは Limitations セクションの題材であり、**弱みとして正直に書くことが査読で評価される**

---

## 7. 関連ドキュメント

- `docs/SETUP_LAPTOP.md` — ノートPC セットアップ手順
- `CLAUDE.md` — H100 側の全仕様・起動コマンド・実験史
- `~/naka/local_experiment.md` (別リポ管理外) — M3 実機での詳細ログ（このドキュメントの基になった観察記録）
- `~/naka/design_briefs/*.md` — Claude Design 用アーキテクチャ図ブリーフ

---

## 8. 改定履歴

- 2026-04-23: 初版（M3 実機テストの結果を元に Claude と共同執筆）
