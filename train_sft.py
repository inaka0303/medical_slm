"""
CPT済みモデルに対する LoRA SFT（Instruction Tuning）スクリプト

CPTで獲得した医療知識を保持しつつ、指示追従能力を追加する。
データ: sft_data_2.jsonl (messages形式, 3194件)

使い方:
  CUDA_VISIBLE_DEVICES=0 python3 train_sft.py \
    --base_model /home/junkanki/naka/output/exp4_large_stable/merged \
    --exp_name sft_exp4_large_stable \
    --lr 2e-5 --epochs 3
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime

import torch

# ============================================================
# 引数パーサー
# ============================================================
parser = argparse.ArgumentParser()
parser.add_argument("--base_model", type=str, required=True, help="CPT済みmergedモデルのパス")
parser.add_argument("--exp_name", type=str, default="sft_default", help="実験名")
parser.add_argument("--lora_r", type=int, default=16, help="LoRAランク")
parser.add_argument("--lora_alpha", type=int, default=16, help="LoRA alpha")
parser.add_argument("--lr", type=float, default=2e-5, help="学習率")
parser.add_argument("--epochs", type=int, default=3, help="エポック数")
parser.add_argument("--batch_size", type=int, default=4, help="バッチサイズ")
parser.add_argument("--grad_accum", type=int, default=8, help="勾配蓄積回数")
parser.add_argument("--warmup_ratio", type=float, default=0.05, help="Warmup比率")
parser.add_argument("--weight_decay", type=float, default=0.001, help="Weight decay")
args = parser.parse_args()

# ============================================================
# 定数
# ============================================================
MAX_SEQ_LENGTH = 2048
LOAD_IN_4BIT = False
SEED = 3407
SFT_DATA_PATH = "/home/junkanki/naka/data/sft_data_2.jsonl"

EXP_NAME = args.exp_name
OUTPUT_DIR = f"/home/junkanki/naka/output/{EXP_NAME}"
LORA_DIR = f"{OUTPUT_DIR}/lora"
MERGED_DIR = f"{OUTPUT_DIR}/merged"

LOG_DIR = "/home/junkanki/naka/logs"
os.makedirs(LOG_DIR, exist_ok=True)

# ============================================================
# ログ設定
# ============================================================
log_file = os.path.join(LOG_DIR, f"{EXP_NAME}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

logger.info(f"Experiment: {EXP_NAME}")
logger.info(f"Base model: {args.base_model}")
logger.info("=" * 60)
logger.info("SFT ハイパーパラメータ")
logger.info("=" * 60)
logger.info(f"  BASE_MODEL        = {args.base_model}")
logger.info(f"  LORA_R            = {args.lora_r}")
logger.info(f"  LORA_ALPHA        = {args.lora_alpha}")
logger.info(f"  LEARNING_RATE     = {args.lr}")
logger.info(f"  NUM_EPOCHS        = {args.epochs}")
logger.info(f"  BATCH_SIZE        = {args.batch_size}")
logger.info(f"  GRAD_ACCUM        = {args.grad_accum}")
logger.info(f"  effective batch   = {args.batch_size * args.grad_accum}")
logger.info("=" * 60)

# ============================================================
# モデル読み込み
# ============================================================
from unsloth import FastLanguageModel

logger.info(f"Loading CPT model: {args.base_model}")
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=args.base_model,
    max_seq_length=MAX_SEQ_LENGTH,
    dtype=None,
    load_in_4bit=LOAD_IN_4BIT,
)

# ============================================================
# Chat template 設定（Qwen の ChatML形式）
# ============================================================
# Qwen3.5-Base は chat template が未設定の場合があるため明示的に設定
if tokenizer.chat_template is None:
    logger.info("Setting ChatML chat template")
    tokenizer.chat_template = (
        "{% for message in messages %}"
        "{% if message['role'] == 'system' %}"
        "<|im_start|>system\n{{ message['content'] }}<|im_end|>\n"
        "{% elif message['role'] == 'user' %}"
        "<|im_start|>user\n{{ message['content'] }}<|im_end|>\n"
        "{% elif message['role'] == 'assistant' %}"
        "<|im_start|>assistant\n{{ message['content'] }}<|im_end|>\n"
        "{% endif %}"
        "{% endfor %}"
        "{% if add_generation_prompt %}<|im_start|>assistant\n{% endif %}"
    )

# ============================================================
# LoRA 設定（SFTではembed_tokens/lm_headは含めない）
# ============================================================
logger.info("Applying LoRA adapters for SFT...")
model = FastLanguageModel.get_peft_model(
    model,
    r=args.lora_r,
    target_modules=[
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj",
    ],
    lora_alpha=args.lora_alpha,
    lora_dropout=0,
    bias="none",
    use_gradient_checkpointing="unsloth",
    random_state=SEED,
    use_rslora=True,
    loftq_config=None,
)

trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
total = sum(p.numel() for p in model.parameters())
logger.info(f"Trainable params: {trainable:,} / {total:,} ({100*trainable/total:.2f}%)")

# ============================================================
# データ準備
# ============================================================
from datasets import Dataset

logger.info(f"Loading SFT data from {SFT_DATA_PATH}")
with open(SFT_DATA_PATH, "r", encoding="utf-8") as f:
    raw_data = [json.loads(line) for line in f]

logger.info(f"SFT data: {len(raw_data)} records")

def format_chat(example):
    text = tokenizer.apply_chat_template(
        example["messages"], tokenize=False, add_generation_prompt=False
    )
    return {"text": text}

dataset = Dataset.from_list(raw_data)
dataset = dataset.map(format_chat, num_proc=4)
logger.info(f"Dataset formatted: {len(dataset)} records")

# サンプル表示
logger.info(f"Sample formatted text:\n{dataset[0]['text'][:300]}")

# ============================================================
# Trainer 設定
# ============================================================
from trl import SFTTrainer, SFTConfig

logger.info("Setting up SFTTrainer...")
trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=dataset,
    args=SFTConfig(
        dataset_text_field="text",
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        num_train_epochs=args.epochs,
        warmup_ratio=args.warmup_ratio,
        learning_rate=args.lr,
        logging_steps=1,
        logging_first_step=True,
        optim="adamw_8bit",
        weight_decay=args.weight_decay,
        lr_scheduler_type="cosine",
        seed=SEED,
        output_dir=OUTPUT_DIR,
        save_steps=500,
        save_total_limit=2,
        report_to="none",
        bf16=True,
        max_seq_length=MAX_SEQ_LENGTH,
        packing=False,
    ),
)

# ============================================================
# 学習実行
# ============================================================
gpu_stats = torch.cuda.get_device_properties(0)
start_gpu_memory = round(torch.cuda.max_memory_reserved() / 1024 / 1024 / 1024, 3)
max_memory = round(gpu_stats.total_memory / 1024 / 1024 / 1024, 3)
logger.info(f"GPU = {gpu_stats.name}. Max memory = {max_memory} GB.")
logger.info(f"{start_gpu_memory} GB of memory reserved before training.")

logger.info("=" * 60)
logger.info("SFT Training started")
logger.info("=" * 60)
trainer_stats = trainer.train()

# ============================================================
# 学習統計
# ============================================================
used_memory = round(torch.cuda.max_memory_reserved() / 1024 / 1024 / 1024, 3)
used_memory_for_lora = round(used_memory - start_gpu_memory, 3)

logger.info("=" * 60)
logger.info("SFT Training completed")
logger.info("=" * 60)
logger.info(f"Training time: {trainer_stats.metrics['train_runtime']:.1f}s "
            f"({trainer_stats.metrics['train_runtime']/60:.1f}min)")
logger.info(f"Final train loss: {trainer_stats.metrics.get('train_loss', 'N/A')}")
logger.info(f"Peak reserved memory = {used_memory} GB")
logger.info(f"Memory for LoRA training = {used_memory_for_lora} GB")

# ============================================================
# モデル保存
# ============================================================
logger.info(f"Saving LoRA adapters to {LORA_DIR}")
os.makedirs(LORA_DIR, exist_ok=True)
model.save_pretrained(LORA_DIR)
tokenizer.save_pretrained(LORA_DIR)

logger.info(f"Saving merged model (16bit) to {MERGED_DIR}")
model.save_pretrained_merged(MERGED_DIR, tokenizer, save_method="merged_16bit")

logger.info(f"SFT Experiment {EXP_NAME} completed!")
