"""
Qwen3.5-0.8B-Base 継続事前学習スクリプト
医療系日本語コーパスでのドメイン適応
"""

import os
import torch
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
    DataCollatorForLanguageModeling,
)
from datasets import load_from_disk

# === 設定 ===
MODEL_DIR = "/home/junkanki/naka/models/qwen3.5-0.8b-base"
DATA_DIR = "/home/junkanki/naka/data/tokenized"
OUTPUT_DIR = "/home/junkanki/naka/output/qwen3.5-0.8b-medical"

# ハイパーパラメータ
NUM_EPOCHS = 3
BATCH_SIZE = 8           # per device
GRAD_ACCUM = 4           # 実効バッチサイズ = 8 * 4 = 32
LEARNING_RATE = 2e-5     # 継続事前学習なので控えめ
WARMUP_RATIO = 0.05
WEIGHT_DECAY = 0.01
SAVE_STEPS = 500
LOGGING_STEPS = 50
MAX_SEQ_LEN = 2048

def main():
    print("Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    print("Loading model...")
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_DIR,
        trust_remote_code=True,
        dtype=torch.bfloat16,  # A100はbf16が最適
        attn_implementation="sdpa",  # PyTorch native scaled dot-product attention
    )
    model.gradient_checkpointing_enable()  # メモリ節約

    print("Loading dataset...")
    dataset = load_from_disk(DATA_DIR)
    train_dataset = dataset["train"]
    eval_dataset = dataset["test"]
    print(f"Train: {len(train_dataset):,} | Val: {len(eval_dataset):,}")

    # Data collator: input_idsからlabelsを自動生成（causal LM）
    data_collator = DataCollatorForLanguageModeling(
        tokenizer=tokenizer,
        mlm=False,  # causal LM（GPT系）なのでMLMはFalse
    )

    # 学習設定
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        num_train_epochs=NUM_EPOCHS,
        per_device_train_batch_size=BATCH_SIZE,
        per_device_eval_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=GRAD_ACCUM,
        learning_rate=LEARNING_RATE,
        warmup_ratio=WARMUP_RATIO,
        weight_decay=WEIGHT_DECAY,
        lr_scheduler_type="cosine",
        bf16=True,                    # A100 bf16
        logging_steps=LOGGING_STEPS,
        save_steps=SAVE_STEPS,
        eval_strategy="steps",
        eval_steps=SAVE_STEPS,
        save_total_limit=3,           # チェックポイント最大3つ保持
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        report_to="none",             # wandb使わない場合
        dataloader_num_workers=4,
        remove_unused_columns=False,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        data_collator=data_collator,
    )

    print("Starting training...")
    trainer.train()

    # 最終モデル保存
    final_dir = os.path.join(OUTPUT_DIR, "final")
    trainer.save_model(final_dir)
    tokenizer.save_pretrained(final_dir)
    print(f"Final model saved to {final_dir}")

if __name__ == "__main__":
    main()
