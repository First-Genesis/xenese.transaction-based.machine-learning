# TML SDK - Transaction-based Machine Learning Platform

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI version](https://badge.fury.io/py/tml-sdk.svg)](https://badge.fury.io/py/tml-sdk)

The official Python SDK for the Transaction-based Machine Learning (TML) Platform. Build, deploy, and manage machine learning models with real-time transaction processing, spatial inheritance, and federated learning capabilities.

## 🚀 Quick Start

### Installation

```bash
pip install tml-sdk
```

### Basic Usage

```python
from tml_sdk import TMLClient

# Initialize client
client = TMLClient(
    api_url="http://localhost:8000",
    api_key="your-api-key"
)

# Create and train a model
model = client.models.create(
    name="fraud_detection",
    model_type="river_classifier",
    features=["amount", "merchant", "location"]
)

# Stream transactions for real-time learning
for transaction in client.transactions.stream("live-transactions"):
    prediction = model.predict(transaction.features)
    model.learn(transaction.features, transaction.label)
```

## 🏗️ Features

### Core Capabilities
- **Real-time Model Training**: Stream-based learning with River ML
- **Transaction Processing**: High-throughput transaction streaming
- **Spatial Inheritance**: Learn from similar models across domains
- **Federated Learning**: Distributed training across multiple nodes
- **Drift Detection**: Automatic model performance monitoring
- **MLflow Integration**: Experiment tracking and model registry

### Advanced Features
- **Multi-tenant Architecture**: Isolated environments for different clients
- **Auto-scaling**: Dynamic resource allocation based on load
- **Privacy-preserving**: Differential privacy and secure aggregation
- **Real-time Analytics**: Live dashboards and monitoring
- **Enterprise Security**: OAuth2, API keys, and role-based access

## 📖 Documentation

### API Reference
- [Client API](docs/api/client.md) - Core client and authentication
- [Models API](docs/api/models.md) - Model management and training
- [Transactions API](docs/api/transactions.md) - Transaction streaming
- [Spatial API](docs/api/spatial.md) - Spatial inheritance
- [Federated API](docs/api/federated.md) - Federated learning

### Tutorials
- [Getting Started](docs/tutorials/getting-started.md)
- [Real-time Fraud Detection](docs/tutorials/fraud-detection.md)
- [Spatial Model Inheritance](docs/tutorials/spatial-inheritance.md)
- [Federated Learning Setup](docs/tutorials/federated-learning.md)

### Examples
- [Basic Classification](examples/basic_classification.py)
- [Transaction Streaming](examples/transaction_streaming.py)
- [Federated Training](examples/federated_training.py)
- [Model Deployment](examples/model_deployment.py)

## 🛠️ Development

### Setup Development Environment

```bash
git clone https://github.com/tml-platform/tml-sdk.git
cd tml-sdk
pip install -e ".[dev]"
```

### Running Tests

```bash
pytest tests/
```

### Code Formatting

```bash
black tml_sdk/
flake8 tml_sdk/
```

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Documentation**: [https://docs.tml-platform.com](https://docs.tml-platform.com)
- **Issues**: [GitHub Issues](https://github.com/tml-platform/tml-sdk/issues)
- **Community**: [Discord Server](https://discord.gg/tml-platform)
- **Email**: support@tml-platform.com

## 🏢 Enterprise

For enterprise features, support, and custom integrations, contact us at enterprise@tml-platform.com.
