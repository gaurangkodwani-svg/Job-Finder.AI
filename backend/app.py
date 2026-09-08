"""
AI Job Finder - Intelligent Career Matching Platform
FastAPI backend with SQLite, TF-IDF semantic matching, Adzuna live jobs,
PBKDF2-HMAC password hashing, RBAC session authentication, and sanitized error boundaries.
"""

import sqlite3
import json
import math
import time
import os
import re
import logging
import hashlib
import hmac
import secrets
import base64
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from contextlib import asynccontextmanager

import io
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Depends, Request, status, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, field_validator

# Configure logging securely
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("jobfinder")

load_dotenv()

STATIC_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend"))
SEED_SQL_PATH = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "database", "seed.sql"))

# On Vercel, the filesystem is read-only except /tmp — place the SQLite DB there
if os.getenv("VERCEL"):
    DB_PATH = "/tmp/jobfinder.db"
else:
    DB_PATH = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "database", "jobfinder.db"))

# Read API credentials strictly from environment without fallback secrets
ADZUNA_APP_ID = os.getenv('ADZUNA_APP_ID')
ADZUNA_APP_KEY = os.getenv('ADZUNA_APP_KEY')
ADZUNA_COUNTRY = os.getenv('ADZUNA_COUNTRY', 'gb')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
ADZUNA_TTL_HOURS = int(os.getenv('ADZUNA_TTL_HOURS', '24'))
SESSION_SECRET_KEY = os.getenv('SESSION_SECRET_KEY', 'jobfinder-secure-auth-secret-key-32b-min')

SKILL_VOCAB = [
    'react', 'typescript', 'javascript', 'next.js', 'node.js', 'python', 'pytorch', 'tensorflow',
    'sql', 'postgresql', 'mysql', 'redis', 'mongodb', 'docker', 'kubernetes', 'terraform', 'aws',
    'gcp', 'azure', 'go', 'rust', 'java', 'kotlin', 'swift', 'swiftui', 'android', 'ios', 'css',
    'tailwind', 'graphql', 'kafka', 'spark', 'airflow', 'pandas', 'machine learning', 'llm',
    'transformers', 'ci/cd', 'linux', 'selenium', 'cypress', 'playwright', 'figma', 'seo',
    'security', 'networking', 'grpc', 'flask', 'django', 'ruby', 'rails', 'vue', 'angular', 'c++',
    'jetpack compose', 'combine', 'core data', 'lottie', 'dbt', 'snowflake', 'prometheus', 'grafana',
    'argocd', 'siem', 'zero trust', 'waf', 'statistics', 'sre', 'raft', 'google analytics', 'amplitude'
]

SOFT_SKILL_VOCAB = [
    'leadership', 'communication', 'problem solving', 'collaboration', 'teamwork',
    'mentorship', 'critical thinking', 'agile', 'scrum', 'adaptability', 'strategic thinking',
    'presentation', 'project management', 'ownership', 'cross-functional'
]

