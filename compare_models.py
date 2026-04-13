"""
全モデル一括比較スクリプト

全25モデル（base + 24学習済み）に同じプロンプトを入力し、
出力を一覧で表示・ファイルに保存する。

使い方:
  # 1つのプロンプトで全モデル比較
  CUDA_VISIBLE_DEVICES=0 python3 compare_models.py --prompt "糖尿病の治療において"

  # 定義済みテストプロンプトを全部実行（results/ に保存）
  CUDA_VISIBLE_DEVICES=0 python3 compare_models.py --run_all

  # 特定のモデルだけ比較（カンマ区切り）
  CUDA_VISIBLE_DEVICES=0 python3 compare_models.py --prompt "高血圧の診断" --models base,exp3_aggressive,r6_r64_5ep_aggressive

  # 自由なプロンプトで全モデル比較
  CUDA_VISIBLE_DEVICES=0 python3 compare_models.py --prompt "あなたの好きなプロンプト"
"""

import argparse
import os
import json
from datetime import datetime
from transformers import AutoModelForCausalLM, AutoTokenizer

OUTPUT_BASE = "/home/junkanki/naka/output"
RESULTS_DIR = "/home/junkanki/naka/results"

ALL_MODELS = {
    "base":                   "unsloth/Qwen3.5-0.8B-Base",
    "exp1_conservative":      f"{OUTPUT_BASE}/exp1_conservative/merged",
    "exp2_balanced":          f"{OUTPUT_BASE}/exp2_balanced/merged",
    "exp3_aggressive":        f"{OUTPUT_BASE}/exp3_aggressive/merged",
    "exp4_large_stable":      f"{OUTPUT_BASE}/exp4_large_stable/merged",
    "r2_1epoch_wd001":        f"{OUTPUT_BASE}/r2_1epoch_wd001/merged",
    "r2_5epoch_wd001":        f"{OUTPUT_BASE}/r2_5epoch_wd001/merged",
    "r2_warmup10pct":         f"{OUTPUT_BASE}/r2_warmup10pct/merged",
    "r2_wd01":                f"{OUTPUT_BASE}/r2_wd01/merged",
    "r3_bs2_ga16":            f"{OUTPUT_BASE}/r3_bs2_ga16/merged",
    "r3_bs16_ga2":            f"{OUTPUT_BASE}/r3_bs16_ga2/merged",
    "r3_linear_sched":        f"{OUTPUT_BASE}/r3_linear_sched/merged",
    "r3_constant_sched":      f"{OUTPUT_BASE}/r3_constant_sched/merged",
    "r4_lr1e5":               f"{OUTPUT_BASE}/r4_lr1e5/merged",
    "r4_lr3e5":               f"{OUTPUT_BASE}/r4_lr3e5/merged",
    "r4_lr7e5":               f"{OUTPUT_BASE}/r4_lr7e5/merged",
    "r4_lr2e4":               f"{OUTPUT_BASE}/r4_lr2e4/merged",
    "r5_r16_a8":              f"{OUTPUT_BASE}/r5_r16_a8/merged",
    "r5_r16_a32":             f"{OUTPUT_BASE}/r5_r16_a32/merged",
    "r5_r32_a16":             f"{OUTPUT_BASE}/r5_r32_a16/merged",
    "r5_r32_a64":             f"{OUTPUT_BASE}/r5_r32_a64/merged",
    "r6_r8_5ep_conservative": f"{OUTPUT_BASE}/r6_r8_5ep_conservative/merged",
    "r6_r16_5ep_balanced":    f"{OUTPUT_BASE}/r6_r16_5ep_balanced/merged",
    "r6_r64_5ep_aggressive":  f"{OUTPUT_BASE}/r6_r64_5ep_aggressive/merged",
    "r6_r16_5ep_emb_ratio":   f"{OUTPUT_BASE}/r6_r16_5ep_emb_ratio/merged",
}

