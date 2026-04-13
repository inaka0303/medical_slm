#!/bin/bash
# 学習の監視スクリプト
# 使い方: bash monitor.sh

echo "========================================"
echo " 学習状況モニター $(date)"
echo "========================================"
echo ""

# ステータスファイル
if [ -f /home/junkanki/naka/run_status.txt ]; then
    echo "--- run_status.txt ---"
    cat /home/junkanki/naka/run_status.txt
    echo ""
else
    echo "run_status.txt が見つかりません（まだ起動前？）"
    echo ""
fi

# 実行中のtrainプロセス
echo "--- 実行中の学習プロセス ---"
ps aux | grep train_unsloth_cpt | grep -v grep | awk '{printf "  PID=%s GPU=%s\n", $2, $0}' | head -10
RUNNING=$(ps aux | grep train_unsloth_cpt | grep -v grep | wc -l)
echo "  合計: ${RUNNING} プロセス"
echo ""

# GPU使用状況
echo "--- GPU使用状況 ---"
nvidia-smi --query-gpu=index,name,memory.used,memory.total,utilization.gpu --format=csv,noheader 2>/dev/null
echo ""

# 各実験の最終loss（最新5行）
echo "--- 各実験ログの末尾 ---"
for f in /home/junkanki/naka/logs/r{2,3,4,5,6}_*_console.log; do
    if [ -f "$f" ]; then
        name=$(basename "$f" _console.log)
        last=$(tail -1 "$f" 2>/dev/null)
        loss=$(grep -o "Final train loss: [0-9.]*" "$f" 2>/dev/null | tail -1)
        if [ -n "$loss" ]; then
            echo "  $name: $loss"
        elif [ -n "$last" ]; then
            echo "  $name: $(echo "$last" | head -c 100)"
        else
            echo "  $name: (空)"
        fi
    fi
done
echo ""
