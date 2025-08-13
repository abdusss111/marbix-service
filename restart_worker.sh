#!/bin/bash

echo "Stopping existing workers..."
pkill -f "arq marbix.worker.WorkerSettings" || true
pkill -f "uvicorn marbix.main:app" || true

echo "Clearing Redis..."
redis-cli flushall || echo "Redis not available locally"

echo "Waiting for processes to stop..."
sleep 3

echo "Starting API server..."
uvicorn marbix.main:app --host 0.0.0.0 --port 10000 &

echo "Starting ARQ worker with memory optimization..."
ARQ_LOG_LEVEL=DEBUG arq marbix.worker.WorkerSettings --verbose &

echo "Worker started. Check logs for any errors."
echo "Use 'ps aux | grep arq' to check if worker is running"
echo "Use 'ps aux | grep uvicorn' to check if API is running"
