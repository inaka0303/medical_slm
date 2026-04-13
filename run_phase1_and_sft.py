"""
Phase 1 (CPT R7/R8) + SFT 一括実行オーケストレーター

1. R7: CPT 4実験並列 (GPU 0-3)
2. R8: CPT 4実験並列 (GPU 0-3)
3. 推論: R7+R8 の 8モデル (GPU 0)
4. SFT: 既存有望3モデル + R7/R8全8モデル = 11モデル (GPU 0-3, 3バッチ)
5. 推論: SFT 11モデル (GPU 0)

使い方:
  nohup python3 run_phase1_and_sft.py > logs/phase1_sft_console.log 2>&1 &
"""

import subprocess
import time
import os
import re
import json
from datetime import datetime
from pathlib import Path

LOG_DIR = "/home/junkanki/naka/logs"
OUTPUT_BASE = "/home/junkanki/naka/output"
CPT_SCRIPT = "/home/junkanki/naka/train_unsloth_cpt.py"
SFT_SCRIPT = "/home/junkanki/naka/train_sft.py"
COMPARE_SCRIPT = "/home/junkanki/naka/compare_models.py"
STATUS_FILE = "/home/junkanki/naka/run_status.txt"

os.makedirs(LOG_DIR, exist_ok=True)

# ============================================================
# CPT 実験定義
# ============================================================
CPT_ROUNDS = {
    7: {
        "concept": "r=128中心の探索（exp4の知識正確性を伸ばす）",
        "experiments": [
            {"name": "r7_r128_lr3e5_5ep", "gpu": 0, "lora_r": 128, "lora_alpha": 128, "lr": 3e-5, "emb_lr": 6e-6, "epochs": 5, "warmup_ratio": 0.05, "scheduler": "cosine", "concept": "r=128, 慎重lr, 5ep"},
            {"name": "r7_r128_lr5e5_5ep", "gpu": 1, "lora_r": 128, "lora_alpha": 128, "lr": 5e-5, "emb_lr": 1e-5, "epochs": 5, "warmup_ratio": 0.05, "scheduler": "cosine", "concept": "r=128, 標準lr, 5ep（最有望）"},
            {"name": "r7_r128_lr5e5_7ep", "gpu": 2, "lora_r": 128, "lora_alpha": 128, "lr": 5e-5, "emb_lr": 1e-5, "epochs": 7, "warmup_ratio": 0.05, "scheduler": "cosine", "concept": "r=128, 標準lr, 7ep長時間"},
            {"name": "r7_r96_lr5e5_5ep",  "gpu": 3, "lora_r": 96,  "lora_alpha": 96,  "lr": 5e-5, "emb_lr": 1e-5, "epochs": 5, "warmup_ratio": 0.05, "scheduler": "cosine", "concept": "r=96でも十分か確認"},
        ],
    },
    8: {
        "concept": "R7近傍の追加探索（lr・alpha比率）",
        "experiments": [
            {"name": "r8_r128_lr7e5_5ep",  "gpu": 0, "lora_r": 128, "lora_alpha": 128, "lr": 7e-5, "emb_lr": 1.4e-5, "epochs": 5, "warmup_ratio": 0.05, "scheduler": "cosine", "concept": "r=128, やや攻めlr"},
            {"name": "r8_r128_lr4e5_7ep",  "gpu": 1, "lora_r": 128, "lora_alpha": 128, "lr": 4e-5, "emb_lr": 8e-6,   "epochs": 7, "warmup_ratio": 0.05, "scheduler": "cosine", "concept": "r=128, 慎重lr, 長時間"},
            {"name": "r8_r128_a64_5ep",    "gpu": 2, "lora_r": 128, "lora_alpha": 64,  "lr": 5e-5, "emb_lr": 1e-5,   "epochs": 5, "warmup_ratio": 0.05, "scheduler": "cosine", "concept": "alpha/r=0.5 控えめスケール"},
            {"name": "r8_r128_a192_5ep",   "gpu": 3, "lora_r": 128, "lora_alpha": 192, "lr": 5e-5, "emb_lr": 1e-5,   "epochs": 5, "warmup_ratio": 0.05, "scheduler": "cosine", "concept": "alpha/r=1.5 強スケール"},
        ],
    },
}

# SFT対象の既存CPTモデル（評価で有望だった3つ）
EXISTING_CPT_FOR_SFT = [
    "exp3_aggressive",
    "r6_r64_5ep_aggressive",
    "exp4_large_stable",
]

