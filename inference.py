"""
学習済みモデルの推論スクリプト

使い方:
  CUDA_VISIBLE_DEVICES=0 python3 inference.py --model exp3_aggressive --prompt "糖尿病の治療において"
  CUDA_VISIBLE_DEVICES=0 python3 inference.py --model base --prompt "糖尿病の治療において"

モデル一覧:
  base              ... ベースモデル（未学習） unsloth/Qwen3.5-0.8B-Base
  exp1_conservative ... r=8,  alpha=8,   lr=2e-5  (loss=2.07)
  exp2_balanced     ... r=16, alpha=16,  lr=5e-5  (loss=1.88)
  exp3_aggressive   ... r=64, alpha=64,  lr=1e-4  (loss=1.52, ベスト) ※デフォルト
  exp4_large_stable ... r=128, alpha=128, lr=5e-5 (loss=1.73)

オプション:
  --model             使用するモデル（上記から選択、デフォルト: exp3_aggressive）
  --prompt            入力プロンプト（デフォルト: "糖尿病の治療において"）
  --max_tokens        最大生成トークン数（デフォルト: 256）
  --temperature       温度（デフォルト: 0.7）
  --top_p             top-p（デフォルト: 0.9）
  --repetition_penalty 繰り返しペナルティ（デフォルト: 1.1）

実行例:
  # 全モデル比較
  for m in base exp1_conservative exp2_balanced exp3_aggressive exp4_large_stable; do
    CUDA_VISIBLE_DEVICES=0 python3 inference.py --model $m --prompt "高血圧の診断基準は"
  done
"""

import argparse
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_MAP = {
    "base": "unsloth/Qwen3.5-0.8B-Base",
    "exp1_conservative": "/home/junkanki/naka/output/exp1_conservative/merged",
    "exp2_balanced": "/home/junkanki/naka/output/exp2_balanced/merged",
    "exp3_aggressive": "/home/junkanki/naka/output/exp3_aggressive/merged",
    "exp4_large_stable": "/home/junkanki/naka/output/exp4_large_stable/merged",
}

parser = argparse.ArgumentParser()
parser.add_argument("--model", type=str, default="exp3_aggressive",
                    choices=MODEL_MAP.keys(), help="使用するモデル")
parser.add_argument("--prompt", type=str, default="糖尿病の治療において",
                    help="入力プロンプト")
parser.add_argument("--max_tokens", type=int, default=256, help="最大生成トークン数")
parser.add_argument("--temperature", type=float, default=0.7)
parser.add_argument("--top_p", type=float, default=0.9)
parser.add_argument("--repetition_penalty", type=float, default=1.1)
args = parser.parse_args()

model_path = MODEL_MAP[args.model]
print(f"Loading: {args.model} ({model_path})")

model = AutoModelForCausalLM.from_pretrained(model_path, torch_dtype="auto", device_map="auto")
tokenizer = AutoTokenizer.from_pretrained(model_path)

inputs = tokenizer(args.prompt, return_tensors="pt").to(model.device)
outputs = model.generate(
    **inputs,
    max_new_tokens=args.max_tokens,
    temperature=args.temperature,
    top_p=args.top_p,
    repetition_penalty=args.repetition_penalty,
)

print(f"\n{'='*60}")
print(f"Model: {args.model}")
print(f"Prompt: {args.prompt}")
print(f"{'='*60}")
print(tokenizer.decode(outputs[0], skip_special_tokens=True))
