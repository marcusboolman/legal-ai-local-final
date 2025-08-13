from fastapi import FastAPI, UploadFile, Form, Body
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from typing import List, Optional, Any, Dict
from fastapi import BackgroundTasks
import os, json, uuid, subprocess, psycopg2, requests, numpy as np
from sentence_transformers import SentenceTransformer

app = FastAPI(title="Legal RAG & Drafting API", version="0.2.0-rag")

# In-memory stubs for simple demo
CASES = {}
QA_LOG = []

# Load config from env or file
CONF_PATH = "/configs/app.yaml"
CONFIG = {}
try:
    import yaml
    if os.path.exists(CONF_PATH):
        with open(CONF_PATH, "r", encoding="utf-8") as cf:
            CONFIG = yaml.safe_load(cf)
except Exception:
    CONFIG = {}

DB_URL = CONFIG.get("storage", {}).get("db_url", os.environ.get("DB_URL", "postgresql://postgres:pass@postgres:5432/legal"))
LLM_ENDPOINT = CONFIG.get("llm", {}).get("endpoint", os.environ.get("LLM_ENDPOINT", "http://vllm:8000/v1"))
EMBED_MODEL = CONFIG.get("rag", {}).get("embed_model", os.environ.get("EMBED_MODEL", "BAAI/bge-large-zh"))
TOP_K = int(CONFIG.get("rag", {}).get("top_k", os.environ.get("TOP_K", 6)))

# Initialize embedding model once
EMBEDDER = None
def get_embedder():
    global EMBEDDER
    if EMBEDDER is None:
        EMBEDDER = SentenceTransformer(EMBED_MODEL)
    return EMBEDDER

class AskReq(BaseModel):
    case_id: str
    question: str
    time_anchor: Optional[str] = None
    top_k: Optional[int] = None

class GenerateReq(BaseModel):
    case_id: str
    doc_type: str
    template_version: str
    fields: dict = {}

def sql_conn():
    return psycopg2.connect(DB_URL)

@app.post("/ingest/case")
async def ingest_case(case_id: str = Form(...), files: List[UploadFile] = []):
    os.makedirs(f"/data/cases/{case_id}/assets", exist_ok=True)
    saved = []
    for f in files:
        path = f"/data/cases/{case_id}/assets/{f.filename}"
        with open(path, "wb") as out:
            out.write(await f.read())
        saved.append(path)
    CASES[case_id] = {"assets": saved}
    return {"ingest_id": str(uuid.uuid4()), "saved": saved}

@app.get("/case/{case_id}/assets")
async def list_assets(case_id: str):
    return CASES.get(case_id, {"assets": []})

def embed_text(text: str):
    model = get_embedder()
    vec = model.encode([text], normalize_embeddings=True)[0]
    return np.array(vec, dtype=np.float32)

