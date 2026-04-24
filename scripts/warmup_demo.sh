#!/usr/bin/env bash
# warmup_demo.sh — デモ患者分の LCP prompt cache を予熱する
#
# 背景 (docs/M3_FIELD_NOTES.md 2026-04-23):
#   llama-server の LCP 類似度 prompt cache (default thold 0.1) が UX を支配する。
#   過去リクエストが cache に入っている患者は 1 秒応答、未登録は 6-9 秒 or timeout。
#
# 本 script は各デモ患者の interview_text を backend から取得し、その内容と共に
# /api/slm/autocomplete を 1 回ずつ叩いて llama-server slot KV cache に prefill 済み状態を
# 作る。デモ直前に実行すると全患者で初回応答が 1 秒以下になる。
#
# 注意:
#   - llama-server 側 prompt cache の LRU で古いエントリは落ちる (8 GB 上限)。
#   - warmup 直後 〜 30 分が最安定。
#   - emr backend + llama-server (ports 8080/8081) が起動している前提。

set -euo pipefail

EMR_URL="${EMR_URL:-http://localhost:8080}"

# デモ対象患者 (MRN, encounter_id, ラベル)
# encounter_id はその時点の DB から取得する動的ルックアップを使うので MRN を基点にする
DEMO_MRNS=(
  "MRN-0022"  # 音声花子 — AF シナリオ、STT 風入力
  "MRN-0021"  # 新規太郎 — 空問診、デモ入力用
  "MRN-0020"  # 池田里奈 — 健診脂質異常、初診
  "MRN-0010"  # 加藤真理 — 未テスト
  "MRN-0007"  # 山本隆  — 2026-04-18 入院の長文 interview
)

if ! curl -s -f "$EMR_URL/api/slm/health" > /dev/null 2>&1; then
  echo "ERROR: emr backend $EMR_URL not reachable" >&2
  exit 1
fi

for MRN in "${DEMO_MRNS[@]}"; do
  # MRN から patient_id を解決
  PID=$(curl -s "$EMR_URL/api/patients" | python3 -c "
import json, sys
for p in json.load(sys.stdin).get('data', []):
    if p.get('mrn') == '$MRN':
        print(p.get('id'))
        break
")
  if [ -z "$PID" ]; then
    echo "  [skip] $MRN: patient not found"
    continue
  fi

  # 最新 encounter を取得
  ENC=$(curl -s "$EMR_URL/api/patients/$PID/encounters" | python3 -c "
import json, sys
arr = json.load(sys.stdin).get('data', [])
if arr:
    # encounter_date の降順で並んでいる想定。最新を使う
    arr_sorted = sorted(arr, key=lambda e: e.get('encounter_date', ''), reverse=True)
    print(arr_sorted[0].get('id'))
")
  if [ -z "$ENC" ]; then
    echo "  [skip] $MRN (pid=$PID): no encounter"
    continue
  fi

  # interview_text を構築 (4 セクション結合)
  # API は {data: [{...}]} 形式で interview note のリストを返す。1 encounter = 1 note 想定。
  INTERVIEW=$(curl -s "$EMR_URL/api/encounters/$ENC/interviews" | python3 -c "
import json, sys
arr = json.load(sys.stdin).get('data') or []
d = arr[0] if arr else {}
parts = []
if d.get('raw_text'):         parts.append('【問診記録】\n' + d['raw_text'])
if d.get('medication_list'):  parts.append('【お薬手帳より】\n' + d['medication_list'])
if d.get('exam_findings'):    parts.append('【診察所見】\n' + d['exam_findings'])
if d.get('lab_results'):      parts.append('【検査結果】\n' + d['lab_results'])
print('\n\n'.join(parts))
")

  INTERVIEW_LEN=$(echo -n "$INTERVIEW" | wc -c)
  if [ "$INTERVIEW_LEN" -lt 10 ]; then
    # interview 無しでも 1 発撃つ (base cache は作れる)
    INTERVIEW=""
  fi

  # warmup リクエスト送信
  # soap_subjective / autocomplete で prefill cache を作る。
  # 少し違う text で 2 回打って、slot cache にも載せる。
  START=$(date +%s%3N)
  for TEXT in "w" "症状"; do
    PAYLOAD=$(python3 -c "
import json
print(json.dumps({
  'text': '$TEXT',
  'context': 'soap_subjective',
  'interview_text': '''$INTERVIEW'''
}, ensure_ascii=False))
")
    curl -s -X POST "$EMR_URL/api/slm/autocomplete" \
      -H "Content-Type: application/json" \
      -d "$PAYLOAD" > /dev/null
  done
  ELAPSED=$(( $(date +%s%3N) - START ))

  echo "  [ok]   $MRN (pid=$PID, enc=$ENC, intv=${INTERVIEW_LEN}c) warmed in ${ELAPSED}ms"
done

echo "warmup 完了"
