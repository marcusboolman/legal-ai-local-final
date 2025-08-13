"""
workers/index_builder.py
- Build BM25-like (text) and vector index using sentence-transformers (bge-large-zh).
- Writes to Postgres(pgvector) via simple SQL upserts.
"""
import os, sys, json, uuid, psycopg2
from sentence_transformers import SentenceTransformer
import numpy as np

def conn(db_url):
    return psycopg2.connect(db_url)

def upsert_chunk(cur, c):
    cur.execute("""INSERT INTO chunks(chunk_id, source_type, source_id, text, meta, page, timecode)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (chunk_id) DO NOTHING""",
                (c["chunk_id"], c["source_type"], c["source_id"], c["text"], json.dumps(c.get("meta",{})), c.get("meta",{}).get("page"), None))

def upsert_vec(cur, chunk_id, vec, model_name):
    cur.execute("""INSERT INTO embeddings(chunk_id, model, vector) VALUES (%s,%s,%s)
                   ON CONFLICT (chunk_id) DO UPDATE SET model=EXCLUDED.model, vector=EXCLUDED.vector""",
                (chunk_id, model_name, vec.tolist()))

def load_jsonl(path):
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)

def main(case_id, db_url, model_name="BAAI/bge-large-zh"):
    parsed = f"/data/cases/{case_id}/parsed/chunks.jsonl"
    if not os.path.exists(parsed):
        print(f"[!] not found: {parsed} (run ocr_parse first)")
        return 1
    model = SentenceTransformer(model_name)
    con = conn(db_url); con.autocommit = True
    cur = con.cursor()
    batch = []
    for c in load_jsonl(parsed):
        upsert_chunk(cur, c)
        batch.append((c["chunk_id"], c["text"]))
    texts = [t for _, t in batch]
    if texts:
        vecs = model.encode(texts, normalize_embeddings=True)
        for (cid,_), v in zip(batch, vecs):
            upsert_vec(cur, cid, np.array(v, dtype=np.float32), model_name)
    cur.close(); con.close()
    print(f"[ok] indexed {len(texts)} chunks for case {case_id}")
    return 0

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python workers/index_builder.py <case_id> <DB_URL> [model_name]")
        sys.exit(1)
    sys.exit(main(sys.argv[1], sys.argv[2], *(sys.argv[3:] if len(sys.argv)>3 else [])))