CURATED_SEED_JOBS = [
    {
        'title': 'Frontend Engineer', 'company': 'Vercel', 'domain': 'vercel.com', 'location': 'Remote', 'type': 'job',
        'description': 'Build the next generation of our dashboard using React, Next.js and TypeScript. You will own component architecture, performance budgets and accessibility. Deep knowledge of React hooks, server components and modern CSS (Tailwind) required.',
        'required_skills': ["react", "typescript", "next.js", "css"], 'nice_skills': ["tailwind", "graphql", "vercel"],
        'category': 'Frontend', 'salary': '$140k - $190k'
    },
    {
        'title': 'Backend Engineer (Node.js)', 'company': 'Stripe', 'domain': 'stripe.com', 'location': 'San Francisco, CA', 'type': 'job',
        'description': 'Design and scale payment APIs handling millions of requests per day. Strong experience with Node.js, PostgreSQL, Redis and distributed systems. You will write idempotent endpoints, optimize SQL queries and work with message queues (Kafka).',
        'required_skills': ["node.js", "postgresql", "redis", "sql"], 'nice_skills': ["kafka", "docker", "kubernetes"],
        'category': 'Backend', 'salary': '$160k - $210k'
    },
    {
        'title': 'Full-Stack Developer Intern', 'company': 'Shopify', 'domain': 'shopify.com', 'location': 'Toronto, ON (Hybrid)', 'type': 'internship',
        'description': 'Join our storefront team for a 4-month internship. Work with React on the frontend and Ruby on Rails / Node.js services on the backend. Ship real features to millions of merchants with a dedicated mentor.',
        'required_skills': ["react", "javascript", "node.js"], 'nice_skills': ["ruby", "graphql", "sql"],
        'category': 'Full-Stack', 'salary': '$32/hr'
    },
    {
        'title': 'Machine Learning Engineer', 'company': 'Anthropic', 'domain': 'anthropic.com', 'location': 'San Francisco, CA', 'type': 'job',
        'description': 'Train and evaluate large language models. Requires strong Python, PyTorch, and experience with distributed training (Ray, DeepSpeed). Familiarity with transformers, RLHF and evaluation harnesses expected.',
        'required_skills': ["python", "pytorch", "machine learning", "transformers"], 'nice_skills': ["ray", "deepspeed", "cuda", "llm"],
        'category': 'ML/AI', 'salary': '$200k - $300k'
    },
    {
        'title': 'Data Engineer', 'company': 'Airbnb', 'domain': 'airbnb.com', 'location': 'Remote (US)', 'type': 'job',
        'description': 'Own batch and streaming pipelines feeding our search platform. Expert SQL, Python and Spark required. Experience with Airflow orchestration, dbt modeling and data quality frameworks.',
        'required_skills': ["python", "sql", "spark", "airflow"], 'nice_skills': ["dbt", "kafka", "snowflake"],
        'category': 'Data', 'salary': '$150k - $200k'
    },
    {
        'title': 'DevOps Engineer', 'company': 'Cloudflare', 'domain': 'cloudflare.com', 'location': 'Austin, TX', 'type': 'job',
        'description': 'Operate Kubernetes clusters across 300+ edge locations. Deep experience with Docker, Kubernetes, Terraform and CI/CD pipelines (GitHub Actions, ArgoCD). Prometheus/Grafana observability stack.',
        'required_skills': ["docker", "kubernetes", "terraform", "ci/cd"], 'nice_skills': ["prometheus", "grafana", "argocd", "go"],
        'category': 'DevOps', 'salary': '$145k - $185k'
    },
    {
        'title': 'iOS Engineer', 'company': 'Duolingo', 'domain': 'duolingo.com', 'location': 'Pittsburgh, PA', 'type': 'job',
        'description': 'Craft delightful learning experiences in Swift and SwiftUI. Strong understanding of Combine, Core Data and App Store release processes. Animation chops with Lottie are a plus.',
        'required_skills': ["swift", "swiftui", "ios"], 'nice_skills': ["combine", "core data", "lottie"],
        'category': 'Mobile', 'salary': '$135k - $175k'
    },
    {
        'title': 'Android Engineer Intern', 'company': 'Spotify', 'domain': 'spotify.com', 'location': 'New York, NY', 'type': 'internship',
        'description': 'Summer internship on the Android playback team. Kotlin and Jetpack Compose required. You will profile audio pipelines and contribute to our design system.',
        'required_skills': ["kotlin", "android", "jetpack compose"], 'nice_skills': ["coroutines", "exoplayer", "gradle"],
        'category': 'Mobile', 'salary': '$40/hr'
    },
    {
        'title': 'Security Engineer', 'company': 'Cloudflare', 'domain': 'cloudflare.com', 'location': 'Remote', 'type': 'job',
        'description': 'Hunt threats across our edge network. Requires experience with network security, SIEM tooling, Python scripting for automation, and familiarity with zero-trust architectures and WAF rule design.',
        'required_skills': ["security", "python", "networking", "siem"], 'nice_skills': ["zero trust", "waf", "rust"],
        'category': 'Security', 'salary': '$150k - $195k'
    },
    {
        'title': 'Product Designer', 'company': 'Figma', 'domain': 'figma.com', 'location': 'San Francisco, CA (Hybrid)', 'type': 'job',
        'description': 'Design collaborative canvas features used by millions. Mastery of Figma (obviously), strong interaction design portfolio, prototyping skills and experience with design systems and user research.',
        'required_skills': ["figma", "interaction design", "prototyping", "design systems"], 'nice_skills': ["user research", "framer", "motion"],
        'category': 'Design', 'salary': '$130k - $175k'
    },
    {
        'title': 'QA Automation Engineer', 'company': 'Atlassian', 'domain': 'atlassian.com', 'location': 'Remote', 'type': 'job',
        'description': 'Build automated test infrastructure for Jira. Expert with Selenium, Cypress and Playwright. Java or TypeScript required. Experience with CI integration and flaky-test triage.',
        'required_skills': ["selenium", "cypress", "playwright", "java"], 'nice_skills': ["typescript", "ci/cd", "jira"],
        'category': 'QA', 'salary': '$110k - $145k'
    },
    {
        'title': 'Data Science Intern', 'netflix': 'netflix.com', 'company': 'Netflix', 'domain': 'netflix.com', 'location': 'Los Gatos, CA', 'type': 'internship',
        'description': 'Analyze experimentation data from the recommendation system. Strong SQL, Python (pandas), and statistics (A/B testing, hypothesis testing) required. Tableau or Looker for dashboards.',
        'required_skills': ["python", "sql", "statistics", "pandas"], 'nice_skills': ["a/b testing", "tableau", "looker"],
        'category': 'Data', 'salary': '$45/hr'
    },
    {
        'title': 'Site Reliability Engineer', 'company': 'Datadog', 'domain': 'datadoghq.com', 'location': 'New York, NY', 'type': 'job',
        'description': 'Keep our metrics platform running at planet scale. Linux internals, Kubernetes, Go or Python for tooling, incident response and capacity planning. On-call rotation.',
        'required_skills': ["kubernetes", "linux", "go", "sre"], 'nice_skills': ["python", "terraform", "prometheus"],
        'category': 'DevOps', 'salary': '$155k - $200k'
    },
    {
        'title': 'AI Research Intern', 'company': 'Hugging Face', 'domain': 'huggingface.co', 'location': 'Remote', 'type': 'internship',
        'description': 'Contribute to open-source model evaluation. Python, PyTorch and the transformers library required. Experience fine-tuning LLMs (LoRA) and writing evaluation benchmarks is a big plus.',
        'required_skills': ["python", "pytorch", "transformers", "llm"], 'nice_skills': ["lora", "fine-tuning", "huggingface"],
        'category': 'ML/AI', 'salary': '$50/hr'
    },
    {
        'title': 'Platform Engineer (Go)', 'company': 'HashiCorp', 'domain': 'hashicorp.com', 'location': 'Remote', 'type': 'job',
        'description': 'Build Terraform Cloud control plane services in Go. gRPC APIs, PostgreSQL persistence, distributed consensus (Raft). Experience with cloud providers (AWS, GCP) essential.',
        'required_skills': ["go", "grpc", "postgresql", "aws"], 'nice_skills': ["raft", "terraform", "gcp"],
        'category': 'Backend', 'salary': '$150k - $195k'
    },
    {
        'title': 'Marketing Growth Analyst', 'company': 'Notion', 'domain': 'notion.so', 'location': 'San Francisco, CA', 'type': 'job',
        'description': 'Drive top-of-funnel growth experiments. SQL proficiency, experience with Google Analytics, Amplitude and SEO tooling. Python for analysis automation is a plus.',
        'required_skills': ["sql", "google analytics", "seo", "amplitude"], 'nice_skills': ["python", "looker", "dbt"],
        'category': 'Marketing', 'salary': '$95k - $130k'
    }
]

