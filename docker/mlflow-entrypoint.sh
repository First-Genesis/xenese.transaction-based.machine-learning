#!/bin/bash
set -e

# Install MLflow
pip install mlflow==2.8.1 psycopg2-binary

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to be ready..."
while ! nc -z postgres 5432; do
  sleep 1
done
echo "PostgreSQL is ready!"

# Create MLflow database if it doesn't exist
export PGPASSWORD=tml123
psql -h postgres -U tml -d tml -c "CREATE DATABASE IF NOT EXISTS mlflow;" || true

# Start MLflow server
exec mlflow server \
    --backend-store-uri postgresql://tml:tml123@postgres:5432/mlflow \
    --default-artifact-root /mlflow/artifacts \
    --host 0.0.0.0 \
    --port 5000
