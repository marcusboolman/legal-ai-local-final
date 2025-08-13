#!/usr/bin/env bash
# End-to-end demo (host shell): parse -> index -> ask (stub) -> generate
set -e
case_id=${1:-sample_case_001}
export DB_URL=${DB_URL:-postgresql://postgres:pass@localhost:5432/legal}
echo "[1/4] 解析 OCR"
docker compose exec -T api python /app/../workers/ocr_parse.py $case_id
echo "[2/4] 建索引"
docker compose exec -T api python /app/../workers/index_builder.py $case_id $DB_URL
echo "[3/4] 问答（调用 /qa/ask）"
curl -s -X POST http://localhost:8000/qa/ask -H 'Content-Type: application/json'   -d '{"case_id":"'"$case_id"'","question":"本案争议焦点为何？"}' | jq .
echo "[4/4] 文书生成（DOCX）"
curl -s -X POST http://localhost:8000/doc/generate -H 'Content-Type: application/json'   -d '{"case_id":"'"$case_id"'","doc_type":"审理报告","template_version":"v2025.08","fields":{"court_name":"示例法院","case_no":"(2025)示01刑初123号","summary":"……","focus_points":["事实是否清楚","证据是否确实充分"],"todo_missing_materials":["补充鉴定意见"]}}' | jq .
