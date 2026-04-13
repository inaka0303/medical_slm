"""
R2〜R6 実験の再実行スクリプト

- orchestrator.py の ROUNDS 定義をそのまま使用
- 各ラウンド起動後、30秒以内に早期失敗を検知
- 失敗時は status ファイルにエラーを書き出して停止
- 成功時はラウンドごとに結果をまとめる

使い方:
  nohup python3 run_r2_r6.py > logs/run_r2_r6_console.log 2>&1 &
"""

import subprocess
import time
import os
import re
from datetime import datetime
from pathlib import Path

LOG_DIR = "/home/junkanki/naka/logs"
OUTPUT_BASE = "/home/junkanki/naka/output"
SCRIPT = "/home/junkanki/naka/train_unsloth_cpt.py"
STATUS_FILE = "/home/junkanki/naka/run_status.txt"
GPUS = [0, 1, 2, 3]

# orchestrator.py と同じ ROUNDS 定義（R2〜R6）
ROUNDS = {
    2: {
        "concept": "エポック数・warmup・weight_decayの影響を調べる",
        "experiments": [
            {"name": "r2_1epoch_wd001", "gpu": 0, "lora_r": 16, "lora_alpha": 16, "lr": 5e-5, "emb_lr": 1e-5, "epochs": 1, "warmup_ratio": 0.05, "scheduler": "cosine", "concept": "1エポックだけ"},
            {"name": "r2_5epoch_wd001", "gpu": 1, "lora_r": 16, "lora_alpha": 16, "lr": 5e-5, "emb_lr": 1e-5, "epochs": 5, "warmup_ratio": 0.05, "scheduler": "cosine", "concept": "5エポック"},
            {"name": "r2_warmup10pct", "gpu": 2, "lora_r": 16, "lora_alpha": 16, "lr": 5e-5, "emb_lr": 1e-5, "epochs": 3, "warmup_ratio": 0.10, "scheduler": "cosine", "concept": "warmup10%"},
            {"name": "r2_wd01", "gpu": 3, "lora_r": 16, "lora_alpha": 16, "lr": 5e-5, "emb_lr": 1e-5, "epochs": 3, "warmup_ratio": 0.05, "scheduler": "cosine", "concept": "weight_decay=0.01"},
        ],
    },
    3: {
        "concept": "バッチサイズとスケジューラの影響を調べる",
        "experiments": [
            {"name": "r3_bs2_ga16", "gpu": 0, "lora_r": 16, "lora_alpha": 16, "lr": 5e-5, "emb_lr": 1e-5, "epochs": 3, "warmup_ratio": 0.05, "scheduler": "cosine", "batch_size": 2, "grad_accum": 16, "concept": "小バッチ(2)×高蓄積(16)"},
            {"name": "r3_bs16_ga2", "gpu": 1, "lora_r": 16, "lora_alpha": 16, "lr": 5e-5, "emb_lr": 1e-5, "epochs": 3, "warmup_ratio": 0.05, "scheduler": "cosine", "batch_size": 16, "grad_accum": 2, "concept": "大バッチ(16)×低蓄積(2)"},
            {"name": "r3_linear_sched", "gpu": 2, "lora_r": 16, "lora_alpha": 16, "lr": 5e-5, "emb_lr": 1e-5, "epochs": 3, "warmup_ratio": 0.05, "scheduler": "linear", "concept": "linearスケジューラ"},
            {"name": "r3_constant_sched", "gpu": 3, "lora_r": 16, "lora_alpha": 16, "lr": 3e-5, "emb_lr": 6e-6, "epochs": 3, "warmup_ratio": 0.05, "scheduler": "constant_with_warmup", "concept": "constant_with_warmup"},
        ],
    },
    4: {
        "concept": "学習率の細かいグリッド探索",
        "experiments": [
            {"name": "r4_lr1e5", "gpu": 0, "lora_r": 16, "lora_alpha": 16, "lr": 1e-5, "emb_lr": 2e-6, "epochs": 3, "warmup_ratio": 0.05, "scheduler": "cosine", "concept": "lr=1e-5"},
            {"name": "r4_lr3e5", "gpu": 1, "lora_r": 16, "lora_alpha": 16, "lr": 3e-5, "emb_lr": 6e-6, "epochs": 3, "warmup_ratio": 0.05, "scheduler": "cosine", "concept": "lr=3e-5"},
            {"name": "r4_lr7e5", "gpu": 2, "lora_r": 16, "lora_alpha": 16, "lr": 7e-5, "emb_lr": 1.4e-5, "epochs": 3, "warmup_ratio": 0.05, "scheduler": "cosine", "concept": "lr=7e-5"},
            {"name": "r4_lr2e4", "gpu": 3, "lora_r": 16, "lora_alpha": 16, "lr": 2e-4, "emb_lr": 4e-5, "epochs": 3, "warmup_ratio": 0.05, "scheduler": "cosine", "concept": "lr=2e-4"},
        ],
    },
    5: {
        "concept": "LoRAのalpha/r比率の影響を調べる",
        "experiments": [
            {"name": "r5_r16_a8", "gpu": 0, "lora_r": 16, "lora_alpha": 8, "lr": 5e-5, "emb_lr": 1e-5, "epochs": 3, "warmup_ratio": 0.05, "scheduler": "cosine", "concept": "alpha/r=0.5"},
            {"name": "r5_r16_a32", "gpu": 1, "lora_r": 16, "lora_alpha": 32, "lr": 5e-5, "emb_lr": 1e-5, "epochs": 3, "warmup_ratio": 0.05, "scheduler": "cosine", "concept": "alpha/r=2.0"},
            {"name": "r5_r32_a16", "gpu": 2, "lora_r": 32, "lora_alpha": 16, "lr": 5e-5, "emb_lr": 1e-5, "epochs": 3, "warmup_ratio": 0.05, "scheduler": "cosine", "concept": "r=32,alpha/r=0.5"},
            {"name": "r5_r32_a64", "gpu": 3, "lora_r": 32, "lora_alpha": 64, "lr": 5e-5, "emb_lr": 1e-5, "epochs": 3, "warmup_ratio": 0.05, "scheduler": "cosine", "concept": "r=32,alpha/r=2.0"},
        ],
    },
    6: {
        "concept": "ベスト設定付近で5エポック長時間学習",
        "experiments": [
            {"name": "r6_r8_5ep_conservative", "gpu": 0, "lora_r": 8, "lora_alpha": 8, "lr": 2e-5, "emb_lr": 4e-6, "epochs": 5, "warmup_ratio": 0.05, "scheduler": "cosine", "concept": "保守的5ep"},
            {"name": "r6_r16_5ep_balanced", "gpu": 1, "lora_r": 16, "lora_alpha": 16, "lr": 5e-5, "emb_lr": 1e-5, "epochs": 5, "warmup_ratio": 0.05, "scheduler": "cosine", "concept": "バランス5ep"},
            {"name": "r6_r64_5ep_aggressive", "gpu": 2, "lora_r": 64, "lora_alpha": 64, "lr": 7e-5, "emb_lr": 1.4e-5, "epochs": 5, "warmup_ratio": 0.05, "scheduler": "cosine", "concept": "積極的5ep"},
            {"name": "r6_r16_5ep_emb_ratio", "gpu": 3, "lora_r": 16, "lora_alpha": 16, "lr": 5e-5, "emb_lr": 2.5e-5, "epochs": 5, "warmup_ratio": 0.05, "scheduler": "cosine", "concept": "emb_lr=1/2"},
        ],
    },
}


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)


