# User-friendly Docker image for Carbon miners and agentic miners

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# System dependencies
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Carbon
COPY pyproject.toml .
RUN pip install --upgrade pip && pip install -e .

# Copy source code
COPY . .

# Create helpful entrypoint
COPY docker/miner/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "examples/run_agentic_miner.py"]
