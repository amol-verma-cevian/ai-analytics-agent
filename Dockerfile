FROM python:3.11-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl && \
    rm -rf /var/lib/apt/lists/*

# Install Node.js for frontend build
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# Copy backend deps and install
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy frontend and build
COPY frontend/package*.json ./frontend/
WORKDIR /app/frontend
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Copy backend source
WORKDIR /app
COPY backend/ ./backend/

# Create data directory for SQLite
RUN mkdir -p /app/backend/data

# Serve built frontend from FastAPI
RUN cp -r /app/frontend/dist /app/backend/static

WORKDIR /app/backend

# Add static file serving to the app
EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
