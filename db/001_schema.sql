CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE laws (
  law_id SERIAL PRIMARY KEY,
  title TEXT NOT NULL,
  level TEXT,
  issuer TEXT,
  effective_from DATE,
  effective_to DATE,
  status TEXT
);

CREATE TABLE law_articles (
  id SERIAL PRIMARY KEY,
  law_id INT REFERENCES laws(law_id),
  article_no TEXT,
  paragraph_no TEXT,
  item_no TEXT,
  text TEXT,
  version_id TEXT
);

CREATE TABLE cases (
  case_id TEXT PRIMARY KEY,
  case_no TEXT,
  case_type TEXT,
  parties_json JSONB,
  occurred_at DATE,
  trial_stage TEXT,
  secrecy_level TEXT
);

CREATE TABLE case_assets (
  asset_id SERIAL PRIMARY KEY,
  case_id TEXT REFERENCES cases(case_id),
  type TEXT,
  path TEXT,
  pages INT,
  duration REAL
);

CREATE TABLE chunks (
  chunk_id TEXT PRIMARY KEY,
  source_type TEXT,
  source_id TEXT,
  text TEXT,
  meta JSONB,
  page INT,
  timecode TEXT
);

CREATE TABLE embeddings (
  chunk_id TEXT PRIMARY KEY REFERENCES chunks(chunk_id),
  model TEXT,
  vector vector(1024)
);

CREATE INDEX idx_chunks_text ON chunks USING GIN (to_tsvector('simple', text));
CREATE INDEX idx_chunks_meta ON chunks USING GIN (meta);
