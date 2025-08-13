"""
scripts/detect_missing.py
- Simple heuristic detector that checks parsed chunks for presence of key facts:
  parties, time, location, core facts, and at least one piece of decisive evidence.
- Usage: python scripts/detect_missing.py <case_id>
- Outputs JSON report to /data/cases/<case_id>/parsed/missing_report.json
"""
import sys, os, json, re
key_terms = {
    "parties": ["被告人","原告","被害人","当事人"],
    "time": ["年","月","日","时间","于.*年"],
    "location": ["地点","在.*地","住所","发生地"],
    "core_facts": ["争执","殴打","侵占","盗窃","伤害","纠纷"],
    "evidence": ["证据","书证","物证","视听资料","证人"]
}

def load_chunks(case_id):
    p = f"/data/cases/{case_id}/parsed/chunks.jsonl"
    if not os.path.exists(p):
        return []
    out=[]
    with open(p, "r", encoding="utf-8") as f:
        for l in f:
            try:
                out.append(json.loads(l))
            except:
                pass
    return out

def main(case_id):
    chunks = load_chunks(case_id)
    text_all = " ".join([c.get("text","") for c in chunks])
    report = {}
    for k, terms in key_terms.items():
        found = False
        examples = []
        for t in terms:
            if re.search(t, text_all):
                found = True
                # grab a short context
                idx = text_all.find(t)
                examples.append(text_all[max(0,idx-30):idx+80])
        report[k] = {"found": found, "examples": examples[:3]}
    outp = f"/data/cases/{case_id}/parsed/missing_report.json"
    os.makedirs(os.path.dirname(outp), exist_ok=True)
    with open(outp, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("[ok] wrote", outp)
    return 0

if __name__ == "__main__":
    if len(sys.argv)<2:
        print("Usage: python scripts/detect_missing.py <case_id>")
        sys.exit(1)
    sys.exit(main(sys.argv[1]))
