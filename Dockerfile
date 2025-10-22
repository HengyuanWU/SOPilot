# Multi-stage build: backend (uvicorn) + frontend (vite build)

# ---------- Frontend build ----------
FROM node:20-alpine AS fe-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---------- Backend runtime ----------
FROM python:3.11-slim AS backend
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl && \
    rm -rf /var/lib/apt/lists/*

# Backend deps
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --upgrade pip
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip config set global.extra-index-url https://pypi.org/simple
RUN pip install --no-cache-dir \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    --extra-index-url https://pypi.org/simple \
    -r /app/backend/requirements.txt

# spaCy models installation (IMPROOVE_GUIDE.md Section 2.1 requirement)
RUN python -m spacy download zh_core_web_sm || echo "zh_core_web_sm download failed, will use blank model"
RUN python -m spacy download en_core_web_sm || echo "en_core_web_sm download failed, will use blank model"

# App code
COPY backend/src /app/backend/src
COPY docs /app/docs

# Frontend static (optional)
COPY --from=fe-build /app/frontend/dist /app/frontend_dist

ENV PYTHONPATH=/app/backend/src
EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.asgi:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "backend/src"]