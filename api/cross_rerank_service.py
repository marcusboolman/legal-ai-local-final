from fastapi import FastAPI, Body
from pydantic import BaseModel
from typing import List, Dict, Any
import os, json
from sentence_transformers import CrossEncoder

app = FastAPI(title="CrossEncoder Rerank Service")

MODEL_NAME = os.environ.get("CROSS_ENCODER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
_ce = None
def get_model():
    global _ce
    if _ce is None:
        _ce = CrossEncoder(MODEL_NAME)
    return _ce

class RerankReq(BaseModel):
    query: str
    candidates: List[Dict[str, Any]]  # each candidate: {"id": "...", "text": "..."}

@app.post("/rerank")
async def rerank(req: RerankReq):
    model = get_model()
    pairs = [[req.query, c.get("text","")] for c in req.candidates]
    scores = model.predict(pairs, batch_size=16)
    out = []
    for c, s in zip(req.candidates, scores):
        out.append({"id": c.get("id"), "score": float(s), "asset": c.get("meta",{}).get("asset"), "page": c.get("meta",{}).get("page")})
    out_sorted = sorted(out, key=lambda x: x["score"], reverse=True)
    return {"results": out_sorted}
