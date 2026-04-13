"""
実験オーケストレーター
- 4 GPUで並列実験を回し続ける
- 各ラウンド終了後、結果をまとめて次のラウンドを自動起動
- 16時間で自動停止
"""

import subprocess
import time
import os
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

LOG_DIR = "/home/junkanki/naka/logs"
OUTPUT_BASE = "/home/junkanki/naka/output"
SCRIPT = "/home/junkanki/naka/train_unsloth_cpt.py"
SUMMARY_FILE = "/home/junkanki/naka/logs/experiment_summary.txt"
GPUS = [0, 1, 2, 3]  # CUDA indices (all A100s)
MAX_HOURS = 16

os.makedirs(LOG_DIR, exist_ok=True)

# ============================================================
# 実験ラウンド定義
# ============================================================
# Round 1: 現在実行中（r/alpha/lr を大きく変える）
# Round 2: エポック数・warmup・weight_decayの探索
# Round 3: バッチサイズ・スケジューラの探索
# Round 4: Round1-3のベストを深掘り（学習率の細かいグリッド）
# Round 5: alpha/r比率の探索（スケーリングの影響）
# Round 6: 控えめ設定の長時間学習（5エポック）
# Round 7以降: 予備

ROUNDS = {
    # ---- Round 2: エポック・正則化の探索 ----
    2: {
        "concept": "エポック数・warmup・weight_decayの影響を調べる",
        "experiments": [
            {
                "name": "r2_1epoch_wd001",
                "gpu": 0, "lora_r": 16, "lora_alpha": 16,
                "lr": 5e-5, "emb_lr": 1e-5, "epochs": 1,
                "warmup_ratio": 0.05, "scheduler": "cosine",
                "concept": "1エポックだけ（過学習回避・データを1周だけ見る）",
            },
            {
                "name": "r2_5epoch_wd001",
                "gpu": 1, "lora_r": 16, "lora_alpha": 16,
                "lr": 5e-5, "emb_lr": 1e-5, "epochs": 5,
                "warmup_ratio": 0.05, "scheduler": "cosine",
                "concept": "5エポック（データを5周見る。過学習の兆候を観察）",
            },
            {
                "name": "r2_warmup10pct",
                "gpu": 2, "lora_r": 16, "lora_alpha": 16,
                "lr": 5e-5, "emb_lr": 1e-5, "epochs": 3,
                "warmup_ratio": 0.10, "scheduler": "cosine",
                "concept": "warmup比率を倍に（10%）。安定性向上を狙う",
            },
            {
                "name": "r2_wd01",
                "gpu": 3, "lora_r": 16, "lora_alpha": 16,
                "lr": 5e-5, "emb_lr": 1e-5, "epochs": 3,
                "warmup_ratio": 0.05, "scheduler": "cosine",
                "concept": "weight_decay=0.01（10倍）。正則化を強めて汎化を狙う",
                "extra_args": "--grad_accum 4",  # weight_decay is in script, override via env
            },
        ],
    },
    # ---- Round 3: バッチサイズ・スケジューラの探索 ----
    3: {
        "concept": "バッチサイズとスケジューラの影響を調べる",
        "experiments": [
            {
                "name": "r3_bs2_ga16",
                "gpu": 0, "lora_r": 16, "lora_alpha": 16,
                "lr": 5e-5, "emb_lr": 1e-5, "epochs": 3,
                "warmup_ratio": 0.05, "scheduler": "cosine",
                "batch_size": 2, "grad_accum": 16,
                "concept": "小バッチ(2)×高蓄積(16)=実効32。ノイジーな勾配で汎化を狙う",
            },
            {
                "name": "r3_bs16_ga2",
                "gpu": 1, "lora_r": 16, "lora_alpha": 16,
                "lr": 5e-5, "emb_lr": 1e-5, "epochs": 3,
                "warmup_ratio": 0.05, "scheduler": "cosine",
                "batch_size": 16, "grad_accum": 2,
                "concept": "大バッチ(16)×低蓄積(2)=実効32。安定した勾配",
            },
            {
                "name": "r3_linear_sched",
                "gpu": 2, "lora_r": 16, "lora_alpha": 16,
                "lr": 5e-5, "emb_lr": 1e-5, "epochs": 3,
                "warmup_ratio": 0.05, "scheduler": "linear",
                "concept": "linearスケジューラ。cosineとの比較",
            },
            {
                "name": "r3_constant_sched",
                "gpu": 3, "lora_r": 16, "lora_alpha": 16,
                "lr": 3e-5, "emb_lr": 6e-6, "epochs": 3,
                "warmup_ratio": 0.05, "scheduler": "constant_with_warmup",
                "concept": "学習率一定（warmup後固定）。低めlrで安定学習",
            },
        ],
    },
    # ---- Round 4: 学習率の細かいグリッド（r=16基準）----
    4: {
        "concept": "Round1-3のベスト付近でlrを細かく探索",
        "experiments": [
            {
                "name": "r4_lr1e5",
                "gpu": 0, "lora_r": 16, "lora_alpha": 16,
                "lr": 1e-5, "emb_lr": 2e-6, "epochs": 3,
                "warmup_ratio": 0.05, "scheduler": "cosine",
                "concept": "非常に低い学習率。最小限の変更",
            },
            {
                "name": "r4_lr3e5",
                "gpu": 1, "lora_r": 16, "lora_alpha": 16,
                "lr": 3e-5, "emb_lr": 6e-6, "epochs": 3,
                "warmup_ratio": 0.05, "scheduler": "cosine",
                "concept": "やや控えめな学習率",
            },
            {
                "name": "r4_lr7e5",
                "gpu": 2, "lora_r": 16, "lora_alpha": 16,
                "lr": 7e-5, "emb_lr": 1.4e-5, "epochs": 3,
                "warmup_ratio": 0.05, "scheduler": "cosine",
                "concept": "やや攻めの学習率",
            },
            {
                "name": "r4_lr2e4",
                "gpu": 3, "lora_r": 16, "lora_alpha": 16,
                "lr": 2e-4, "emb_lr": 4e-5, "epochs": 3,
                "warmup_ratio": 0.05, "scheduler": "cosine",
                "concept": "かなり攻めの学習率。過学習リスクを確認",
            },
        ],
    },
    # ---- Round 5: alpha/r比率の探索 ----
    5: {
        "concept": "LoRAのスケーリング（alpha/r比率）の影響を調べる",
        "experiments": [
            {
                "name": "r5_r16_a8",
                "gpu": 0, "lora_r": 16, "lora_alpha": 8,
                "lr": 5e-5, "emb_lr": 1e-5, "epochs": 3,
                "warmup_ratio": 0.05, "scheduler": "cosine",
                "concept": "alpha/r=0.5（LoRA更新を控えめにスケール）",
            },
            {
                "name": "r5_r16_a32",
                "gpu": 1, "lora_r": 16, "lora_alpha": 32,
                "lr": 5e-5, "emb_lr": 1e-5, "epochs": 3,
                "warmup_ratio": 0.05, "scheduler": "cosine",
                "concept": "alpha/r=2.0（LoRA更新を強くスケール）",
            },
            {
                "name": "r5_r32_a16",
                "gpu": 2, "lora_r": 32, "lora_alpha": 16,
                "lr": 5e-5, "emb_lr": 1e-5, "epochs": 3,
                "warmup_ratio": 0.05, "scheduler": "cosine",
                "concept": "alpha/r=0.5だがrは大きめ。表現力↑＋控えめスケール",
            },
            {
                "name": "r5_r32_a64",
                "gpu": 3, "lora_r": 32, "lora_alpha": 64,
                "lr": 5e-5, "emb_lr": 1e-5, "epochs": 3,
                "warmup_ratio": 0.05, "scheduler": "cosine",
                "concept": "alpha/r=2.0でr=32。表現力↑＋強スケール",
            },
        ],
    },
    # ---- Round 6: 長時間学習 ----
    6: {
        "concept": "ベスト設定付近で5エポック長時間学習",
        "experiments": [
            {
                "name": "r6_r8_5ep_conservative",
                "gpu": 0, "lora_r": 8, "lora_alpha": 8,
                "lr": 2e-5, "emb_lr": 4e-6, "epochs": 5,
                "warmup_ratio": 0.05, "scheduler": "cosine",
                "concept": "保守的設定を5エポックで十分に学習",
            },
            {
                "name": "r6_r16_5ep_balanced",
                "gpu": 1, "lora_r": 16, "lora_alpha": 16,
                "lr": 5e-5, "emb_lr": 1e-5, "epochs": 5,
                "warmup_ratio": 0.05, "scheduler": "cosine",
                "concept": "バランス設定を5エポックで十分に学習",
            },
            {
                "name": "r6_r64_5ep_aggressive",
                "gpu": 2, "lora_r": 64, "lora_alpha": 64,
                "lr": 7e-5, "emb_lr": 1.4e-5, "epochs": 5,
                "warmup_ratio": 0.05, "scheduler": "cosine",
                "concept": "積極的設定を5エポック。過学習するか確認",
            },
            {
                "name": "r6_r16_5ep_emb_ratio",
                "gpu": 3, "lora_r": 16, "lora_alpha": 16,
                "lr": 5e-5, "emb_lr": 2.5e-5, "epochs": 5,
                "warmup_ratio": 0.05, "scheduler": "cosine",
                "concept": "emb_lr比率を1/2に変更（通常1/5）。埋め込みを強く学習",
            },
        ],
    },
}


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(SUMMARY_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def launch_experiment(exp):
    """1つの実験を起動してPIDを返す"""
    gpu = exp["gpu"]
    name = exp["name"]
    bs = exp.get("batch_size", 8)
    ga = exp.get("grad_accum", 4)

    cmd = (
        f"python3 {SCRIPT}"
        f" --exp_name {name}"
        f" --lora_r {exp['lora_r']}"
        f" --lora_alpha {exp['lora_alpha']}"
        f" --lr {exp['lr']}"
        f" --emb_lr {exp['emb_lr']}"
        f" --epochs {exp['epochs']}"
        f" --warmup_ratio {exp['warmup_ratio']}"
        f" --scheduler {exp['scheduler']}"
        f" --batch_size {bs}"
        f" --grad_accum {ga}"
    )

    console_log = os.path.join(LOG_DIR, f"{name}_console.log")
    full_cmd = f"CUDA_VISIBLE_DEVICES={gpu} nohup {cmd} > {console_log} 2>&1 & echo $!"
    result = subprocess.run(full_cmd, shell=True, capture_output=True, text=True)
    pid = int(result.stdout.strip())
    return pid


def is_running(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def get_final_loss(exp_name):
    """コンソールログから最終lossを抽出"""
    console_log = os.path.join(LOG_DIR, f"{exp_name}_console.log")
    if not os.path.exists(console_log):
        return None
    with open(console_log, "r") as f:
        content = f.read()
    # 'loss': X.XXXX パターンを探す
    losses = re.findall(r"'loss':\s*([\d.]+)", content)
    if losses:
        return float(losses[-1])
    # train_loss パターン
    losses = re.findall(r"Final train loss:\s*([\d.]+)", content)
    if losses:
        return float(losses[-1])
    return None


def wait_for_round(pids, names):
    """全プロセスの完了を待つ"""
    while any(is_running(pid) for pid in pids):
        running = sum(1 for pid in pids if is_running(pid))
        log(f"  ... {running}/{len(pids)} experiments still running")
        time.sleep(120)  # 2分おきにチェック


def summarize_round(round_num, experiments):
    """ラウンドの結果をまとめる"""
    log(f"")
    log(f"{'='*70}")
    log(f"Round {round_num} Results")
    log(f"{'='*70}")
    for exp in experiments:
        loss = get_final_loss(exp["name"])
        loss_str = f"{loss:.4f}" if loss else "N/A"
        log(f"  {exp['name']:35s} | loss={loss_str} | r={exp['lora_r']:3d} alpha={exp['lora_alpha']:3d} lr={exp['lr']:.0e} | {exp['concept']}")
    log(f"{'='*70}")
    log(f"")


# ============================================================
# メインループ
# ============================================================
if __name__ == "__main__":
    start_time = datetime.now()
    deadline = start_time + timedelta(hours=MAX_HOURS)

    log(f"Orchestrator started. Deadline: {deadline.strftime('%Y-%m-%d %H:%M')}")
    log(f"Max runtime: {MAX_HOURS} hours")
    log(f"")

    # Round 1 は既に実行中なので待つ
    log("Round 1 (already running): waiting for completion...")
    round1_names = [
        "exp1_conservative", "exp2_balanced",
        "exp3_aggressive", "exp4_large_stable",
    ]
    # Round 1のPIDを見つける
    result = subprocess.run(
        "ps aux | grep train_unsloth_cpt | grep -v grep | awk '{print $2}'",
        shell=True, capture_output=True, text=True,
    )
    round1_pids = [int(p) for p in result.stdout.strip().split("\n") if p]
    log(f"  Found {len(round1_pids)} running processes: {round1_pids}")

    if round1_pids:
        wait_for_round(round1_pids, round1_names)

    # Round 1の結果
    log(f"")
    log(f"{'='*70}")
    log(f"Round 1 Results")
    log(f"{'='*70}")
    for name in round1_names:
        loss = get_final_loss(name)
        loss_str = f"{loss:.4f}" if loss else "N/A"
        log(f"  {name:35s} | loss={loss_str}")
    log(f"{'='*70}")
    log(f"")

    # Round 2以降を順次実行
    for round_num in sorted(ROUNDS.keys()):
        if datetime.now() >= deadline:
            log(f"Deadline reached. Stopping.")
            break

        round_info = ROUNDS[round_num]
        log(f"")
        log(f"{'#'*70}")
        log(f"Round {round_num}: {round_info['concept']}")
        log(f"{'#'*70}")

        # 実験を起動
        pids = []
        for exp in round_info["experiments"]:
            pid = launch_experiment(exp)
            pids.append(pid)
            log(f"  Launched {exp['name']} on GPU {exp['gpu']} (PID {pid})")
            log(f"    {exp['concept']}")
            time.sleep(2)  # 少し間隔を空ける

        # 全実験の完了を待つ
        wait_for_round(pids, [e["name"] for e in round_info["experiments"]])

        # 結果まとめ
        summarize_round(round_num, round_info["experiments"])

    # 全体まとめ
    elapsed = (datetime.now() - start_time).total_seconds() / 3600
    log(f"")
    log(f"{'='*70}")
    log(f"ALL EXPERIMENTS COMPLETED")
    log(f"Total time: {elapsed:.1f} hours")
    log(f"{'='*70}")

    # 全実験のlossを一覧
    log(f"")
    log(f"Final Loss Summary (lower is better):")
    log(f"{'─'*70}")
    all_results = []
    for logfile in sorted(Path(LOG_DIR).glob("*_console.log")):
        name = logfile.stem.replace("_console", "")
        loss = get_final_loss(name)
        if loss:
            all_results.append((loss, name))
    all_results.sort()
    for loss, name in all_results:
        log(f"  {loss:.4f}  {name}")
    log(f"{'─'*70}")
