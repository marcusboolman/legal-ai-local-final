#!/usr/bin/env bash
set -e
echo "[i] 创建示例 MinIO 桶"
mc alias set local http://minio:9000 minio minio123 || true
mc mb -p local/legal-data || true
echo "[i] 载入本地示例数据到 /data，API 会直接访问此路径"
