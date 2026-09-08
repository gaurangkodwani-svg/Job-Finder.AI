# Production Dockerfile for JobFinder.ai
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY database/ ./database/

# Expose port (default 8000, overridable by environment)
ENV PORT=8000
EXPOSE 8000

# Start server using uvicorn
CMD ["sh", "-c", "uvicorn backend.app:app --host 0.0.0.0 --port ${PORT}"]
