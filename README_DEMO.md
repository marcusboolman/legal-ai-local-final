# Demo: End-to-end Milvus + Cross-Encoder + LLM pipeline

Prerequisites:
- Docker with NVIDIA container runtime if you want GPU acceleration for cross-encoder.
- Models:
  - Put a cross-encoder model files under `models/cross_encoder` (or set CROSS_ENCODER_MODEL env var).
  - Ensure sentence-transformers can load the model locally (or allow internet in container).
  - Embedding model BAAI/bge-large-zh will be downloaded by sentence-transformers if container has internet, or pre-download to models/ for offline use.
- Ensure `docker-compose.yml` exposes services on ports: 8000 (api), 8100 (cross rerank), 19530 (milvus).

Run demo (from project root):
```bash
# start services
docker compose up -d

# wait for services healthy (Milvus may take a moment)
# then run the end-to-end demo script (it runs parse -> pg index -> milvus index -> qa ask)
bash scripts/run_end_to_end_demo.sh sample_case_001

# check logs in /data/cases/sample_case_001/demo_logs
```
