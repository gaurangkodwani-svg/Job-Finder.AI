AI Job Finder - Python Version
This is a Python implementation of the AI Job Finder, replacing the Node.js/Hono stack with FastAPI and SQLite. The premium features have been removed.

Features
Hybrid TF-IDF matching engine
SQLite database storage
Simple resume parsing
Job matching with similarity scoring
No premium features (removed as requested)
Requirements
Python 3.8+
pip
Installation
pip install -r requirements.txt
Running the Server
python app.py
The server will start on http://localhost:8000.

API Endpoints
Create User
POST /api/users
{"email": "user@example.com", "name": "John Doe"}
Get User
GET /api/users/{id}
Create Profile
POST /api/users/{id}/profile
{"raw_text": "Resume text here..."}
Get Profile
GET /api/users/{id}/profile
Run Match Engine
POST /api/users/{id}/match
Get Matches
GET /api/users/{id}/matches