# 4つの評価観点に対応するテストプロンプト
TEST_PROMPTS = {
    "medical_knowledge_1": {
        "prompt": "糖尿病の病態生理について説明して",
        "category": "医学基礎知識",
    },
    "medical_knowledge_2": {
        "prompt": "関節リウマチはどんな病気ですか",
        "category": "医学基礎知識",
    },
    "medical_knowledge_3": {
        "prompt": "急性腎障害の診断基準は",
        "category": "医学基礎知識",
    },
    "guideline_1": {
        "prompt": "アフェレシス療法のガイドラインでは",
        "category": "ガイドライン情報",
    },
    "guideline_2": {
        "prompt": "クローン病の治療方針として推奨されるのは",
        "category": "ガイドライン情報",
    },
    "guideline_3": {
        "prompt": "ギラン・バレー症候群に対する血漿交換療法の適応は",
        "category": "ガイドライン情報",
    },
    "clinical_1": {
        "prompt": "70歳男性。主訴は両下肢の浮腫。既往歴に2型糖尿病、高血圧。来院時の検査所見では",
        "category": "カルテ調文章理解",
    },
    "clinical_2": {
        "prompt": "患者はSLEと診断され、ループス腎炎の増悪に対して",
        "category": "カルテ調文章理解",
    },
    "coherence_1": {
        "prompt": "多発性硬化症の治療選択肢について、急性期と維持期に分けて説明すると",
        "category": "回答のまとまり",
    },
    "coherence_2": {
        "prompt": "おなか痛いんだけどどうしたらいい",
        "category": "回答のまとまり",
    },
    "suggest_1": {
        "prompt": "問診情報: 45歳女性。3日前から咳と発熱あり。体温37.8度。食欲低下。既往歴に気管支喘息。\nカルテ記載:",
        "category": "カルテsuggest",
    },
    "suggest_2": {
        "prompt": "問診情報: 62歳男性。1週間前から労作時の息切れが増悪。夜間の呼吸困難あり。既往歴に心筋梗塞(5年前)、2型糖尿病。内服薬はアスピリン、メトホルミン。\nカルテ記載:",
        "category": "カルテsuggest",
    },
}


def generate(model, tokenizer, prompt, max_tokens=256):
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    outputs = model.generate(
        **inputs,
        max_new_tokens=max_tokens,
        temperature=0.7,
        top_p=0.9,
        repetition_penalty=1.1,
        do_sample=True,
    )
    return tokenizer.decode(outputs[0], skip_special_tokens=True)


def run_comparison(prompt, model_names, max_tokens=256):
    """指定モデルでプロンプトを実行し結果を返す"""
    results = {}
    for name in model_names:
        path = ALL_MODELS[name]
        print(f"  Loading {name}...", end="", flush=True)
        model = AutoModelForCausalLM.from_pretrained(path, torch_dtype="auto", device_map="auto")
        tokenizer = AutoTokenizer.from_pretrained(path)
        output = generate(model, tokenizer, prompt, max_tokens)
        results[name] = output
        print(f" done")
        # メモリ解放
        del model, tokenizer
        import torch; torch.cuda.empty_cache()
    return results


def print_results(prompt, results):
    print(f"\n{'='*80}")
    print(f"PROMPT: {prompt}")
    print(f"{'='*80}")
    for name, output in results.items():
        print(f"\n--- {name} ---")
        print(output)
    print(f"\n{'='*80}\n")


def save_results(prompt_id, prompt, category, results):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    filepath = os.path.join(RESULTS_DIR, f"{prompt_id}.txt")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"Prompt ID: {prompt_id}\n")
        f.write(f"Category: {category}\n")
        f.write(f"Prompt: {prompt}\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"{'='*80}\n\n")
        for name, output in results.items():
            f.write(f"--- {name} ---\n")
            f.write(output + "\n\n")
    print(f"  Saved to {filepath}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", type=str, help="テストするプロンプト")
    parser.add_argument("--run_all", action="store_true", help="定義済みテストプロンプトを全部実行")
    parser.add_argument("--models", type=str, default=None,
                        help="比較するモデル（カンマ区切り）。省略時は全モデル")
    parser.add_argument("--max_tokens", type=int, default=256)
    args = parser.parse_args()

    model_names = args.models.split(",") if args.models else list(ALL_MODELS.keys())

    if args.run_all:
        print(f"全 {len(TEST_PROMPTS)} プロンプト × {len(model_names)} モデル を実行します")
        for prompt_id, info in TEST_PROMPTS.items():
            print(f"\n[{prompt_id}] {info['category']}: {info['prompt'][:40]}...")
            results = run_comparison(info["prompt"], model_names, args.max_tokens)
            save_results(prompt_id, info["prompt"], info["category"], results)
            print_results(info["prompt"], results)
        print(f"\n全結果を {RESULTS_DIR}/ に保存しました")
    elif args.prompt:
        results = run_comparison(args.prompt, model_names, args.max_tokens)
        print_results(args.prompt, results)
        save_results("custom_" + datetime.now().strftime("%H%M%S"), args.prompt, "カスタム", results)
    else:
        print("--prompt または --run_all を指定してください")
        print(f"定義済みプロンプト一覧:")
        for pid, info in TEST_PROMPTS.items():
            print(f"  {pid}: [{info['category']}] {info['prompt']}")
