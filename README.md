# 本地法律文书生成与知识库RAG系统（可离线）

此仓库为最小可行骨架，包含：
- FastAPI 后端（解析/检索/问答/文书导出接口骨架）
- PostgreSQL + pgvector 模式与建表 SQL
- Docker Compose 部署清单（含 vLLM、Postgres、MinIO）
- Pipelines（解析、建索引、文书生成）
- 示例数据：法条与案件材料
- 模板占位：刑事判决书、审理报告（需替换为你的 .docx 模板）

> 注：为避免环境不一致，此包未内置 .docx 模板文件，请将你单位审定的模板放入 `templates/<文书类型>/<版本>/template.docx`，变量字段见对应 meta.json。

## 快速开始
1. 准备模型权重（例如 Qwen2.5-14B-Instruct）放到 `models/`。
2. `docker compose up -d` 启动（首次需 3-5 分钟拉取镜像）。
3. 打开后端文档：`http://localhost:8000/docs`。
4. 载入示例案件：`scripts/load_sample.sh`。
5. 在 `/qa/ask` 提问，或用 `/doc/generate` 导出文书（返回 docx 占位）。

## 重要
- 生产使用前请接入你方审判系统、替换法条库和模板，并开启 RBAC 与审计。
- 所有路径与端口在 `configs/app.yaml` 与 `docker-compose.yml` 中可改。