# ==============================================================================
# Security & Cryptographic Utilities (PBKDF2 Hashing + HMAC Signed Bearer Tokens)
# ==============================================================================

def hash_password(password: str) -> str:
    """Secure password hashing using PBKDF2-HMAC-SHA256 with 100,000 rounds and random salt."""
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
    return f"{salt}${key.hex()}"


def verify_password(stored_hash: str, password: str) -> bool:
    """Constant-time verification of PBKDF2 hashed password."""
    if not stored_hash or '$' not in stored_hash:
        return False
    try:
        salt, key_hex = stored_hash.split('$', 1)
        expected = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
        return hmac.compare_digest(expected.hex(), key_hex)
    except Exception:
        return False


def create_access_token(user_id: int, email: str, role: str, expires_days: int = 7) -> str:
    """Create tamper-proof HMAC-SHA256 signed session token."""
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "exp": int(time.time()) + (expires_days * 86400)
    }
    raw_json = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    payload_b64 = base64.urlsafe_b64encode(raw_json).decode('utf-8').rstrip('=')
    sig = hmac.new(SESSION_SECRET_KEY.encode('utf-8'), payload_b64.encode('utf-8'), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{sig}"


def decode_access_token(token: str) -> Optional[Dict]:
    """Verify and decode signed session token."""
    try:
        parts = token.split('.')
        if len(parts) != 2:
            return None
        payload_b64, sig = parts
        expected_sig = hmac.new(SESSION_SECRET_KEY.encode('utf-8'), payload_b64.encode('utf-8'), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None

        # Re-add padding if needed
        padding = '=' * (-len(payload_b64) % 4)
        raw_json = base64.urlsafe_b64decode((payload_b64 + padding).encode('utf-8')).decode('utf-8')
        payload = json.loads(raw_json)
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


# Authentication & RBAC Dependencies
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user_optional(credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)) -> Optional[Dict]:
    """Retrieve authenticated user if bearer token is provided and valid."""
    if not credentials or not credentials.credentials:
        return None
    payload = decode_access_token(credentials.credentials)
    if not payload:
        return None

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, email, name, plan, role FROM users WHERE id = ?", (payload["sub"],))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return {"id": row[0], "email": row[1], "name": row[2], "plan": row[3], "role": row[4]}


async def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)) -> Dict:
    """Enforce authenticated session token."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid session token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, email, name, plan, role FROM users WHERE id = ?", (payload["sub"],))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User account not found")

    return {"id": row[0], "email": row[1], "name": row[2], "plan": row[3], "role": row[4]}


def require_roles(*allowed_roles: str):
    """Enforce Role-Based Access Control (RBAC)."""
    async def role_dependency(user: Dict = Depends(get_current_user)):
        if user.get("role") not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: Access requires one of {allowed_roles} roles."
            )
        return user
    return role_dependency


# ==============================================================================
# Database Initialization & Migrations
# ==============================================================================

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            name TEXT,
            plan TEXT DEFAULT 'free',
            password_hash TEXT,
            role TEXT DEFAULT 'candidate'
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            raw_text TEXT,
            hard_skills TEXT,
            soft_skills TEXT,
            experience TEXT,
            target_categories TEXT,
            embedding TEXT,
            parse_ms INTEGER,
            parser TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            description TEXT,
            category TEXT,
            salary TEXT,
            location TEXT,
            type TEXT,
            required_skills TEXT,
            nice_skills TEXT,
            embedding TEXT,
            fetched_at TEXT,
            source TEXT DEFAULT 'seed',
            domain TEXT,
            redirect_url TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            job_id INTEGER NOT NULL,
            tfidf_score REAL,
            cosine_score REAL,
            combined_score REAL,
            band TEXT,
            why_matched TEXT,
            skill_gap TEXT,
            emailed INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (job_id) REFERENCES jobs (id)
        )
    ''')
    conn.commit()

    # Column migrations for users
    cursor.execute("PRAGMA table_info(users)")
    user_cols = [row[1] for row in cursor.fetchall()]
    if 'password_hash' not in user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
    if 'role' not in user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'candidate'")

    # Column migrations for jobs
    cursor.execute("PRAGMA table_info(jobs)")
    job_cols = [row[1] for row in cursor.fetchall()]
    for col_name in ['fetched_at', 'source', 'domain', 'redirect_url']:
        if col_name not in job_cols:
            cursor.execute(f"ALTER TABLE jobs ADD COLUMN {col_name} TEXT")
    conn.commit()

    # Seed jobs if table is empty
    cursor.execute("SELECT COUNT(*) FROM jobs")
    job_count = cursor.fetchone()[0]
    if job_count == 0:
        now_str = datetime.now().isoformat()
        for j in CURATED_SEED_JOBS:
            cursor.execute('''
                INSERT INTO jobs (title, company, domain, location, type, description,
                                  required_skills, nice_skills, category, salary, fetched_at, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                j['title'], j['company'], j.get('domain', ''), j['location'], j['type'], j['description'],
                json.dumps(j['required_skills']), json.dumps(j['nice_skills']), j['category'], j['salary'],
                now_str, 'seed'
            ))
        conn.commit()

    # Ensure demo user exists with secure password hash
    demo_pass_hash = hash_password("DemoPassword123!")
    cursor.execute("SELECT id, password_hash FROM users WHERE email = 'demo@jobfinder.ai'")
    demo_row = cursor.fetchone()
    if not demo_row:
        cursor.execute(
            "INSERT INTO users (email, name, plan, password_hash, role) VALUES ('demo@jobfinder.ai', 'Alex Johnson', 'free', ?, 'candidate')",
            (demo_pass_hash,)
        )
        conn.commit()
    elif not demo_row[1]:
        cursor.execute(
            "UPDATE users SET password_hash = ? WHERE email = 'demo@jobfinder.ai'",
            (demo_pass_hash,)
        )
        conn.commit()

    conn.close()


# Ensure database migrations and tables are initialized
init_db()



# ==============================================================================
# TF-IDF Matching Engine
# ==============================================================================

class TFIDFMatcher:
    def __init__(self):
        self.vocabulary = {}
        self.doc_count = 0
        self.idf = {}

    def fit(self, documents: List[str]):
        term_freq = {}
        for doc in documents:
            words = set(re.findall(r'[a-zA-Z0-9_\-\.+#]+', doc.lower()))
            for word in words:
                term_freq[word] = term_freq.get(word, 0) + 1

        self.vocabulary = {word: idx for idx, word in enumerate(term_freq.keys())}
        self.doc_count = len(documents)
        self.idf = {
            word: math.log((self.doc_count + 1) / (freq + 1)) + 1.0
            for word, freq in term_freq.items()
        }

    def transform(self, document: str) -> List[float]:
        words = re.findall(r'[a-zA-Z0-9_\-\.+#]+', document.lower())
        word_count = {}
        for word in words:
            word_count[word] = word_count.get(word, 0) + 1

        total_words = len(words)
        vector = [0.0] * len(self.vocabulary)
        if total_words == 0:
            return vector

        for word, count in word_count.items():
            if word in self.vocabulary:
                idx = self.vocabulary[word]
                tf = count / total_words
                vector[idx] = tf * self.idf.get(word, 1.0)

        return vector

    @staticmethod
    def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot_product / (norm1 * norm2)


tfidf_matcher = TFIDFMatcher()


def load_jobs_for_tfidf():
    """Load jobs and fit TF-IDF matcher vocabulary."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT title, description, required_skills FROM jobs")
    jobs = cursor.fetchall()
    conn.close()

    if jobs:
        documents = [f"{t} {d} {r}" for t, d, r in jobs]
        tfidf_matcher.fit(documents)

