"""
scripts/import_laws.py
- Imports JSON law file (see data/laws/sample_laws.json) into Postgres laws and law_articles tables.
Usage:
  python scripts/import_laws.py <DB_URL> <path_to_laws_json>
"""
import sys, json, psycopg2, os

def conn(db_url):
    return psycopg2.connect(db_url)

def main(db_url, path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    con = conn(db_url); cur = con.cursor(); con.autocommit=True
    for law in data:
        cur.execute("INSERT INTO laws(title, level, issuer, effective_from, effective_to, status) VALUES (%s,%s,%s,%s,%s,%s) RETURNING law_id",
                    (law.get("title"), None, None, None, None, "active"))
        law_id = cur.fetchone()[0]
        for art in law.get("articles",[]):
            cur.execute("INSERT INTO law_articles(law_id, article_no, paragraph_no, item_no, text, version_id) VALUES (%s,%s,%s,%s,%s,%s)",
                        (law_id, art.get("article_no"), None, None, art.get("text"), art.get("version_id")))
    cur.close(); con.close()
    print("[ok] imported", len(data))
    return 0

if __name__ == "__main__":
    if len(sys.argv)<3:
        print("Usage: python scripts/import_laws.py <DB_URL> <path_to_laws_json>")
        sys.exit(1)
    sys.exit(main(sys.argv[1], sys.argv[2]))
