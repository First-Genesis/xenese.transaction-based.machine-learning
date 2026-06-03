.PHONY: help setup start stop deploy deploy-staging deploy-prod test clean lint format security-check

# Default target
help:
	@echo "🧠 TML Platform - Available Commands:"
	@echo ""
	@echo "📦 Setup & Development:"
	@echo "  setup         - Complete development environment setup"
	@echo "  start         - Start all services (development)"
	@echo "  stop          - Stop all services"
	@echo "  clean         - Clean up temporary files and containers"
	@echo ""
	@echo "🚀 Deployment:"
	@echo "  deploy-staging - Deploy to staging environment"
	@echo "  deploy-prod   - Deploy to production environment"
	@echo ""
	@echo "🧪 Testing & Quality:"
	@echo "  test          - Run complete test suite"
	@echo "  test-unit     - Run unit tests only"
	@echo "  test-integration - Run integration tests only"
	@echo "  lint          - Run code linting"
	@echo "  format        - Format code with black and isort"
	@echo "  security-check - Run security vulnerability scan"
	@echo ""
	@echo "📊 Monitoring:"
	@echo "  monitor       - Open monitoring dashboards"

# Complete setup
setup:
	@echo "🚀 Setting up TML Platform..."
	python3 scripts/setup.py
	@echo "✅ Setup complete! Run 'make start' to begin."

# Quick environment setup
setup-env:
	python -m venv venv
	. venv/bin/activate && pip install --upgrade pip
	. venv/bin/activate && pip install -r requirements.txt
	. venv/bin/activate && pip install -r requirements-dev.txt

# Service management
start:
	@echo "🚀 Starting TML Platform..."
	docker-compose up -d
	@echo "⏳ Waiting for services to be ready..."
	sleep 30
	@echo "✅ TML Platform started successfully!"
	@echo "🌐 Access: http://localhost:8081"

stop:
	@echo "⏹️  Stopping TML Platform..."
	docker-compose down
	@echo "✅ TML Platform stopped"

# Legacy aliases
start-infra: start
stop-infra: stop

# Production deployment
deploy-staging:
	@echo "🚀 Deploying to staging..."
	python3 scripts/deploy.py staging

deploy-prod:
	@echo "🚀 Deploying to production..."
	python3 scripts/deploy.py production

# Legacy deployment
deploy: deploy-staging

# Testing
test:
	. venv/bin/activate && pytest tests/ -v --cov=tml --cov-report=html

test-integration:
	. venv/bin/activate && pytest tests/integration/ -v

test-unit:
	. venv/bin/activate && pytest tests/unit/ -v

# Code quality
lint:
	. venv/bin/activate && flake8 tml/ tests/
	. venv/bin/activate && mypy tml/

format:
	. venv/bin/activate && black tml/ tests/
	. venv/bin/activate && isort tml/ tests/

# Cleanup
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	docker system prune -f

# Development helpers
dev-setup: setup-env start-infra
	@echo "Development environment ready!"

dev-teardown: stop-infra clean
	@echo "Development environment cleaned up!"

# Model operations
train-base-model:
	. venv/bin/activate && python -m tml.learning.train_base_model

benchmark:
	. venv/bin/activate && python -m tml.benchmarks.run_benchmarks

# Security
security-check:
	@echo "🔒 Running security checks..."
	. venv/bin/activate && safety check
	. venv/bin/activate && bandit -r tml/
	@echo "✅ Security check complete"

# Monitoring
monitor:
	@echo "📊 Opening monitoring dashboards..."
	open http://localhost:3000  # Grafana
	open http://localhost:9090  # Prometheus
	open http://localhost:8081  # TML Dashboard
