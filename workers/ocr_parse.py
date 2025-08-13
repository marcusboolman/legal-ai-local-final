"""
workers/ocr_parse.py
- Extract text from PDFs, images, Word docs.
- Use PyMuPDF/pdfplumber for text-based PDFs; PaddleOCR for scanned PDFs/images.
- Output JSONL chunks and a merged TXT to /data/cases/<case_id>/parsed/
"""
import os, sys, json, uuid, pathlib, fitz, pdfplumber
from PIL import Image
from paddleocr import PaddleOCR

def ensure_dir(p):
    os.makedirs(p, exist_ok=True)

def extract_pdf(pdf_path, ocr=None):
    texts = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            t = page.extract_text() or ""
            if t.strip():
                texts.append({"type":"text","page":i,"text":t})
            else:
                # fallback OCR
                if ocr:
                    # rasterize page
                    with fitz.open(pdf_path) as doc:
                        pix = doc.load_page(i-1).get_pixmap(dpi=200)
                        img_path = pdf_path + f".p{i}.png"
                        pix.save(img_path)
                        ocr_res = ocr.ocr(img_path, cls=True)
                        txt = "\n".join([line[1][0] for line in (ocr_res[0] or [])])
                        texts.append({"type":"ocr","page":i,"text":txt})
                        os.remove(img_path)
    return texts

def extract_image(img_path, ocr):
    res = ocr.ocr(img_path, cls=True)
    txt = "\n".join([line[1][0] for line in (res[0] or [])])
    return [{"type":"ocr","page":1,"text":txt}]

def extract_docx(docx_path):
    try:
        from docx import Document
    except Exception:
        return []
    doc = Document(docx_path)
    paras = [p.text for p in doc.paragraphs if p.text.strip()]
    return [{"type":"text","page":i+1,"text":t} for i,t in enumerate(paras)]

def main(case_id):
    assets_dir = f"/data/cases/{case_id}/assets"
    out_dir = f"/data/cases/{case_id}/parsed"
    ensure_dir(out_dir)
    ocr = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
    chunks = []
    for name in os.listdir(assets_dir):
        p = os.path.join(assets_dir, name)
        low = name.lower()
        if low.endswith(".pdf"):
            items = extract_pdf(p, ocr)
        elif low.endswith((".png",".jpg",".jpeg",".bmp",".tiff")):
            items = extract_image(p, ocr)
        elif low.endswith(".docx"):
            items = extract_docx(p)
        elif low.endswith(".txt"):
            with open(p, "r", encoding="utf-8", errors="ignore") as f:
                items = [{"type":"text","page":1,"text":f.read()}]
        else:
            continue
        for it in items:
            chunk_id = str(uuid.uuid4())
            chunks.append({
                "chunk_id": chunk_id,
                "source_type": "case",
                "source_id": name,
                "text": it["text"],
                "meta": {"page": it.get("page"), "asset": name}
            })
    # write jsonl
    jl = os.path.join(out_dir, "chunks.jsonl")
    with open(jl, "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    # write merged txt
    merged = os.path.join(out_dir, "merged.txt")
    with open(merged, "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(f"【{c['meta'].get('asset')} p.{c['meta'].get('page')}】\n{c['text']}\n\n")
    print(f"[ok] parsed {len(chunks)} chunks -> {jl}")
    return 0

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python workers/ocr_parse.py <case_id>")
        sys.exit(1)
    sys.exit(main(sys.argv[1]))
