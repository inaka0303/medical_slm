#!/bin/bash
# ============================================================
# 4台のA100で並列ハイパーパラメータ実験
# GPU 0, 1, 2, 4 を使用（GPU 3 = DGX Display は除外）
# ============================================================
#
# exp1 保守的:    低ランク・低学習率。元の知識を壊さず慎重に医療知識追加
# exp2 バランス:  元ノートブック準拠。比較の基準線
# exp3 積極的:    高ランク・高学習率。医療ドメインに強く寄せる
# exp4 大容量安定: ランク最大・学習率控えめ。表現力を確保しつつ安定学習
# ============================================================

SCRIPT="/home/junkanki/naka/train_unsloth_cpt.py"
LOG_DIR="/home/junkanki/naka/logs"
mkdir -p "$LOG_DIR"

echo "========================================"
echo " Starting 4 parallel experiments"
echo " $(date)"
echo "========================================"
echo ""
echo " exp1 [GPU 0] 保守的:    r=8   alpha=8   lr=2e-5  emb_lr=4e-6"
echo " exp2 [GPU 1] バランス:  r=16  alpha=16  lr=5e-5  emb_lr=1e-5"
echo " exp3 [GPU 2] 積極的:    r=64  alpha=64  lr=1e-4  emb_lr=2e-5"
echo " exp4 [GPU 4] 大容量安定: r=128 alpha=32  lr=3e-5  emb_lr=6e-6"
echo ""

# --- exp1: 保守的 (GPU 0) ---
CUDA_VISIBLE_DEVICES=0 nohup python3 "$SCRIPT" \
    --exp_name exp1_conservative \
    --lora_r 8 \
    --lora_alpha 8 \
    --lr 2e-5 \
    --emb_lr 4e-6 \
    --epochs 3 \
    --scheduler cosine \
    > "$LOG_DIR/exp1_console.log" 2>&1 &
PID1=$!

# --- exp2: バランス (GPU 1) ---
CUDA_VISIBLE_DEVICES=1 nohup python3 "$SCRIPT" \
    --exp_name exp2_balanced \
    --lora_r 16 \
    --lora_alpha 16 \
    --lr 5e-5 \
    --emb_lr 1e-5 \
    --epochs 3 \
    --scheduler cosine \
    > "$LOG_DIR/exp2_console.log" 2>&1 &
PID2=$!

# --- exp3: 積極的 (GPU 2) ---
CUDA_VISIBLE_DEVICES=2 nohup python3 "$SCRIPT" \
    --exp_name exp3_aggressive \
    --lora_r 64 \
    --lora_alpha 64 \
    --lr 1e-4 \
    --emb_lr 2e-5 \
    --epochs 3 \
    --scheduler cosine \
    > "$LOG_DIR/exp3_console.log" 2>&1 &
PID3=$!

# --- exp4: 大容量安定 (GPU 4) ---
CUDA_VISIBLE_DEVICES=3 nohup python3 "$SCRIPT" \
    --exp_name exp4_large_stable \
    --lora_r 128 \
    --lora_alpha 32 \
    --lr 3e-5 \
    --emb_lr 6e-6 \
    --epochs 3 \
    --scheduler cosine \
    > "$LOG_DIR/exp4_console.log" 2>&1 &
PID4=$!

echo "All experiments launched!"
echo "  exp1 PID=$PID1 (GPU 0) 保守的"
echo "  exp2 PID=$PID2 (GPU 1) バランス"
echo "  exp3 PID=$PID3 (GPU 2) 積極的"
echo "  exp4 PID=$PID4 (GPU 4) 大容量安定"
echo ""
echo "Monitor commands:"
echo "  tail -f $LOG_DIR/exp1_console.log"
echo "  tail -n5 $LOG_DIR/exp*_console.log"
echo "  watch nvidia-smi"