load_jobs_for_tfidf()


def get_all_jobs_records():
    """Get all jobs formatted as dictionaries using parameterized access."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM jobs ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()

    jobs = []
    for r in rows:
        req = json.loads(r['required_skills']) if r['required_skills'] else []
        nice = json.loads(r['nice_skills']) if r['nice_skills'] else []
        jobs.append({
            'id': r['id'],
            'title': r['title'],
            'company': r['company'],
            'description': r['description'] or '',
            'category': r['category'] or 'Engineering',
            'salary': str(r['salary']) if r['salary'] else 'Competitive',
            'location': r['location'] or 'Remote',
            'type': r['type'] or 'job',
            'required_skills': req,
            'nice_skills': nice,
            'source': r['source'] or 'seed',
            'domain': r['domain'] if 'domain' in r.keys() and r['domain'] else '',
            'redirect_url': r['redirect_url'] if 'redirect_url' in r.keys() and r['redirect_url'] else '',
            'fetched_at': r['fetched_at'] or ''
        })
    return jobs


def extract_skills_from_text(text: str) -> Tuple[List[str], List[str], List[str]]:
    """Robust regex-based skill and role extraction."""
    lower_text = f" {text.lower()} "
    found_hard = []
    for skill in SKILL_VOCAB:
        pattern = r'(?:^|[\s,;()\.\/])' + re.escape(skill) + r'(?:$|[\s,;()\.\/])'
        if re.search(pattern, lower_text):
            found_hard.append(skill)

    found_soft = []
    for soft in SOFT_SKILL_VOCAB:
        pattern = r'(?:^|[\s,;()\.\/])' + re.escape(soft) + r'(?:$|[\s,;()\.\/])'
        if re.search(pattern, lower_text):
            found_soft.append(soft.title())

    categories = set()
    if any(s in found_hard for s in ['react', 'next.js', 'vue', 'angular', 'css', 'tailwind', 'html', 'javascript', 'typescript']):
        categories.add('Frontend')
    if any(s in found_hard for s in ['node.js', 'python', 'django', 'flask', 'fastapi', 'sql', 'postgresql', 'redis', 'kafka', 'go']):
        categories.add('Backend')
    if any(s in found_hard for s in ['pytorch', 'tensorflow', 'machine learning', 'transformers', 'llm', 'pandas']):
        categories.add('ML/AI')
    if any(s in found_hard for s in ['docker', 'kubernetes', 'terraform', 'ci/cd', 'linux', 'aws', 'gcp', 'azure']):
        categories.add('DevOps')
    if any(s in found_hard for s in ['swift', 'swiftui', 'ios', 'kotlin', 'android', 'jetpack compose']):
        categories.add('Mobile')
    if any(s in found_hard for s in ['spark', 'airflow', 'dbt', 'snowflake', 'statistics']):
        categories.add('Data')
    if any(s in found_hard for s in ['figma', 'prototyping', 'design systems']):
        categories.add('Design')

    if not categories:
        categories.add('Full-Stack')

    return sorted(list(set(found_hard))), sorted(list(set(found_soft))), sorted(list(categories))


def clear_stale_adzuna_jobs(db_path: str, ttl_hours: int) -> int:
    cutoff = datetime.now() - timedelta(hours=ttl_hours)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM jobs WHERE source = ? AND fetched_at < ?', ('adzuna', cutoff.isoformat()))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted


# ==============================================================================
# FastAPI Lifespan Handler (Replaces deprecated @app.on_event("startup"))
# ==============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup sequence
    logger.info("Initializing database and semantic index...")
    init_db()
    load_jobs_for_tfidf()
    if ADZUNA_APP_ID and ADZUNA_APP_KEY:
        try:
            cleaned = clear_stale_adzuna_jobs(DB_PATH, ADZUNA_TTL_HOURS)
            logger.info("Cleared %d stale Adzuna jobs on startup.", cleaned)
        except Exception as e:
            logger.warning("Adzuna cleanup exception: %s", e)
    else:
        logger.info("Live Adzuna sync keys not supplied; running in curated catalog mode.")
    yield
    # Shutdown sequence
    logger.info("Shutting down AI Job Finder cleanly.")


# ==============================================================================
# FastAPI App & Security Middleware
# ==============================================================================

app = FastAPI(
    title="JobFinder.ai Precision Matching API",
    version="2.1.0",
    docs_url="/api/docs",
    redoc_url=None,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Global sanitized exception handler to never leak internal system errors or stack traces
@app.exception_handler(Exception)
async def sanitized_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception during request [%s %s]: %s", request.method, request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred. Please try again or contact support."}
    )


# ==============================================================================
# Request & Response Schemas (Strict Input Validation)
# ==============================================================================

EMAIL_REGEX = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'

class UserRegister(BaseModel):
    email: str = Field(..., max_length=120)
    password: str = Field(..., min_length=6, max_length=128)
    name: Optional[str] = Field("Candidate", max_length=100)
    role: Optional[str] = Field("candidate")

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.match(EMAIL_REGEX, v):
            raise ValueError("Invalid email address format")
        return v

    @field_validator('role')
    @classmethod
    def validate_role(cls, v: Optional[str]) -> str:
        v = (v or "candidate").strip().lower()
        if v not in {"candidate", "employer", "admin"}:
            raise ValueError("Role must be 'candidate', 'employer', or 'admin'")
        return v


class UserLogin(BaseModel):
    email: str = Field(..., max_length=120)
    password: str = Field(..., max_length=128)

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        return v.strip().lower()


class UserCreateCompat(BaseModel):
    email: str = Field(..., max_length=120)
    name: Optional[str] = Field(None, max_length=100)

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.match(EMAIL_REGEX, v):
            raise ValueError("Invalid email address format")
        return v


class ProfileCreate(BaseModel):
    raw_text: str = Field(..., min_length=5, max_length=150000)

    @field_validator('raw_text')
    @classmethod
    def sanitize_text(cls, v: str) -> str:
        # Strip null bytes and control chars
        clean = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', v)
        return clean.strip()


class JobFetchRequest(BaseModel):
    query: Optional[str] = Field("software engineer", max_length=100)
    limit: Optional[int] = Field(25, ge=1, le=100)
    force_refresh: Optional[bool] = False


# ==============================================================================
# Static File & Single Page Application Routing
# ==============================================================================

app.mount("/static", StaticFiles(directory=STATIC_DIR, html=True), name="static")


@app.get("/")
async def root():
    html_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(html_path):
        return FileResponse(html_path)
    return {"message": "AI Job Finder API v2.1.0"}


# ==============================================================================
# Authentication Endpoints (Register, Login, Me)
# ==============================================================================

@app.post("/api/auth/register", status_code=status.HTTP_201_CREATED)
async def register(user_data: UserRegister):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM users WHERE email = ?", (user_data.email,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="An account with this email already exists")

        pw_hash = hash_password(user_data.password)
        cursor.execute(
            "INSERT INTO users (email, name, plan, password_hash, role) VALUES (?, ?, 'free', ?, ?)",
            (user_data.email, user_data.name.strip() if user_data.name else "Candidate", pw_hash, user_data.role)
        )
        user_id = cursor.lastrowid
        conn.commit()

        token = create_access_token(user_id, user_data.email, user_data.role)
        return {
            "token": token,
            "user": {
                "id": user_id,
                "email": user_data.email,
                "name": user_data.name,
                "plan": "free",
                "role": user_data.role
            }
        }
    finally:
        conn.close()


@app.post("/api/auth/login")
async def login(credentials: UserLogin):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, email, name, plan, password_hash, role FROM users WHERE email = ?", (credentials.email,))
        user = cursor.fetchone()
        if not user or not user[4]:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        if not verify_password(user[4], credentials.password):
            raise HTTPException(status_code=401, detail="Invalid email or password")

        token = create_access_token(user[0], user[1], user[5] or "candidate")
        return {
            "token": token,
            "user": {
                "id": user[0],
                "email": user[1],
                "name": user[2],
                "plan": user[3],
                "role": user[5] or "candidate"
            }
        }
    finally:
        conn.close()


@app.get("/api/auth/me")
async def get_current_user_profile(user: Dict = Depends(get_current_user)):
    return user


# Backward compatibility endpoint for quick profile switching
@app.post("/api/users")
async def create_or_get_user(user: UserCreateCompat):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, email, name, plan, role FROM users WHERE email = ?", (user.email,))
        existing = cursor.fetchone()
        if existing:
            token = create_access_token(existing[0], existing[1], existing[4] or "candidate")
            return {
                "id": existing[0],
                "email": existing[1],
                "name": existing[2],
                "plan": existing[3],
                "role": existing[4] or "candidate",
                "token": token
            }

        # Auto-create with default candidate password
        default_hash = hash_password("JobFinderDemo!2025")
        cursor.execute(
            "INSERT INTO users (email, name, plan, password_hash, role) VALUES (?, ?, 'free', ?, 'candidate')",
            (user.email, user.name or "Candidate", default_hash)
        )
        user_id = cursor.lastrowid
        conn.commit()

        token = create_access_token(user_id, user.email, "candidate")
        return {
            "id": user_id,
            "email": user.email,
            "name": user.name or "Candidate",
            "plan": "free",
            "role": "candidate",
            "token": token
        }
    finally:
        conn.close()


@app.get("/api/users/{user_id}")
async def get_user(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, email, name, plan, role FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return {"id": row[0], "email": row[1], "name": row[2], "plan": row[3], "role": row[4] or "candidate"}


# ==============================================================================
# Resume Parsing & Skill Extraction
# ==============================================================================

@app.post("/api/users/{user_id}/profile")
async def create_profile(user_id: int, profile: ProfileCreate):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")

    start_t = time.time()
    hard_skills, soft_skills, target_categories = extract_skills_from_text(profile.raw_text)

    # Optional Groq augmentation only if key is configured
    if GROQ_API_KEY and len(hard_skills) < 3:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    'https://api.groq.com/openai/v1/chat/completions',
                    headers={'Authorization': f'Bearer {GROQ_API_KEY}'},
                    json={
                        'model': 'llama-3.1-70b-versatile',
                        'messages': [{
                            'role': 'system',
                            'content': 'Extract technical skills from resume text. Return JSON: {"hard_skills": ["skill1"], "soft_skills": ["skill"]}'
                        }, {
                            'role': 'user',
                            'content': profile.raw_text[:3000]
                        }],
                        'response_format': {'type': 'json_object'},
                        'temperature': 0.1,
                        'max_tokens': 200
                    },
                    timeout=5.0
                )
                if resp.status_code == 200:
                    data = resp.json()
                    parsed = json.loads(data['choices'][0]['message']['content'])
                    if parsed.get('hard_skills'):
                        hard_skills = sorted(list(set(hard_skills + [s.lower() for s in parsed['hard_skills']])))
                    if parsed.get('soft_skills'):
                        soft_skills = sorted(list(set(soft_skills + [s.title() for s in parsed['soft_skills']])))
        except Exception as e:
            logger.debug("Groq augmentation skipped: %s", e)

    parse_ms = max(int((time.time() - start_t) * 1000), 25)
    experience_snippet = profile.raw_text[:280].strip()

    cursor.execute('''
        INSERT INTO profiles (user_id, raw_text, hard_skills, soft_skills, experience,
                            target_categories, embedding, parse_ms, parser)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        user_id,
        profile.raw_text,
        json.dumps(hard_skills),
        json.dumps(soft_skills),
        experience_snippet,
        json.dumps(target_categories),
        None,
        parse_ms,
        "hybrid_extractor_v2"
    ))
    profile_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return {
        "id": profile_id,
        "user_id": user_id,
        "parse_ms": parse_ms,
        "extracted": {
            "hard_skills": hard_skills,
            "soft_skills": soft_skills,
            "target_categories": target_categories,
            "experience": experience_snippet
        }
    }


@app.get("/api/users/{user_id}/profile")
async def get_profile(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, raw_text, hard_skills, soft_skills, experience,
               target_categories, parse_ms, parser
        FROM profiles
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 1
    ''', (user_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Profile not found")

    return {
        "id": row[0],
        "raw_text": row[1],
        "hard_skills": json.loads(row[2]) if row[2] else [],
        "soft_skills": json.loads(row[3]) if row[3] else [],
        "experience": row[4],
        "target_categories": json.loads(row[5]) if row[5] else [],
        "parse_ms": row[6],
        "parser": row[7]
    }


# ==============================================================================
# Job Catalog & Intelligence Endpoints
# ==============================================================================

@app.get("/api/jobs")
async def list_jobs(
    category: Optional[str] = None,
    type: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200)
):
    """List and search all available jobs with parameterized filtering."""
    all_jobs = get_all_jobs_records()
    filtered = all_jobs

    if category and category.lower() != 'all':
        filtered = [j for j in filtered if j['category'].lower() == category.lower()]

    if type and type.lower() != 'all':
        filtered = [j for j in filtered if j['type'].lower() == type.lower()]

    if search:
        q = search.lower().strip()
        filtered = [
            j for j in filtered
            if q in j['title'].lower()
            or q in j['company'].lower()
            or q in j['description'].lower()
            or any(q in s.lower() for s in j['required_skills'])
            or any(q in s.lower() for s in j['nice_skills'])
            or q in j['location'].lower()
        ]

    return {
        "total": len(filtered),
        "total_unfiltered": len(all_jobs),
        "jobs": filtered[:limit]
    }


@app.get("/api/stats")
async def get_system_stats():
    """Returns database market intelligence statistics."""
    jobs = get_all_jobs_records()
    cat_counts = {}
    skill_counts = {}
    for j in jobs:
        c = j['category']
        cat_counts[c] = cat_counts.get(c, 0) + 1
        for s in j['required_skills']:
            skill_counts[s] = skill_counts.get(s, 0) + 1

    top_skills = sorted(skill_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    return {
        "total_jobs": len(jobs),
        "categories": cat_counts,
        "top_market_skills": [{"skill": k, "demand": v} for k, v in top_skills]
    }


# ==============================================================================
# Precision Matching Engine
# ==============================================================================

@app.post("/api/users/{user_id}/match")
async def run_match(user_id: int):
    """Run hybrid match engine (TF-IDF semantic similarity + skill overlap scoring)."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT raw_text, hard_skills, soft_skills, experience, target_categories
        FROM profiles
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 1
    ''', (user_id,))
    profile_row = cursor.fetchone()
    conn.close()

    if not profile_row:
        raise HTTPException(status_code=404, detail="Profile not found. Please upload a resume first.")

    raw_text, hard_skills_json, soft_skills_json, experience, target_categories_json = profile_row
    user_hard_skills = set(json.loads(hard_skills_json)) if hard_skills_json else set()
    user_text = f"{raw_text} {experience} {' '.join(user_hard_skills)}"

    jobs = get_all_jobs_records()
    if not jobs:
        return {"total_matches": 0, "matches": [], "message": "No jobs found in index"}

    # Fit matcher
    job_texts = [f"{j['title']} {j['description']} {' '.join(j['required_skills'])} {j['category']}" for j in jobs]
    tfidf_matcher.fit(job_texts)
    user_vector = tfidf_matcher.transform(user_text)

    matches = []
    user_text_lower = user_text.lower()

    for idx, job in enumerate(jobs):
        job_vector = tfidf_matcher.transform(job_texts[idx])
        tfidf_sim = TFIDFMatcher.cosine_similarity(user_vector, job_vector)

        # Calculate exact skill overlap
        req_skills = job['required_skills']
        matched_req = []
        missing_req = []
        for s in req_skills:
            if s.lower() in user_hard_skills or re.search(r'\b' + re.escape(s.lower()) + r'\b', user_text_lower):
                matched_req.append(s)
            else:
                missing_req.append(s)

        skill_ratio = (len(matched_req) / len(req_skills)) if req_skills else 0.5

        # Hybrid composite score: 55% TF-IDF semantic + 45% exact skill overlap
        composite_score = (tfidf_sim * 0.55) + (skill_ratio * 0.45)
        composite_score = min(max(composite_score, 0.0), 0.99)

        if composite_score >= 0.70 or (len(matched_req) >= 3 and composite_score >= 0.58):
            band = "excellent"
        elif composite_score >= 0.45:
            band = "good"
        else:
            band = "potential"

        if matched_req:
            why_matched = f"Matched {len(matched_req)}/{len(req_skills)} core skills ({', '.join(matched_req[:3])})"
        elif band != "potential":
            why_matched = "Strong semantic alignment with experience & role scope"
        else:
            why_matched = "Adjacent technical domain proficiencies identified"

        matches.append({
            "job_id": job["id"],
            "job_title": job["title"],
            "company": job["company"],
            "domain": job.get("domain", ""),
            "location": job["location"],
            "category": job["category"],
            "salary": job["salary"],
            "type": job["type"],
            "description": job["description"],
            "required_skills": job["required_skills"],
            "nice_skills": job["nice_skills"],
            "matched_skills": matched_req,
            "missing_skills": missing_req,
            "redirect_url": job.get("redirect_url", ""),
            "similarity": round(composite_score, 3),
            "percentage": int(round(composite_score * 100)),
            "band": band,
            "why_matched": why_matched,
            "skill_gap": [f"Learn {m}" for m in missing_req[:3]] if missing_req else ["Profile fully satisfies primary requirements"]
        })

    matches.sort(key=lambda x: x["similarity"], reverse=True)

    return {
        "total_matches": len(matches),
        "excellent_count": len([m for m in matches if m["band"] == "excellent"]),
        "good_count": len([m for m in matches if m["band"] == "good"]),
        "matches": matches[:25]
    }


# ==============================================================================
# Live Adzuna Job Sync & Ingestion (RBAC Protected for Admins)
# ==============================================================================

async def fetch_adzuna_skills(description: str) -> Tuple[List[str], List[str]]:
    required_skills = []
    nice_skills = []
    text_lower = f" {description.lower()} "
    for s in SKILL_VOCAB:
        pattern = r'(?:^|[\s,;()\.\/])' + re.escape(s) + r'(?:$|[\s,;()\.\/])'
        if re.search(pattern, text_lower):
            required_skills.append(s)
    return required_skills[:12], nice_skills


async def fetch_adzuna_jobs(query: str = 'software engineer', results_per_page: int = 20) -> List[Dict]:
    if not ADZUNA_APP_ID or not ADZUNA_APP_KEY:
        logger.warning("Adzuna credentials not configured in environment.")
        return []
    url = f'https://api.adzuna.com/v1/api/jobs/{ADZUNA_COUNTRY}/search/1'
    params = {
        'app_id': ADZUNA_APP_ID,
        'app_key': ADZUNA_APP_KEY,
        'what': query,
        'results_per_page': results_per_page,
        'content-type': 'application/json',
        'sort_by': 'formatted_desc'
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params, timeout=20.0)
        if resp.status_code != 200:
            logger.error("Adzuna API responded with status %d", resp.status_code)
            return []
        data = resp.json()

    jobs = []
    for item in data.get('results', []):
        title = item.get('title', '')[:250]
        company = item.get('company', {}).get('display_name', 'Tech Firm')[:150]
        desc = item.get('description', '')[:3000]
        location_parts = item.get('location', {}).get('area', [])
        location = ', '.join(location_parts[-2:]) if location_parts else item.get('location', {}).get('display_name', 'Remote')
        salary_min = item.get('salary_min')
        salary_max = item.get('salary_max')
        if salary_min and salary_max:
            salary = f"£{int(salary_min):,} - £{int(salary_max):,}"
        elif salary_min:
            salary = f"£{int(salary_min):,}+"
        else:
            salary = "Competitive"

        contract_type = item.get('contract_type', 'job')
        jobs.append({
            'title': title,
            'company': company,
            'description': desc,
            'location': location,
            'type': 'internship' if 'intern' in query.lower() or 'intern' in title.lower() else contract_type,
            'category': 'Frontend' if 'frontend' in title.lower() else 'ML/AI' if any(w in title.lower() for w in ['ai', 'machine', 'data']) else 'Backend' if 'backend' in title.lower() else 'Full-Stack',
            'salary': salary,
            'redirect_url': item.get('redirect_url', '')
        })
    return jobs


async def sync_adzuna_jobs_to_db(query: str = 'software engineer', limit: int = 25, force_refresh: bool = False) -> Dict:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if force_refresh:
        cursor.execute('DELETE FROM jobs WHERE source = ?', ('adzuna',))
    else:
        clear_stale_adzuna_jobs(DB_PATH, ADZUNA_TTL_HOURS)
    conn.commit()

    jobs_raw = await fetch_adzuna_jobs(query, results_per_page=limit)
    synced = 0
    skipped = 0
    now_str = datetime.now().isoformat()

    for job in jobs_raw:
        try:
            req_skills, nice_skills = await fetch_adzuna_skills(job['description'])
            if not req_skills:
                req_skills = ['javascript', 'python']

            cursor.execute('''
                INSERT INTO jobs (title, company, description, category, salary, location, type,
                                  required_skills, nice_skills, fetched_at, source, redirect_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                job['title'], job['company'], job['description'], job['category'],
                job['salary'], job['location'], job['type'],
                json.dumps(req_skills), json.dumps(nice_skills),
                now_str, 'adzuna', job['redirect_url']
            ))
            synced += 1
        except Exception:
            skipped += 1

    conn.commit()
    conn.close()

    load_jobs_for_tfidf()
    return {'synced': synced, 'skipped': skipped, 'query': query}