def cosine_sim(a: np.ndarray, b: np.ndarray):
    if a is None or b is None:
        return -1.0
    denom = (np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return -1.0
    return float(np.dot(a, b) / denom)

def fetch_candidate_chunks(case_id: str, query: str, limit:int=50):
    """
    Use PostgreSQL full-text search to fetch candidate chunks for the case.
    Returns list of dicts: {chunk_id, text, meta, vector (may be None)}
    """
    con = sql_conn(); cur = con.cursor()
    # Prefer case-scoped chunks; use plainto_tsquery for simple search
    try:
        cur.execute("""
            SELECT c.chunk_id, c.text, c.meta
            FROM chunks c
            WHERE c.source_type='case' AND c.source_id=%s AND to_tsvector('simple', c.text) @@ plainto_tsquery('simple', %s)
            LIMIT %s
        """, (case_id, query, limit))
        rows = cur.fetchall()
    except Exception as e:
        # fallback: return empty
        print("[warn] full-text search failed:", e)
        rows = []
    candidates = []
    for r in rows:
        cid, text, meta = r
        candidates.append({"chunk_id": cid, "text": text, "meta": meta})
    cur.close(); con.close()
    return candidates

def load_vectors_for_chunk_ids(chunk_ids):
    if not chunk_ids:
        return {}
    con = sql_conn(); cur = con.cursor()
    try:
        # embeddings.vector is stored as pgvector; psycopg2 returns as list when properly configured.
        placeholders = ",".join(["%s"]*len(chunk_ids))
        cur.execute(f"SELECT chunk_id, vector FROM embeddings WHERE chunk_id IN ({placeholders})", tuple(chunk_ids))
        rows = cur.fetchall()
    except Exception as e:
        print("[warn] fetch vectors failed:", e)
        rows = []
    vec_map = {}
    for cid, vec in rows:
        # vec may be returned as list or memoryview; convert to numpy array
        try:
            arr = np.array(vec, dtype=np.float32)
        except Exception:
            # try parsing string like '[0.1, 0.2, ...]'
            try:
                arr = np.array(json.loads(vec), dtype=np.float32)
            except Exception:
                arr = None
        vec_map[cid] = arr
    cur.close(); con.close()
    return vec_map

def build_rag_context(chunks, max_chars=3000):
    """
    Pack top chunks into a single context string with source annotations.
    """
    parts = []
    counted = 0
    for c in chunks:
        header = f"[证据:{c.get('chunk_id')} asset:{c.get('meta',{}).get('asset')} p:{c.get('meta',{}).get('page')}]"
        text = c.get("text","").strip()
        snippet = text.replace("\n", " ")[:1000]
        parts.append(header + "\n" + snippet + "\n")
        counted += len(snippet)
        if counted > max_chars:
            break
    return "\n\n".join(parts)

def call_llm_system(prompt: str, max_tokens:int=1024):
    """
    Call a local LLM endpoint (vLLM or similar OpenAI-compatible). Attempts chat/completions style.
    """
    payload = {
        "model": CONFIG.get("llm",{}).get("model","gpt-3.5"),
        "messages": [{"role":"system","content":"你是法律写作助手，回答需要引用材料并给出引用列表。"},
                     {"role":"user","content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.0
    }
    headers = {"Content-Type":"application/json"}
    try:
        resp = requests.post(LLM_ENDPOINT + "/chat/completions", json=payload, timeout=60, headers=headers)
        if resp.status_code == 200:
            j = resp.json()
            # try to extract text from common schemas
            if "choices" in j and len(j["choices"])>0:
                return j["choices"][0]["message"]["content"]
            elif "data" in j and len(j["data"])>0:
                return j["data"][0].get("text","")
            else:
                return json.dumps(j, ensure_ascii=False)
        else:
            print("[warn] llm call status", resp.status_code, resp.text)
            return None
    except Exception as e:
        print("[warn] llm call failed:", e)
        return None

@app.post("/qa/ask")
async def ask(req: AskReq):
    """
    New retrieval pipeline:
    1) Query Milvus ANN (collection: legal_chunks_{case_id}) for top N candidates using embedding.
    2) If Milvus unavailable or no results, fallback to Postgres full-text + vector cosine scoring.
    3) Call Cross-Encoder rerank service (http://cross_rerank_service:8100/rerank) with top candidates.
    4) Build RAG context from re-ranked top-K and call local LLM.
    """
    top_k = int(req.top_k or TOP_K)
    q_emb = None
    try:
        q_emb = embed_text(req.question)
    except Exception as e:
        print("[warn] embed failed:", e)
        q_emb = None

    candidates = []

    # Try Milvus first for ANN search
    try:
        from pymilvus import connections, Collection, utility
        milvus_host = os.environ.get("MILVUS_HOST", "milvus")
        milvus_port = os.environ.get("MILVUS_PORT", "19530")
        connections.connect(host=milvus_host, port=milvus_port)
        coll_name = f"legal_chunks_{req.case_id}"
        if utility.has_collection(coll_name):
            coll = Collection(coll_name)
            search_params = {"metric_type":"IP", "params":{"ef":50}}
            if q_emb is None:
                # try embedding with embedder directly
                q_emb = embed_text(req.question)
            # perform search; pymilvus expects list of vectors
            results = coll.search([q_emb.tolist()], "embedding", param=search_params, limit=top_k, output_fields=["chunk_id"])
            for res in results[0]:
                # res.entity.get("chunk_id") may not exist depending on schema; try get primary key then fetch chunk from DB
                chunk_id = None
                try:
                    chunk_id = res.entity.get("chunk_id")
                except Exception:
                    try:
                        # fallback to using id from result
                        chunk_id = str(res.id)
                    except:
                        chunk_id = None
                score = float(res.distance) if hasattr(res, "distance") else float(res.score) if hasattr(res, "score") else 0.0
                candidates.append({"chunk_id": chunk_id, "score": score})
        else:
            print(f"[info] milvus collection {coll_name} not found, fallback to postgres search")
    except Exception as e:
        print("[warn] Milvus ANN search failed, will fallback to Postgres/fulltext:", e)

    # If Milvus returned chunk_ids, fetch chunk text/meta from Postgres; else fallback to full-text retrieval
    if candidates:
        # fetch chunk texts from Postgres by ids
        try:
            con = sql_conn(); cur = con.cursor()
            ids = [c["chunk_id"] for c in candidates if c.get("chunk_id")]
            if ids:
                placeholders = ",".join(["%s"]*len(ids))
                cur.execute(f"SELECT chunk_id, text, meta FROM chunks WHERE chunk_id IN ({placeholders})", tuple(ids))
                rows = cur.fetchall()
                id_map = {r[0]: {"chunk_id": r[0], "text": r[1], "meta": r[2]} for r in rows}
                candidates = [id_map.get(cid) for cid in ids if id_map.get(cid)]
            else:
                candidates = []
            cur.close(); con.close()
        except Exception as e:
            print("[warn] fetching chunks by id failed:", e)
            candidates = []
    else:
        # Fallback: Postgres full-text search (existing behavior)
        candidates = fetch_candidate_chunks(req.case_id, req.question, limit=200)

    if not candidates:
        # final fallback: use merged parsed text
        merged = f"/data/cases/{req.case_id}/parsed/merged.txt"
        if os.path.exists(merged):
            with open(merged, "r", encoding="utf-8", errors='ignore') as f:
                text = f.read()[:5000]
            candidates = [{"chunk_id":"merged", "text": text, "meta": {"asset":"merged","page":1}}]

    # Prepare candidates for Cross-Encoder rerank: send top N by current scoring or by order
    # Keep at most 50 to send to reranker
    cand_subset = candidates[:50]
    # If candidates are simple dicts with score only, try to attach text via DB lookup (best-effort)
    for i,c in enumerate(cand_subset):
        if isinstance(c, dict) and "text" not in c:
            # attempt DB lookup
            try:
                con = sql_conn(); cur = con.cursor()
                cur.execute("SELECT text, meta FROM chunks WHERE chunk_id=%s", (c.get("chunk_id"),))
                r = cur.fetchone()
                if r:
                    c["text"] = r[0]; c["meta"] = r[1]
                cur.close(); con.close()
            except Exception as e:
                pass

    # Call cross-encoder rerank service if available
    reranked = None
    try:
        rerank_url = os.environ.get("CROSS_RERANK_URL", "http://cross_rerank_service:8100/rerank")
        payload = {"query": req.question, "candidates": [{"id": c.get("chunk_id"), "text": c.get("text",""), "meta": c.get("meta",{})} for c in cand_subset]}
        import requests as _reqs
        resp = _reqs.post(rerank_url, json=payload, timeout=30)
        if resp.status_code == 200:
            jr = resp.json()
            ranked = jr.get("results", [])
            # Map back to full candidate dicts preserving text/meta
            id_to_candidate = {c.get("chunk_id"): c for c in cand_subset}
            reranked = []
            for item in ranked:
                cid = item.get("id")
                cand = id_to_candidate.get(cid)
                if cand:
                    cand["score"] = item.get("score", 0.0)
                    reranked.append(cand)
    except Exception as e:
        print("[warn] cross-encoder rerank failed:", e)
        reranked = None

    final_candidates = reranked if reranked is not None else cand_subset

    # Take top_k from final_candidates
    top = final_candidates[:top_k]

    # Build RAG context and call LLM
    context = build_rag_context(top)
    prompt = f"请基于下列案件材料片段和现有法条知识，回答用户问题，并在每个事实性陈述后标注证据引用（格式：[证据:chunk_id asset p]）。\n\n【问题】{req.question}\n\n【材料片段】\n{context}\n\n请给出清晰结论和引用清单。"
    llm_out = call_llm_system(prompt)
    if llm_out is None:
        lines = ["无法连接本地LLM，返回检索片段与基本提示：", f"问题：{req.question}", "检索到的材料片段："]
        for c in top:
            lines.append(f"- chunk:{c.get('chunk_id')} asset:{c.get('meta',{}).get('asset')} p:{c.get('meta',{}).get('page')}: {c.get('text')[:200]}")
        answer = "\n".join(lines)
    else:
        answer = llm_out

    citations = [{"chunk_id": c.get("chunk_id"), "asset": c.get("meta",{}).get("asset"), "page": c.get("meta",{}).get("page")} for c in top if c]
    QA_LOG.append({"case_id": req.case_id, "q": req.question, "a": answer, "citations": citations})
    return {"answer": answer, "citations": citations}

@app.post("/doc/generate")
async def generate(req: GenerateReq):
    out_dir = f"/data/cases/{req.case_id}"
    os.makedirs(out_dir, exist_ok=True)
    fields_json = f"{out_dir}/fields.json"
    with open(fields_json, "w", encoding="utf-8") as jf:
        jf.write(json.dumps(req.fields, ensure_ascii=False))
    out_docx = f"{out_dir}/{req.doc_type}-{req.template_version}.docx"
    # Attempt render via workers/render_docx
    os.system(f"python /app/../workers/render_docx.py {req.doc_type} {req.template_version} {fields_json} {out_docx}")
    # If docx not created, fallback to txt
    if not os.path.exists(out_docx):
        out_txt = out_docx.replace('.docx','.txt')
        with open(out_txt, 'w', encoding='utf-8') as f:
            f.write(f"# 文书占位稿\n文书类型: {req.doc_type}\n版本: {req.template_version}\n字段: {json.dumps(req.fields, ensure_ascii=False, indent=2)}\n")
        return {"download": out_txt, "note": "未找到模板，已生成占位 txt。"}
    return {"download": out_docx, "note": "已渲染 DOCX（如需官方模板请覆盖 templates/）。"}

from fastapi.responses import FileResponse

@app.get("/case/{case_id}/assets/list")
async def list_case_assets(case_id: str):
    path = f"/data/cases/{case_id}/assets"
    if not os.path.exists(path):
        return {"assets": []}
    files = []
    for name in sorted(os.listdir(path)):
        files.append({"name": name, "url": f"/case/{case_id}/assets/download/{name}"})
    return {"assets": files}

@app.get("/case/{case_id}/assets/download/{filename}")
async def download_asset(case_id: str, filename: str):
    p = os.path.join("/data/cases", case_id, "assets", filename)
    if not os.path.exists(p):
        return {"error":"not_found"}
    # For safety, only serve from assets dir
    return FileResponse(p, media_type="application/octet-stream", filename=filename)


@app.get("/healthz")
async def healthz():
    return {"ok": True}

from api.tasks.tasks import run_parse, run_index, run_docgen
from celery.result import AsyncResult
from fastapi import HTTPException

@app.post("/tasks/submit")
async def submit_task(task_type: str = Form(...), case_id: str = Form(...), doc_type: str = Form(None), version: str = Form(None)):
    """
    Submit a background task:
    task_type: parse | index | docgen
    """
    if task_type == "parse":
        job = run_parse.delay(case_id)
    elif task_type == "index":
        db_url = os.environ.get("DB_URL", "postgresql://postgres:pass@postgres:5432/legal")
        job = run_index.delay(case_id, db_url)
    elif task_type == "docgen":
        if not doc_type or not version:
            raise HTTPException(status_code=400, detail="doc_type and version required for docgen")
        fields_json = f"/data/cases/{case_id}/fields.json"
        job = run_docgen.delay(case_id, doc_type, version, fields_json)
    else:
        raise HTTPException(status_code=400, detail="unknown task_type")
    return {"task_id": job.id, "status": "submitted"}

@app.get("/tasks/{task_id}")
async def task_status(task_id: str):
    res = AsyncResult(task_id)
    return {"task_id": task_id, "state": res.state, "result": res.result}
