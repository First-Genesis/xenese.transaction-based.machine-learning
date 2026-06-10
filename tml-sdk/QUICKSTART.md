# TML SDK - Quick Start Guide

## Installation

### Prerequisites
- Python 3.8 or higher
- pip package manager

### Install Dependencies

```bash
cd tml-sdk
pip install -r requirements.txt
```

### Install SDK in Development Mode

```bash
pip install -e .
```

## Quick Start

### 1. Basic Usage

```python
from tml_sdk import TMLClient, create_transaction

# Initialize client
client = TMLClient(
    api_url="http://localhost:8000",
    api_key="your-api-key"
)

# Create a model
model = client.models.create(
    name="my_model",
    model_type="river_classifier",
    algorithm="logistic_regression",
    features=["feature1", "feature2", "feature3"]
)

# Create a transaction
transaction = create_transaction(
    features={"feature1": 1.0, "feature2": 2.0, "feature3": 3.0},
    label=1
)

# Make prediction and learn
prediction = model.predict_one(transaction.features)
model.learn_one(transaction.features, transaction.label)
```

### 2. Run the Fraud Detection Example

```bash
cd tml-sdk
python3 examples/basic_fraud_detection.py
```

This will demonstrate:
- ✅ Model creation and configuration
- ✅ Online learning with streaming data
- ✅ Real-time predictions
- ✅ Model performance tracking
- ✅ Model persistence
- ✅ Real-time transaction processing

### 3. Key Features

#### Model Types Supported
- **River ML Models**: Online learning algorithms
  - `river_classifier`: Classification models
  - `river_regressor`: Regression models
  - `river_anomaly_detector`: Anomaly detection

- **Scikit-learn Models**: Batch learning algorithms
  - `sklearn_classifier`: Classification models
  - `sklearn_regressor`: Regression models

#### Algorithms Available
- **Classification**: logistic_regression, naive_bayes, hoeffding_tree
- **Regression**: linear_regression, hoeffding_tree_regressor
- **Ensemble**: adaptive_random_forest (if available)

#### Transaction Processing
- Real-time transaction streaming
- Batch transaction processing
- Automatic feature validation
- Metadata and prediction tracking

### 4. Configuration

#### Environment Variables
```bash
export TML_API_URL="http://localhost:8000"
export TML_API_KEY="your-api-key"
export TML_KAFKA_BOOTSTRAP_SERVERS="localhost:29092"
export TML_POSTGRES_HOST="localhost"
export TML_POSTGRES_USER="tml"
export TML_POSTGRES_PASSWORD="tml123"
```

#### Configuration File
```yaml
# config.yaml
api_url: "http://localhost:8000"
api_key: "your-api-key"
kafka_bootstrap_servers: "localhost:29092"
postgres_host: "localhost"
postgres_user: "tml"
postgres_password: "tml123"
log_level: "INFO"
```

```python
from tml_sdk import TMLClient, TMLConfig

config = TMLConfig.from_file("config.yaml")
client = TMLClient(config=config)
```

### 5. Advanced Features

#### Spatial Inheritance
```python
# Find similar models
similar_models = client.spatial.find_similar(
    model_id="your-model-id",
    similarity_threshold=0.8
)
```

#### Federated Learning
```python
# Start federated training
federation_round = client.federated.start_round(
    model_id="your-model-id",
    participants=["node1", "node2", "node3"]
)
```

#### Monitoring & Drift Detection
```python
# Monitor model performance
drift_status = client.monitoring.check_drift(
    model_id="your-model-id",
    recent_data=transactions
)
```

## Next Steps

1. **Explore Examples**: Check out more examples in the `examples/` directory
2. **Read Documentation**: Full API documentation in `docs/`
3. **Integration**: Integrate with your existing ML pipeline
4. **Production**: Deploy models using the deployment APIs

## Support

- **Issues**: [GitHub Issues](https://github.com/tml-platform/tml-sdk/issues)
- **Documentation**: [Full Documentation](https://docs.tml-platform.com)
- **Community**: [Discord Server](https://discord.gg/tml-platform)
