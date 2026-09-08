# AI Job Finder - Python Version

This is a Python implementation of the AI Job Finder, replacing the Node.js/Hono stack with FastAPI and SQLite. The premium features have been removed.

## Features
- Hybrid TF-IDF matching engine
- SQLite database storage
- Simple resume parsing
- Job matching with similarity scoring
- No premium features (removed as requested)

## Requirements
- Python 3.8+
- pip

## Installation
```bash
pip install -r requirements.txt
```

## Running the Server
```bash
python app.py
```

The server will start on `http://localhost:8000`.

## API Endpoints

### Create User
```bash
POST /api/users
{"email": "user@example.com", "name": "John Doe"}
```

### Get User
```bash
GET /api/users/{id}
```

### Create Profile
```bash
POST /api/users/{id}/profile
{"raw_text": "Resume text here..."}
```

### Get Profile
```bash
GET /api/users/{id}/profile
```

### Run Match Engine
```bash
POST /api/users/{id}/match
```

### Get Matches
```bash
GET /api/users/{id}/matches
```

## Notes
- This version removes Node.js dependencies (Hono, Vite, Wrangler)
- Premium features (plan switching, cover letters) have been removed
- Uses FastAPI instead of Hono
- Uses SQLite directly instead of D1
- TF-IDF matching is implemented in pure Python