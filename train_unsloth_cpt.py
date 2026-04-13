"""
Qwen3.5-0.8B-Base LoRA継続事前学習スクリプト（Unsloth版）
ベース: https://github.com/unslothai/notebooks/blob/main/nb/Mistral_v0.3_(7B)-CPT.ipynb

方式: LoRA（FFTではない）
データ: 医療系日本語コーパス（ガイドライン2,257件 + カルテ6,242件）

使い方:
  CUDA_VISIBLE_DEVICES=0 python3 train_unsloth_cpt.py --exp_name exp1 --lr 5e-5 --epochs 3
"""

import os
import sys
import logging
import argparse
from datetime import datetime

import torch

# ============================================================
# 引数パーサー（実験ごとに変えたいパラメータを外から指定）
# ============================================================
parser = argparse.ArgumentParser()
parser.add_argument("--exp_name", type=str, default="default", help="実験名")
parser.add_argument("--lora_r", type=int, default=16, help="LoRAランク")
parser.add_argument("--lora_alpha", type=int, default=16, help="LoRA alpha")
parser.add_argument("--lr", type=float, default=5e-5, help="LoRA本体の学習率")
parser.add_argument("--emb_lr", type=float, default=1e-5, help="embed/lm_head の学習率")
parser.add_argument("--epochs", type=int, default=3, help="エポック数")
parser.add_argument("--batch_size", type=int, default=8, help="バッチサイズ")
parser.add_argument("--grad_accum", type=int, default=4, help="勾配蓄積回数")
parser.add_argument("--warmup_ratio", type=float, default=0.05, help="Warmup比率")
parser.add_argument("--scheduler", type=str, default="cosine", help="LRスケジューラ")
parser.add_argument("--weight_decay", type=float, default=0.001, help="Weight decay")
args = parser.parse_args()

# ============================================================
# CCE無効化（継続事前学習では必須）— 元ノートブック Cell 2
# ============================================================
os.environ["UNSLOTH_RETURN_LOGITS"] = "1"

# ============================================================
# ★ ハイパーパラメータ一覧
# ============================================================
# --- モデル（固定） ---
MODEL_NAME = "unsloth/Qwen3.5-0.8B-Base"
MAX_SEQ_LENGTH = 2048
LOAD_IN_4BIT = False

# --- LoRA（実験ごとに変動） ---
LORA_R = args.lora_r
LORA_ALPHA = args.lora_alpha
LORA_DROPOUT = 0
USE_RSLORA = True

# --- 学習（実験ごとに変動） ---
NUM_EPOCHS = args.epochs
BATCH_SIZE = args.batch_size
GRAD_ACCUM = args.grad_accum
LEARNING_RATE = args.lr
EMBEDDING_LR = args.emb_lr
WARMUP_RATIO = args.warmup_ratio
WEIGHT_DECAY = args.weight_decay
LR_SCHEDULER = args.scheduler
OPTIM = "adamw_8bit"
SEED = 3407

# --- 保存・ログ ---
EXP_NAME = args.exp_name
OUTPUT_DIR = f"/home/junkanki/naka/output/{EXP_NAME}"
LORA_DIR = f"/home/junkanki/naka/output/{EXP_NAME}/lora"
MERGED_DIR = f"/home/junkanki/naka/output/{EXP_NAME}/merged"
LOGGING_STEPS = 1
SAVE_STEPS = 500
SAVE_TOTAL_LIMIT = 2

# --- データ（固定） ---
CORPUS_PATH = "/home/junkanki/naka/data/corpus.txt"
SEPARATOR = "<|endoftext|>"

# ============================================================
# ログ設定（コンソール + ファイルに同時出力）
# ============================================================
LOG_DIR = "/home/junkanki/naka/logs"
os.makedirs(LOG_DIR, exist_ok=True)
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
logger.info(f"Log file: {log_file}")
logger.info("=" * 60)
logger.info("ハイパーパラメータ")
logger.info("=" * 60)
logger.info(f"  MODEL_NAME        = {MODEL_NAME}")
logger.info(f"  MAX_SEQ_LENGTH    = {MAX_SEQ_LENGTH}")
logger.info(f"  LOAD_IN_4BIT      = {LOAD_IN_4BIT}")
logger.info(f"  LORA_R            = {LORA_R}")
logger.info(f"  LORA_ALPHA        = {LORA_ALPHA}")
logger.info(f"  USE_RSLORA        = {USE_RSLORA}")
logger.info(f"  NUM_EPOCHS        = {NUM_EPOCHS}")
logger.info(f"  BATCH_SIZE        = {BATCH_SIZE}")
logger.info(f"  GRAD_ACCUM        = {GRAD_ACCUM}")
logger.info(f"  effective batch   = {BATCH_SIZE * GRAD_ACCUM}")
logger.info(f"  LEARNING_RATE     = {LEARNING_RATE}")
logger.info(f"  EMBEDDING_LR      = {EMBEDDING_LR}")
logger.info(f"  WARMUP_RATIO      = {WARMUP_RATIO}")
logger.info(f"  WEIGHT_DECAY      = {WEIGHT_DECAY}")
logger.info(f"  LR_SCHEDULER      = {LR_SCHEDULER}")
logger.info(f"  OPTIM             = {OPTIM}")
logger.info("=" * 60)

# ============================================================
# モデル読み込み — 元ノートブック Cell 3
# ============================================================
from unsloth import FastLanguageModel

