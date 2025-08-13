# api/tasks/tasks.py
from .celery_app import cel
import os, subprocess, json

@cel.task(bind=True)
def run_parse(self, case_id):
    try:
        cmd = ["python", "/app/../workers/ocr_parse.py", case_id]
        res = subprocess.run(cmd, check=True, capture_output=True, text=True)
        return {"status":"ok", "out": res.stdout}
    except subprocess.CalledProcessError as e:
        return {"status":"error", "err": e.stderr}

@cel.task(bind=True)
def run_index(self, case_id, db_url):
    try:
        cmd = ["python", "/app/../workers/index_builder.py", case_id, db_url]
        res = subprocess.run(cmd, check=True, capture_output=True, text=True)
        return {"status":"ok", "out": res.stdout}
    except subprocess.CalledProcessError as e:
        return {"status":"error", "err": e.stderr}

@cel.task(bind=True)
def run_docgen(self, case_id, doc_type, version, fields_json_path):
    try:
        out_path = f"/data/cases/{case_id}/{doc_type}-{version}.docx"
        cmd = ["python", "/app/../workers/render_docx.py", doc_type, version, fields_json_path, out_path]
        res = subprocess.run(cmd, check=True, capture_output=True, text=True)
        return {"status":"ok", "out": res.stdout, "out_path": out_path}
    except subprocess.CalledProcessError as e:
        return {"status":"error", "err": e.stderr}
