"""
workers/milvus_indexer.py
- Index parsed chunks into Milvus collection for fast ANN search.
- Stores chunk_id and embedding; keeps text/meta in Postgres chunks table as canonical source.
- Recommended index params for production demo: HNSW with M=32, efConstruction=200, metric IP.
Usage: python workers/milvus_indexer.py <case_id> [milvus_host] [milvus_port] [collection_prefix]
"""
import sys, os, json, uuid
from pymilvus import connections, FieldSchema, CollectionSchema, DataType, Collection, utility, DataType
from sentence_transformers import SentenceTransformer

def main(case_id, host="milvus", port="19530", coll_prefix="legal_chunks"):
    parsed = f"/data/cases/{case_id}/parsed/chunks.jsonl"
    if not os.path.exists(parsed):
        print("[!] parsed not found:", parsed); return 1
    # connect
    connections.connect(host=host, port=port)
    # ensure embedding model dimension matches your embedder
    model = SentenceTransformer("BAAI/bge-large-zh")
    dim = model.get_sentence_embedding_dimension()
    coll_name = f"{coll_prefix}_{case_id}"
    if utility.has_collection(coll_name):
        print("[i] collection exists, drop and recreate for demo")
        utility.drop_collection(coll_name)
    # schema: pk(auto_id), chunk_id(varchar), embedding(float_vector)
    fields = [
        FieldSchema(name="pk", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=256, description="chunk id"),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dim)
    ]
    schema = CollectionSchema(fields, description="Case chunks vectors")
    coll = Collection(coll_name, schema=schema)
    # load chunks and embed
    chunks = []
    with open(parsed, "r", encoding="utf-8") as f:
        for line in f:
            chunks.append(json.loads(line))
    texts = [c.get("text","") for c in chunks]
    vecs = model.encode(texts, normalize_embeddings=True)
    # prepare insert: chunk_id list and vectors
    chunk_ids = [c.get("chunk_id") for c in chunks]
    entities = [chunk_ids, vecs.tolist()]
    insert_result = coll.insert(entities)
    # create index - tuned parameters
    index_params = {"index_type":"HNSW", "metric_type":"IP", "params":{"M":32, "efConstruction":200}}
    coll.create_index(field_name="embedding", index_params=index_params)
    coll.load()
    print(f"[ok] milvus indexed {len(chunks)} chunks into {coll_name} (dim={dim})")
    return 0

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python workers/milvus_indexer.py <case_id> [host] [port] [coll_prefix]")
        sys.exit(1)
    sys.exit(main(sys.argv[1], *(sys.argv[2:] if len(sys.argv)>2 else [])))
