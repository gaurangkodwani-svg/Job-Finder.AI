-- AI Job Finder v2.0 - Initial Schema (Cloudflare D1)
-- Replaces PRD's PostgreSQL+pgvector: relational tables + embeddings as JSON vectors.

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT UNIQUE NOT NULL,
  name TEXT,
  plan TEXT NOT NULL DEFAULT 'free',           -- free | premium (PR-4.x)
  exclusions TEXT NOT NULL DEFAULT '[]',       -- FR-3.4: JSON array of excluded tags/domains
  vector_weights TEXT NOT NULL DEFAULT '{}',   -- FR-3.3: learned tag weights from feedback
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS profiles (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id),
  raw_text TEXT,                               -- parsed resume text (FR-1.1)
  hard_skills TEXT NOT NULL DEFAULT '[]',      -- JSON array (FR-1.2)
  soft_skills TEXT NOT NULL DEFAULT '[]',
  experience TEXT NOT NULL DEFAULT '[]',       -- JSON array of {title, company, years}
  target_categories TEXT NOT NULL DEFAULT '[]',
  embedding TEXT,                              -- JSON number[] embedding vector
  parse_ms INTEGER,                            -- FR-1.3: parsing latency (<1500ms target)
  parser TEXT,                                 -- 'groq' | 'heuristic' (fallback)
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS jobs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  company TEXT NOT NULL,
  domain TEXT,
  location TEXT,
  type TEXT NOT NULL DEFAULT 'job',            -- job | internship
  description TEXT NOT NULL,
  required_skills TEXT NOT NULL DEFAULT '[]',  -- hard requirement tech stack (FR-2.1)
  nice_skills TEXT NOT NULL DEFAULT '[]',
  category TEXT,
  salary TEXT,
  embedding TEXT,                              -- JSON number[] embedding vector
  scraped_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS matches (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id),
  job_id INTEGER NOT NULL REFERENCES jobs(id),
  tfidf_score REAL NOT NULL DEFAULT 0,         -- FR-2.1 token overlap score
  cosine_score REAL NOT NULL DEFAULT 0,        -- FR-2.2 semantic similarity
  combined_score REAL NOT NULL DEFAULT 0,      -- weighted index score
  band TEXT NOT NULL DEFAULT 'none',           -- excellent(>=.85) | gap(.75-.90) | low
  why_matched TEXT,                            -- FR-3.1 2-sentence explanation
  skill_gap TEXT,                              -- FR-3.2 advice text
  feedback TEXT,                               -- FR-3.3: 'relevant' | 'irrelevant' | NULL
  emailed INTEGER NOT NULL DEFAULT 0,          -- assembled into digest
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(user_id, job_id)
);

CREATE TABLE IF NOT EXISTS feedback_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id),
  match_id INTEGER NOT NULL,
  job_id INTEGER NOT NULL REFERENCES jobs(id),
  label TEXT NOT NULL,                         -- relevant | irrelevant
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cover_letters (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id),
  job_id INTEGER NOT NULL REFERENCES jobs(id),
  content TEXT NOT NULL,
  generator TEXT NOT NULL DEFAULT 'template',  -- 'groq' | 'template'
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Indexes (relational counterpart to NFR-5.2 HNSW: keep lookups flat)
CREATE INDEX IF NOT EXISTS idx_profiles_user ON profiles(user_id);
CREATE INDEX IF NOT EXISTS idx_matches_user ON matches(user_id, combined_score DESC);
CREATE INDEX IF NOT EXISTS idx_matches_job ON matches(job_id);
CREATE INDEX IF NOT EXISTS idx_jobs_category ON jobs(category);
CREATE INDEX IF NOT EXISTS idx_feedback_user ON feedback_events(user_id);