logger.info(f"Loading model: {MODEL_NAME}")
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=MODEL_NAME,
    max_seq_length=MAX_SEQ_LENGTH,
    dtype=None,
    load_in_4bit=LOAD_IN_4BIT,
)
# Qwen3.5はVLモデルとして読み込まれるため、tokenizer.tokenizerが実体
if hasattr(tokenizer, "tokenizer"):
    inner_tokenizer = tokenizer.tokenizer
    logger.info(f"Model loaded. Vocab size: {inner_tokenizer.vocab_size}")
else:
    inner_tokenizer = tokenizer
    logger.info(f"Model loaded. Vocab size: {len(tokenizer)}")

# ============================================================
# LoRA設定 — 元ノートブック Cell 4
# ============================================================
logger.info("Applying LoRA adapters...")
model = FastLanguageModel.get_peft_model(
    model,
    r=LORA_R,
    target_modules=[
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj",
        "embed_tokens", "lm_head",
    ],
    lora_alpha=LORA_ALPHA,
    lora_dropout=LORA_DROPOUT,
    bias="none",
    use_gradient_checkpointing="unsloth",
    random_state=SEED,
    use_rslora=USE_RSLORA,
    loftq_config=None,
)

trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
total = sum(p.numel() for p in model.parameters())
logger.info(f"Trainable params: {trainable:,} / {total:,} ({100*trainable/total:.2f}%)")

# ============================================================
# データ準備 — 元ノートブック Cell 5-6
# ============================================================
from datasets import Dataset

logger.info(f"Reading corpus from {CORPUS_PATH}")
with open(CORPUS_PATH, "r", encoding="utf-8") as f:
    raw_text = f.read()

documents = raw_text.split(SEPARATOR)
documents = [doc.strip() for doc in documents if doc.strip()]
logger.info(f"Documents: {len(documents)}")

EOS_TOKEN = inner_tokenizer.eos_token if hasattr(tokenizer, "tokenizer") else tokenizer.eos_token

def formatting_prompts_func(examples):
    outputs = []
    for text in examples["text"]:
        outputs.append(text + EOS_TOKEN)
    return {"text": outputs}

dataset = Dataset.from_dict({"text": documents})
dataset = dataset.map(formatting_prompts_func, batched=True)
logger.info(f"Dataset size: {len(dataset)} documents")

# ============================================================
# Trainer設定 — 元ノートブック Cell 7
# ============================================================
from unsloth import UnslothTrainer, UnslothTrainingArguments

logger.info("Setting up UnslothTrainer...")
trainer = UnslothTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=dataset,
    dataset_text_field="text",
    max_seq_length=MAX_SEQ_LENGTH,
    dataset_num_proc=4,
    args=UnslothTrainingArguments(
        per_device_train_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=GRAD_ACCUM,
        num_train_epochs=NUM_EPOCHS,
        warmup_ratio=WARMUP_RATIO,
        learning_rate=LEARNING_RATE,
        embedding_learning_rate=EMBEDDING_LR,
        logging_steps=LOGGING_STEPS,
        logging_first_step=True,
        optim=OPTIM,
        weight_decay=WEIGHT_DECAY,
        lr_scheduler_type=LR_SCHEDULER,
        seed=SEED,
        output_dir=OUTPUT_DIR,
        save_steps=SAVE_STEPS,
        save_total_limit=SAVE_TOTAL_LIMIT,
        report_to="none",
        bf16=True,
    ),
)

# ============================================================
# 学習実行 — 元ノートブック Cell 8-9
# ============================================================
gpu_stats = torch.cuda.get_device_properties(0)
start_gpu_memory = round(torch.cuda.max_memory_reserved() / 1024 / 1024 / 1024, 3)
max_memory = round(gpu_stats.total_memory / 1024 / 1024 / 1024, 3)
logger.info(f"GPU = {gpu_stats.name}. Max memory = {max_memory} GB.")
logger.info(f"{start_gpu_memory} GB of memory reserved before training.")

logger.info("=" * 60)
logger.info("Training started")
logger.info("=" * 60)
trainer_stats = trainer.train()

# ============================================================
# 学習統計 — 元ノートブック Cell 15
# ============================================================
used_memory = round(torch.cuda.max_memory_reserved() / 1024 / 1024 / 1024, 3)
used_memory_for_lora = round(used_memory - start_gpu_memory, 3)
used_percentage = round(used_memory / max_memory * 100, 3)
lora_percentage = round(used_memory_for_lora / max_memory * 100, 3)

logger.info("=" * 60)
logger.info("Training completed")
logger.info("=" * 60)
logger.info(f"Training time: {trainer_stats.metrics['train_runtime']:.1f}s "
            f"({trainer_stats.metrics['train_runtime']/60:.1f}min)")
logger.info(f"Final train loss: {trainer_stats.metrics.get('train_loss', 'N/A')}")
logger.info(f"Peak reserved memory = {used_memory} GB ({used_percentage}% of max)")
logger.info(f"Memory for LoRA training = {used_memory_for_lora} GB ({lora_percentage}% of max)")

# ============================================================
# モデル保存 — 元ノートブック Cell 18, 21
# ============================================================
logger.info(f"Saving LoRA adapters to {LORA_DIR}")
os.makedirs(LORA_DIR, exist_ok=True)
model.save_pretrained(LORA_DIR)
tokenizer.save_pretrained(LORA_DIR)

logger.info(f"Saving merged model (16bit) to {MERGED_DIR}")
model.save_pretrained_merged(MERGED_DIR, tokenizer, save_method="merged_16bit")

logger.info(f"Experiment {EXP_NAME} completed!")
