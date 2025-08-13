#!/usr/bin/env bash
set -euo pipefail
case_id=${1:-sample_case_001}
DB_URL=${DB_URL:-postgresql://postgres:pass@postgres:5432/legal}
MILVUS_HOST=${MILVUS_HOST:-milvus}
MILVUS_PORT=${MILVUS_PORT:-19530}
CROSS_RE_RANK_URL=${CROSS_RE_RANK_URL:-http://localhost:8100/rerank}
OUTDIR=/data/cases/${case_id}/demo_logs
mkdir -p ${OUTDIR}

echo "[1/5] Parse OCR and prepare chunks"
docker compose exec -T api python /app/../workers/ocr_parse.py ${case_id} | tee ${OUTDIR}/parse.log

echo "[2/5] Index into Postgres (vectors via index_builder)"
docker compose exec -T api python /app/../workers/index_builder.py ${case_id} ${DB_URL} | tee ${OUTDIR}/index_pg.log

echo "[3/5] Index into Milvus"
docker compose exec -T api python /app/../workers/milvus_indexer.py ${case_id} ${MILVUS_HOST} ${MILVUS_PORT} | tee ${OUTDIR}/index_milvus.log

echo "[4/5] Query QA API (Milvus + Cross-Encoder path)"
curl -s -X POST http://localhost:8000/qa/ask -H 'Content-Type: application/json'   -d '{"case_id":"'"${case_id}"'","question":"本案争议焦点为何？"}' | jq . | tee ${OUTDIR}/qa_out.json

echo "[5/5] Done. Logs in ${OUTDIR}"
