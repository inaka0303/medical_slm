"""
コーパスをトークナイズしてHuggingFace Datasets形式で保存するスクリプト

処理の流れ:
1. corpus.txt を <|endoftext|> で文書単位に分割
2. 各文書をQwen3.5のトークナイザーでトークンIDに変換
3. トークン列を固定長（block_size）のチャンクに連結・分割
4. datasets形式で保存（学習時にそのままDataLoaderに渡せる）
"""

import os
import numpy as np
from transformers import AutoTokenizer
from datasets import Dataset

# === 設定 ===
MODEL_DIR = "/home/junkanki/naka/models/qwen3.5-0.8b-base"
CORPUS_PATH = "/home/junkanki/naka/data/corpus.txt"
OUTPUT_DIR = "/home/junkanki/naka/data/tokenized"
BLOCK_SIZE = 2048  # 1チャンクあたりのトークン数
SEPARATOR = "<|endoftext|>"

# === 1. トークナイザー読み込み ===
print("Loading tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR, trust_remote_code=True)

# endoftextトークンIDを確認
eos_token_id = tokenizer.convert_tokens_to_ids(SEPARATOR)
if eos_token_id is None:
    eos_token_id = tokenizer.eos_token_id
print(f"EOS token: '{SEPARATOR}' -> ID: {eos_token_id}")
print(f"Block size: {BLOCK_SIZE}")

# === 2. コーパスを読み込んで文書単位に分割 ===
print("Reading corpus...")
with open(CORPUS_PATH, "r", encoding="utf-8") as f:
    raw_text = f.read()

documents = raw_text.split(SEPARATOR)
documents = [doc.strip() for doc in documents if doc.strip()]
print(f"Documents: {len(documents)}")

# === 3. 全文書をトークナイズして1つの長いトークン列に連結 ===
# 各文書の間に eos_token_id を挿入する（文書境界を明示）
print("Tokenizing...")
all_token_ids = []
for i, doc in enumerate(documents):
    if i % 1000 == 0:
        print(f"  {i}/{len(documents)} documents tokenized...")
    token_ids = tokenizer.encode(doc, add_special_tokens=False)
    all_token_ids.extend(token_ids)
    all_token_ids.append(eos_token_id)  # 文書の終わりにEOSを追加

total_tokens = len(all_token_ids)
print(f"Total tokens: {total_tokens:,}")

# === 4. 固定長チャンクに分割 ===
# 最後の端数は捨てる（学習効率のため）
n_chunks = total_tokens // BLOCK_SIZE
print(f"Chunks (block_size={BLOCK_SIZE}): {n_chunks:,}")
print(f"Dropped tokens: {total_tokens - n_chunks * BLOCK_SIZE:,}")

all_token_ids = all_token_ids[: n_chunks * BLOCK_SIZE]
chunks = [all_token_ids[i * BLOCK_SIZE : (i + 1) * BLOCK_SIZE] for i in range(n_chunks)]

# === 5. Datasets形式で保存 ===
# input_ids = トークン列、labels = input_ids のコピー（causal LMなので同じ）
print("Creating dataset...")
dataset = Dataset.from_dict({
    "input_ids": chunks,
    "labels": chunks,  # causal LM: labelsはinput_idsと同じ
})

# 90/10 で train/val に分割
split = dataset.train_test_split(test_size=0.1, seed=42)
print(f"Train: {len(split['train']):,} chunks")
print(f"Val:   {len(split['test']):,} chunks")

split.save_to_disk(OUTPUT_DIR)
print(f"\nSaved to {OUTPUT_DIR}")
print("Done!")
