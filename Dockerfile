# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install OS dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/*

# Create and set work directory
WORKDIR /app

# Copy only requirements first (for cache efficiency)
COPY src/marbix/requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/marbix/ ./marbix/

# Expose the port Uvicorn will run on
EXPOSE 80

# Start the application
CMD ["uvicorn", "marbix.main:app", "--host", "0.0.0.0", "--port", "80"]
