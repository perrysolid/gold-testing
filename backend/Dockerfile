FROM python:3.11-slim

WORKDIR /app

# System deps for OpenCV, WeasyPrint, librosa, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    libgl1 \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
# Install core deps first (layer cache friendly)
RUN pip install --no-cache-dir -e ".[core]"

COPY app ./app
COPY scripts ./scripts

RUN mkdir -p data/artifacts models

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