def write_status(status, detail=""):
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        f.write(f"status: {status}\n")
        f.write(f"updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        if detail:
            f.write(f"detail: {detail}\n")


def launch_experiment(exp):
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
    # 前回の失敗ログを消す
    if os.path.exists(console_log):
        os.remove(console_log)

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


def check_early_failure(exp_name, pid):
    """起動直後の失敗を検知。Trueなら失敗。"""
    if is_running(pid):
        return False
    # プロセスが既に終了 → ログを確認
    console_log = os.path.join(LOG_DIR, f"{exp_name}_console.log")
    if not os.path.exists(console_log):
        return True
    with open(console_log, "r") as f:
        content = f.read()
    if "Training started" in content:
        return False  # 学習完了済み（早い実験）
    return True  # 学習開始前に終了 = 失敗


def get_error_message(exp_name):
    console_log = os.path.join(LOG_DIR, f"{exp_name}_console.log")
    if not os.path.exists(console_log):
        return "ログファイルなし"
    with open(console_log, "r") as f:
        content = f.read()
    # 最後の数行からエラーを探す
    lines = content.strip().split("\n")
    error_lines = [l for l in lines[-20:] if "Error" in l or "error" in l.lower() or "failed" in l.lower() or "Traceback" in l]
    if error_lines:
        return error_lines[-1][:200]
    return lines[-1][:200] if lines else "空のログ"


def get_final_loss(exp_name):
    console_log = os.path.join(LOG_DIR, f"{exp_name}_console.log")
    if not os.path.exists(console_log):
        return None
    with open(console_log, "r") as f:
        content = f.read()
    losses = re.findall(r"Final train loss:\s*([\d.]+)", content)
    if losses:
        return float(losses[-1])
    losses = re.findall(r"'loss':\s*'?([\d.]+)", content)
    if losses:
        return float(losses[-1])
    return None


if __name__ == "__main__":
    start_time = datetime.now()
    log("=" * 70)
    log("R2〜R6 実験再実行 開始")
    log("=" * 70)
    write_status("running", "R2〜R6 開始")

    for round_num in sorted(ROUNDS.keys()):
        round_info = ROUNDS[round_num]
        log("")
        log(f"{'#'*70}")
        log(f"Round {round_num}: {round_info['concept']}")
        log(f"{'#'*70}")
        write_status("running", f"Round {round_num} 起動中")

        # 起動
        pids = []
        for exp in round_info["experiments"]:
            pid = launch_experiment(exp)
            pids.append(pid)
            log(f"  Launched {exp['name']} on GPU {exp['gpu']} (PID {pid}) - {exp['concept']}")
            time.sleep(2)

        # 早期失敗チェック（30秒待ってから）
        log("  早期失敗チェック中（30秒待機）...")
        time.sleep(30)
        failed = []
        for exp, pid in zip(round_info["experiments"], pids):
            if check_early_failure(exp["name"], pid):
                err = get_error_message(exp["name"])
                failed.append((exp["name"], err))
                log(f"  *** FAILED: {exp['name']} - {err}")

        if failed:
            detail = "; ".join(f"{n}: {e}" for n, e in failed)
            write_status("error", f"Round {round_num} 早期失敗: {detail}")
            log(f"  Round {round_num} で {len(failed)}/{len(pids)} 件失敗。停止します。")
            log(f"  run_status.txt を確認してください。")
            exit(1)

        log(f"  全 {len(pids)} 実験が正常起動")
        write_status("running", f"Round {round_num} 学習中 ({len(pids)}実験)")

        # 完了待ち（2分おき + 途中失敗チェック）
        while any(is_running(pid) for pid in pids):
            running = sum(1 for pid in pids if is_running(pid))
            log(f"  ... {running}/{len(pids)} 実験が実行中")
            time.sleep(120)

        # 結果まとめ
        log("")
        log(f"{'='*70}")
        log(f"Round {round_num} Results")
        log(f"{'='*70}")
        all_ok = True
        for exp in round_info["experiments"]:
            loss = get_final_loss(exp["name"])
            if loss:
                log(f"  {exp['name']:35s} | loss={loss:.4f} | {exp['concept']}")
            else:
                err = get_error_message(exp["name"])
                log(f"  {exp['name']:35s} | loss=FAILED | {err}")
                all_ok = False
        log(f"{'='*70}")

        if not all_ok:
            write_status("error", f"Round {round_num} で一部実験のloss取得に失敗")
            log("  一部実験が失敗した可能性あり。続行します。")

        write_status("running", f"Round {round_num} 完了。次のラウンドへ")

    # 全体まとめ
    elapsed = (datetime.now() - start_time).total_seconds() / 3600
    log("")
    log(f"{'='*70}")
    log(f"ALL ROUNDS (R2-R6) COMPLETED")
    log(f"Total time: {elapsed:.1f} hours")
    log(f"{'='*70}")

    log("")
    log("Final Loss Summary (lower is better):")
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

    write_status("completed", f"全ラウンド完了。{elapsed:.1f}時間。{len(all_results)}実験成功")