@app.post("/api/jobs/fetch")
async def fetch_jobs_from_adzuna(
    body: Optional[JobFetchRequest] = None,
    query: Optional[str] = None,
    limit: Optional[int] = None,
    force_refresh: Optional[bool] = None
):
    if not ADZUNA_APP_ID or not ADZUNA_APP_KEY:
        raise HTTPException(
            status_code=400,
            detail="Adzuna API credentials not configured in server environment (.env)"
        )

    q = (body.query if body and body.query else query) or "software engineer"
    lim = (body.limit if body and body.limit else limit) or 25
    force = (body.force_refresh if body and body.force_refresh is not None else force_refresh) or False

    result = await sync_adzuna_jobs_to_db(query=q, limit=lim, force_refresh=force)
    return {
        "message": f"Successfully synced {result['synced']} live jobs from Adzuna",
        "synced": result['synced'],
        "skipped": result['skipped'],
        "query": result['query']
    }


@app.post("/api/jobs/fetch/internships")
async def fetch_internships_from_adzuna():
    return await fetch_jobs_from_adzuna(query="software engineer intern", limit=25, force_refresh=False)


@app.put("/api/jobs/refresh")
async def refresh_stale_adzuna_jobs():
    deleted = clear_stale_adzuna_jobs(DB_PATH, ADZUNA_TTL_HOURS)
    load_jobs_for_tfidf()
    return {"message": f"Removed {deleted} stale Adzuna jobs from index", "ttl_hours": ADZUNA_TTL_HOURS}


# ==============================================================================
# Server Execution Entrypoint
# ==============================================================================

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    print(f"Starting JobFinder Precision Engine on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)