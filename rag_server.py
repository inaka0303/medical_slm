#!/usr/bin/env python3
"""
RAG server (FastAPI) — 既存の rag_db_v2 を HTTP API で提供する。

起動方法:
  CUDA_VISIBLE_DEVICES=1 python3.11 rag_server.py --port 8082

エンドポイント:
  GET  /health                         ヘルスチェック
  POST /search   body: {"query": "...", "n": 5}
       → {"results": [{"title": "...", "text": "...", "score": 0.83, "child_hits": 3, "parent_id": "..."}]}

EMR backend (Go, port 8080) から proxy して、SOAPドラフトのP生成時に参照する。
"""
import argparse
import os
import sys
import time
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import uvicorn

# 環境変数でパス上書き可能 (例: ノートPC では RAG_DB_DIR=~/naka-models/rag_db_v2)
BASE_DIR = os.environ.get("NAKA_BASE_DIR", "/data2/junkanki/naka")
DB_DIR = os.path.expanduser(os.environ.get("RAG_DB_DIR", f"{BASE_DIR}/rag_db_v2"))
EMBEDDING_MODEL = os.environ.get("RAG_EMBEDDING_MODEL", "cl-nagoya/ruri-v3-310m")

# グローバル: 初期化は startup で実行
_client = None
_embedder = None


class RuriEmbedder:
    """build_rag_v2.py と同じ仕様の Ruri-v3 embedder."""
    def __init__(self, model_name=EMBEDDING_MODEL):
        from sentence_transformers import SentenceTransformer
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"[rag_server] Loading Ruri-v3: {model_name} (device={device})...", flush=True)
        self.model = SentenceTransformer(model_name, device=device)
        print(f"[rag_server] Embedding dim: {self.model.get_sentence_embedding_dimension()}", flush=True)

    def embed_query(self, query: str):
        embedding = self.model.encode(
            [f"検索クエリ: {query}"], normalize_embeddings=True,
        )
        return embedding.tolist()[0]


def search_parent_child(query: str, client, embedder, n_child_results=15, n_parent_results=5):
    children_col = client.get_collection("children")
    parents_col = client.get_collection("parents")

    q_emb = embedder.embed_query(query)
    child_results = children_col.query(
        query_embeddings=[q_emb],
        n_results=n_child_results,
    )

    parent_scores = {}
    for meta, dist in zip(child_results["metadatas"][0], child_results["distances"][0]):
        pid = meta["parent_id"]
        score = 1.0 / (1.0 + dist)
        if pid not in parent_scores:
            parent_scores[pid] = {"score": 0.0, "count": 0, "title": meta.get("title", "")}
        parent_scores[pid]["score"] += score
        parent_scores[pid]["count"] += 1

    sorted_parents = sorted(parent_scores.items(), key=lambda x: -x[1]["score"])
    top_parent_ids = [pid for pid, _ in sorted_parents[:n_parent_results]]

    if not top_parent_ids:
        return []

    parent_results = parents_col.get(ids=top_parent_ids, include=["documents", "metadatas"])
    results = []
    for pid, doc, meta in zip(
        parent_results["ids"],
        parent_results["documents"],
        parent_results["metadatas"],
    ):
        results.append({
            "parent_id": pid,
            "text": doc,
            "title": meta.get("title", ""),
            "publication_year": meta.get("publication_year"),
            "score": parent_scores[pid]["score"],
            "child_hits": parent_scores[pid]["count"],
        })
    results.sort(key=lambda x: -x["score"])
    return results


# ============================================================
# FastAPI
# ============================================================
app = FastAPI(title="RAG server (Ruri-v3 + ChromaDB)")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class SearchRequest(BaseModel):
    query: str
    n: Optional[int] = 5


class SearchResult(BaseModel):
    parent_id: str
    text: str
    title: str
    publication_year: Optional[int] = None
    score: float
    child_hits: int


class SearchResponse(BaseModel):
    query: str
    results: List[SearchResult]
    elapsed_ms: int


@app.on_event("startup")
def startup():
    global _client, _embedder
    import chromadb
    print(f"[rag_server] Opening ChromaDB at {DB_DIR}...", flush=True)
    _client = chromadb.PersistentClient(path=DB_DIR)
    _embedder = RuriEmbedder()
    # warm up
    try:
        _ = _embedder.embed_query("ウォームアップ")
        print("[rag_server] ready", flush=True)
    except Exception as e:
        print(f"[rag_server] warmup failed: {e}", flush=True)


@app.get("/health")
def health():
    return {"status": "ok", "db_dir": DB_DIR, "model": EMBEDDING_MODEL}


@app.post("/search", response_model=SearchResponse)
def search(req: SearchRequest):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="query is empty")
    t0 = time.time()
    results = search_parent_child(req.query, _client, _embedder, n_parent_results=req.n or 5)
    elapsed_ms = int((time.time() - t0) * 1000)
    return SearchResponse(query=req.query, results=results, elapsed_ms=elapsed_ms)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8082)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)
