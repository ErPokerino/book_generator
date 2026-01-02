# Stage 1: Build Frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Backend + Static
FROM python:3.11-slim
WORKDIR /app

# Install build dependencies for pycairo and other packages
RUN apt-get update && apt-get install -y \
    build-essential \
    libcairo2-dev \
    libpango1.0-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Copy backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev

# Copy app code
COPY backend/app ./app
COPY config ./config

# Copy frontend build
COPY --from=frontend-builder /frontend/dist ./static

# Create credentials directory (will use Service Account in Cloud Run)
RUN mkdir -p credentials

EXPOSE 8080
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
