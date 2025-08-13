"""
workers/render_docx.py
- Render DOCX from docxtpl with fields JSON, fall back to .txt if template missing.
Usage:
  python workers/render_docx.py <doc_type> <version> <fields_json_path> <out_docx_path>
"""
import os, sys, json
from docxtpl import DocxTemplate

def main(doc_type, version, fields_json, out_path):
    tpl_path = f"/templates/{doc_type}/{version}/template.docx"
    if not os.path.exists(tpl_path):
        # fallback: write txt
        with open(out_path.replace(".docx",".txt"), "w", encoding="utf-8") as f:
            f.write("[占位] 模板未找到: " + tpl_path + "\n" + open(fields_json, "r", encoding="utf-8").read())
        print("[!] template not found, wrote txt placeholder")
        return 0
    ctx = json.load(open(fields_json, "r", encoding="utf-8"))
    doc = DocxTemplate(tpl_path)
    doc.render(ctx)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    doc.save(out_path)
    print("[ok] rendered ->", out_path)
    return 0

if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("Usage: python workers/render_docx.py <doc_type> <version> <fields_json_path> <out_docx_path>")
        sys.exit(1)
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]))
