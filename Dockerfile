# Use the latest official Python image
FROM python:latest

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    BM_TOKEN="" \
    WEBHOOK="" \
    BM_ORG_ID="" \
    POLL_INTERVAL=60

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

ARG UID=10001
RUN adduser --disabled-password --gecos "" --home "/home/appuser" --shell "/sbin/nologin" --uid "${UID}" appuser

# Copy app code
COPY . .

RUN chown -R appuser /app

USER appuser

CMD ["python3", "main.py"]
