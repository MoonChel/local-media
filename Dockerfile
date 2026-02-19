FROM oven/bun:1-debian AS ui-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN bun install
COPY frontend/ ./
RUN bun run build

FROM python:3.12-slim AS app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libboost-system-dev \
    libboost-python-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Install Python dependencies
COPY backend/requirements.txt /app/backend/requirements.txt
RUN uv pip install --system --no-cache -r /app/backend/requirements.txt && \
    uv pip install --system --no-cache libtorrent yt-dlp

COPY backend /app/backend
COPY --from=ui-build /app/frontend/dist /app/frontend/dist

ENV APP_CONFIG=/config/config.yaml
EXPOSE 8080
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8080"]
