"""
workers/reranker.py
- Rerank candidate passages using a Cross-Encoder (sentence-transformers CrossEncoder).
Usage:
  python workers/reranker.py "<question>" /data/cases/<case_id>/parsed/chunks.jsonl
Outputs top-K scored passages to stdout as JSON.
"""
import sys, json, os
from sentence_transformers import CrossEncoder

def load_chunks(path):
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)

def main():
    if len(sys.argv) < 3:
        print("Usage: python workers/reranker.py \"<query>\" <chunks.jsonl> [top_k]")
        sys.exit(1)
    query = sys.argv[1]
    chunks_path = sys.argv[2]
    top_k = int(sys.argv[3]) if len(sys.argv) > 3 else 10
    # model name can be changed; using a reasonably small cross-encoder for demo
    model_name = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    model = CrossEncoder(model_name)
    chunks = list(load_chunks(chunks_path))
    pairs = [[query, c.get("text","")] for c in chunks]
    scores = model.predict(pairs, batch_size=16)
    scored = sorted(zip(scores, chunks), key=lambda x: x[0], reverse=True)[:top_k]
    out = []
    for s,c in scored:
        out.append({"score": float(s), "chunk_id": c["chunk_id"], "asset": c.get("meta",{}).get("asset"), "page": c.get("meta",{}).get("page"), "text": c.get("text","")[:1000]})
    print(json.dumps(out, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