# SFT ハイパーパラメータ（固定）
SFT_PARAMS = {
    "lora_r": 16,
    "lora_alpha": 16,
    "lr": 2e-5,
    "epochs": 3,
    "batch_size": 4,
    "grad_accum": 8,
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


def launch_cpt(exp):
    gpu = exp["gpu"]
    name = exp["name"]
    bs = exp.get("batch_size", 8)
    ga = exp.get("grad_accum", 4)
    console_log = os.path.join(LOG_DIR, f"{name}_console.log")
    if os.path.exists(console_log):
        os.remove(console_log)

    cmd = (
        f"python3 {CPT_SCRIPT}"
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
    full_cmd = f"CUDA_VISIBLE_DEVICES={gpu} nohup {cmd} > {console_log} 2>&1 & echo $!"
    result = subprocess.run(full_cmd, shell=True, capture_output=True, text=True)
    pid = int(result.stdout.strip())
    return pid


def launch_sft(base_model_path, sft_name, gpu):
    console_log = os.path.join(LOG_DIR, f"{sft_name}_console.log")
    if os.path.exists(console_log):
        os.remove(console_log)

    p = SFT_PARAMS
    cmd = (
        f"python3 {SFT_SCRIPT}"
        f" --base_model {base_model_path}"
        f" --exp_name {sft_name}"
        f" --lora_r {p['lora_r']}"
        f" --lora_alpha {p['lora_alpha']}"
        f" --lr {p['lr']}"
        f" --epochs {p['epochs']}"
        f" --batch_size {p['batch_size']}"
        f" --grad_accum {p['grad_accum']}"
    )
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


def wait_for_all(pids, names, check_interval=120):
    while any(is_running(pid) for pid in pids):
        running = sum(1 for pid in pids if is_running(pid))
        log(f"  ... {running}/{len(pids)} 実行中")
        time.sleep(check_interval)


def check_early_failure(name, pid):
    time.sleep(30)
    if is_running(pid):
        return False
    console_log = os.path.join(LOG_DIR, f"{name}_console.log")
    if not os.path.exists(console_log):
        return True
    with open(console_log, "r") as f:
        content = f.read()
    if "Training started" in content or "SFT Training started" in content:
        return False
    return True


def get_final_loss(name):
    console_log = os.path.join(LOG_DIR, f"{name}_console.log")
    if not os.path.exists(console_log):
        return None
    with open(console_log, "r") as f:
        content = f.read()
    losses = re.findall(r"Final (?:train|SFT train) loss:\s*([\d.]+)", content)
    if losses:
        return float(losses[-1])
    losses = re.findall(r"'loss':\s*'?([\d.]+)", content)
    if losses:
        return float(losses[-1])
    return None


def run_inference(model_names_and_paths, gpu=0):
    """複数モデルの推論を実行し results/ に保存"""
    log(f"  推論開始: {len(model_names_and_paths)} モデル")

    for name, path in model_names_and_paths:
        log(f"    推論中: {name}")
        console_log = os.path.join(LOG_DIR, f"infer_{name}_console.log")
        cmd = (
            f"CUDA_VISIBLE_DEVICES={gpu} python3 {COMPARE_SCRIPT}"
            f" --run_all --models {name}"
        )
        # compare_models.py の ALL_MODELS に登録されていない場合があるので
        # 一時的にモデルパスを環境変数で渡す代わりに、直接 inference.py を使う
        # → compare_models は既知モデルのみ対応なので、個別に推論スクリプトを実行
        infer_cmd = f"""CUDA_VISIBLE_DEVICES={gpu} python3 -c "
import json, os
from transformers import AutoModelForCausalLM, AutoTokenizer

model_path = '{path}'
model_name = '{name}'
results_dir = '/home/junkanki/naka/results_phase2'
os.makedirs(results_dir, exist_ok=True)

prompts = {{
    'medical_knowledge_1': '糖尿病の病態生理について説明して',
    'medical_knowledge_2': '関節リウマチはどんな病気ですか',
    'guideline_1': 'アフェレシス療法のガイドラインでは',
    'clinical_1': '70歳男性。主訴は両下肢の浮腫。既往歴に2型糖尿病、高血圧。来院時の検査所見では',
    'coherence_2': 'おなか痛いんだけどどうしたらいい',
    'suggest_1': '問診情報: 45歳女性。3日前から咳と発熱あり。体温37.8度。食欲低下。既往歴に気管支喘息。\\nカルテ記載:',
    'suggest_2': '問診情報: 62歳男性。1週間前から労作時の息切れが増悪。夜間の呼吸困難あり。既往歴に心筋梗塞(5年前)、2型糖尿病。内服薬はアスピリン、メトホルミン。\\nカルテ記載:',
    'soap_s': '以下の問診記録から、S（主観的情報）を記載してください。\\n\\n【問診記録】78歳女性　高血圧・糖尿病で通院中\\n医師「今日はどうされましたか？」\\n患者「先生、この薬飲んでも大丈夫なんですか？」',
}}

print(f'Loading {{model_name}}...')
model = AutoModelForCausalLM.from_pretrained(model_path, torch_dtype='auto', device_map='auto')
tokenizer = AutoTokenizer.from_pretrained(model_path)

out_path = os.path.join(results_dir, f'{{model_name}}.txt')
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(f'Model: {{model_name}}\\nPath: {{model_path}}\\n')
    f.write('='*80 + '\\n\\n')
    for pid, prompt in prompts.items():
        inputs = tokenizer(prompt, return_tensors='pt').to(model.device)
        outputs = model.generate(**inputs, max_new_tokens=256, temperature=0.7, top_p=0.9, repetition_penalty=1.1, do_sample=True)
        text = tokenizer.decode(outputs[0], skip_special_tokens=True)
        f.write(f'--- {{pid}} ---\\nPrompt: {{prompt[:60]}}\\n{{text}}\\n\\n')
        print(f'  {{pid}}: done')

print(f'Saved to {{out_path}}')
del model, tokenizer
import torch; torch.cuda.empty_cache()
" > {console_log} 2>&1"""
        subprocess.run(infer_cmd, shell=True)
    log(f"  推論完了")


# ============================================================
# メイン実行
# ============================================================
if __name__ == "__main__":
    start_time = datetime.now()

    log("=" * 70)
    log("Phase 1 + SFT 一括実行 開始")
    log("=" * 70)
    write_status("running", "Phase 1 + SFT 開始")

    # ============================================================
    # Phase 1: CPT R7, R8
    # ============================================================
    all_cpt_names = []

    for round_num in sorted(CPT_ROUNDS.keys()):
        round_info = CPT_ROUNDS[round_num]
        log(f"")
        log(f"{'#'*70}")
        log(f"CPT Round {round_num}: {round_info['concept']}")
        log(f"{'#'*70}")
        write_status("running", f"CPT Round {round_num}")

        pids = []
        for exp in round_info["experiments"]:
            pid = launch_cpt(exp)
            pids.append(pid)
            log(f"  Launched {exp['name']} on GPU {exp['gpu']} (PID {pid}) - {exp['concept']}")
            all_cpt_names.append(exp["name"])
            time.sleep(2)

        # 早期失敗チェック
        log("  早期失敗チェック中...")
        time.sleep(30)
        for exp, pid in zip(round_info["experiments"], pids):
            if not is_running(pid):
                console_log = os.path.join(LOG_DIR, f"{exp['name']}_console.log")
                if os.path.exists(console_log):
                    with open(console_log) as f:
                        tail = f.read()[-300:]
                    log(f"  *** WARNING: {exp['name']} may have failed: {tail[-100:]}")

        # 完了待ち
        wait_for_all(pids, [e["name"] for e in round_info["experiments"]])

        # 結果
        log(f"{'='*70}")
        log(f"CPT Round {round_num} Results")
        log(f"{'='*70}")
        for exp in round_info["experiments"]:
            loss = get_final_loss(exp["name"])
            loss_str = f"{loss:.4f}" if loss else "FAILED"
            log(f"  {exp['name']:35s} | loss={loss_str} | {exp['concept']}")
        log(f"{'='*70}")

    # ============================================================
    # 推論: R7+R8 モデル
    # ============================================================
    log("")
    log(f"{'#'*70}")
    log("CPT R7+R8 モデルの推論")
    log(f"{'#'*70}")
    write_status("running", "CPT推論中")

    cpt_models = []
    for name in all_cpt_names:
        merged_path = f"{OUTPUT_BASE}/{name}/merged"
        if os.path.exists(merged_path):
            cpt_models.append((name, merged_path))
        else:
            log(f"  SKIP: {name} (merged not found)")
    run_inference(cpt_models)

    # ============================================================
    # Phase 2: SFT
    # ============================================================
    log("")
    log(f"{'#'*70}")
    log("Phase 2: SFT (Instruction Tuning)")
    log(f"{'#'*70}")
    write_status("running", "SFT開始")

    # SFT対象リスト: 既存3 + R7/R8全モデル
    sft_targets = []
    for name in EXISTING_CPT_FOR_SFT:
        merged_path = f"{OUTPUT_BASE}/{name}/merged"
        if os.path.exists(merged_path):
            sft_targets.append((name, merged_path))
    for name in all_cpt_names:
        merged_path = f"{OUTPUT_BASE}/{name}/merged"
        if os.path.exists(merged_path):
            sft_targets.append((name, merged_path))

    log(f"  SFT対象: {len(sft_targets)} モデル")
    for name, path in sft_targets:
        log(f"    - {name}")

    # 4 GPU で並列バッチ実行
    gpus = [0, 1, 2, 3]
    for batch_start in range(0, len(sft_targets), len(gpus)):
        batch = sft_targets[batch_start:batch_start + len(gpus)]
        batch_num = batch_start // len(gpus) + 1
        log(f"")
        log(f"  SFT バッチ {batch_num}: {len(batch)} モデル")
        write_status("running", f"SFT バッチ {batch_num}/{(len(sft_targets)-1)//len(gpus)+1}")

        pids = []
        for i, (cpt_name, cpt_path) in enumerate(batch):
            sft_name = f"sft_{cpt_name}"
            gpu = gpus[i]
            pid = launch_sft(cpt_path, sft_name, gpu)
            pids.append(pid)
            log(f"    Launched sft_{cpt_name} on GPU {gpu} (PID {pid})")
            time.sleep(2)

        # 早期失敗チェック
        time.sleep(30)
        for (cpt_name, _), pid in zip(batch, pids):
            sft_name = f"sft_{cpt_name}"
            if not is_running(pid):
                console_log = os.path.join(LOG_DIR, f"{sft_name}_console.log")
                if os.path.exists(console_log):
                    with open(console_log) as f:
                        tail = f.read()[-300:]
                    log(f"    *** WARNING: {sft_name} may have failed: {tail[-100:]}")

        wait_for_all(pids, [f"sft_{n}" for n, _ in batch])

        # バッチ結果
        for cpt_name, _ in batch:
            sft_name = f"sft_{cpt_name}"
            loss = get_final_loss(sft_name)
            loss_str = f"{loss:.4f}" if loss else "FAILED"
            log(f"    {sft_name:40s} | loss={loss_str}")

    # ============================================================
    # 推論: SFT モデル
    # ============================================================
    log("")
    log(f"{'#'*70}")
    log("SFT モデルの推論")
    log(f"{'#'*70}")
    write_status("running", "SFT推論中")

    sft_models = []
    for cpt_name, _ in sft_targets:
        sft_name = f"sft_{cpt_name}"
        merged_path = f"{OUTPUT_BASE}/{sft_name}/merged"
        if os.path.exists(merged_path):
            sft_models.append((sft_name, merged_path))
        else:
            log(f"  SKIP: {sft_name} (merged not found)")
    run_inference(sft_models)

    # ============================================================
    # 全体まとめ
    # ============================================================
    elapsed = (datetime.now() - start_time).total_seconds() / 3600
    log("")
    log(f"{'='*70}")
    log(f"ALL COMPLETED")
    log(f"Total time: {elapsed:.1f} hours")
    log(f"{'='*70}")

    log("")
    log("CPT Loss Summary:")
    log(f"{'─'*70}")
    for name in all_cpt_names:
        loss = get_final_loss(name)
        loss_str = f"{loss:.4f}" if loss else "FAILED"
        log(f"  {loss_str}  {name}")

    log("")
    log("SFT Loss Summary:")
    log(f"{'─'*70}")
    for cpt_name, _ in sft_targets:
        sft_name = f"sft_{cpt_name}"
        loss = get_final_loss(sft_name)
        loss_str = f"{loss:.4f}" if loss else "FAILED"
        log(f"  {loss_str}  {sft_name}")
    log(f"{'─'*70}")

    log("")
    log(f"推論結果: results_phase2/ を確認してください")

    write_status("completed", f"全完了。{elapsed:.1f}時間。CPT {len(all_cpt_names)}件 + SFT {len(sft_targets)}件")
