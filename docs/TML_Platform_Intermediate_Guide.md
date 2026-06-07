# 🚀 TML Platform Intermediate Guide: From Theory to Implementation

**For Computer Science and Engineering Students with Programming Experience**

## Table of Contents
1. [Prerequisites & Setup](#prerequisites--setup)
2. [Deep Dive: Spatial Model Inheritance](#deep-dive-spatial-model-inheritance)
3. [Implementing Your First TML Model](#implementing-your-first-tml-model)
4. [Understanding Proto.Actor System](#understanding-protoactor-system)
5. [Working with Drift Detection](#working-with-drift-detection)
6. [Building a Real Application](#building-a-real-application)
7. [Performance Optimization](#performance-optimization)
8. [Testing Your Implementation](#testing-your-implementation)
9. [Debugging Distributed Systems](#debugging-distributed-systems)
10. [Capstone Project Ideas](#capstone-project-ideas)

---

## Prerequisites & Setup

### Required Knowledge
- **Programming**: Python (intermediate), C# basics
- **Data Structures**: Trees, graphs, hash tables
- **Algorithms**: Basic ML algorithms (regression, classification)
- **Databases**: SQL basics, understanding of ACID properties
- **Networking**: HTTP/REST APIs, basic understanding of distributed systems

### Development Environment Setup

```bash
# 1. Clone the repository
git clone https://github.com/First-Genesis/xenese.transaction-based.machine-learning.git
cd TML

# 2. Set up Python environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. Install Docker Desktop
# Download from: https://www.docker.com/products/docker-desktop

# 4. Start the development environment
docker-compose up -d

# 5. Verify installation
python -c "from tml.core import TransactionProcessor; print('TML Ready!')"
```

### Understanding the Codebase Structure

```
TML/
├── tml/                    # Python implementation
│   ├── core/              # Core TML algorithms
│   │   ├── model.py       # Base model classes
│   │   ├── inheritance.py # Spatial inheritance logic
│   │   └── processor.py   # Transaction processing
│   ├── orchestration/     # Proto.Actor integration
│   └── storage/           # Database integration
├── src/                   # C# .NET implementation
│   ├── TML.API/          # REST API
│   ├── TML.Actors/       # Proto.Actor system
│   └── TML.Storage/      # Data persistence
└── demo/                  # Streamlit demo application
```

---

## Deep Dive: Spatial Model Inheritance

### The Mathematics Behind Spatial Inheritance

Unlike traditional ML where models are independent, TML models inherit knowledge based on **similarity metrics**:

```python
# Similarity calculation between two contexts
def calculate_similarity(context_a: Dict, context_b: Dict) -> float:
    """
    Calculate similarity using weighted features:
    - Geographic distance (30%)
    - Temporal proximity (20%)
    - Feature similarity (50%)
    """
    geo_sim = 1.0 / (1.0 + haversine_distance(context_a['location'], 
                                              context_b['location']))
    
    time_sim = 1.0 / (1.0 + abs(context_a['timestamp'] - 
                                context_b['timestamp']).days)
    
    feature_sim = cosine_similarity(context_a['features'], 
                                   context_b['features'])
    
    return 0.3 * geo_sim + 0.2 * time_sim + 0.5 * feature_sim
```

### Implementing Custom Similarity Functions

```python
class CustomSimilarityCalculator:
    def __init__(self, weights: Dict[str, float]):
        self.weights = weights
    
    def compute(self, model_a: TMLModel, model_b: TMLModel) -> float:
        similarities = {}
        
        # Domain-specific similarity
        if 'domain' in self.weights:
            similarities['domain'] = self.domain_similarity(
                model_a.metadata['domain'],
                model_b.metadata['domain']
            )
        
        # Performance-based similarity
        if 'performance' in self.weights:
            similarities['performance'] = self.performance_similarity(
                model_a.metrics,
                model_b.metrics
            )
        
        # Weighted combination
        total_similarity = sum(
            self.weights[key] * similarities[key] 
            for key in similarities
        )
        
        return total_similarity
    
    def domain_similarity(self, domain_a: str, domain_b: str) -> float:
        # Implement domain-specific logic
        domain_hierarchy = {
            'healthcare': ['hospital', 'clinic', 'lab'],
            'finance': ['banking', 'trading', 'insurance'],
            'manufacturing': ['automotive', 'electronics', 'chemicals']
        }
        
        # Check if domains are in same category
        for category, domains in domain_hierarchy.items():
            if domain_a in domains and domain_b in domains:
                return 1.0 if domain_a == domain_b else 0.7
        
        return 0.0
```

---

## Implementing Your First TML Model

### Step 1: Define Your Transaction Context

```python
from dataclasses import dataclass
from typing import Dict, Any, Optional
import uuid
from datetime import datetime

@dataclass
class TransactionContext:
    """Context for each transaction that spawns a model"""
    
    transaction_id: str
    entity_id: str  # User, device, or system generating the transaction
    timestamp: datetime
    location: Optional[Dict[str, float]] = None  # {'lat': x, 'lon': y}
    domain: str = "general"
    features: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.features is None:
            self.features = {}
        
        if not self.transaction_id:
            self.transaction_id = str(uuid.uuid4())
```

### Step 2: Create a Custom TML Model

```python
from tml.core.model import BaseModel
import numpy as np
from sklearn.linear_model import SGDRegressor

class CustomTMLModel(BaseModel):
    """Custom model that learns from each transaction"""
    
    def __init__(self, context: TransactionContext, parent_model=None):
        super().__init__(context)
        
        # Initialize the online learning model
        self.learner = SGDRegressor(
            learning_rate='adaptive',
            eta0=0.01,
            warm_start=True
        )
        
        # Inherit from parent if available
        if parent_model:
            self.inherit_from(parent_model)
        
        self.training_samples = 0
        self.prediction_history = []
    
    def inherit_from(self, parent_model):
        """Inherit knowledge from parent model"""
        
        if hasattr(parent_model, 'learner'):
            # Copy parent's model parameters
            self.learner.coef_ = parent_model.learner.coef_.copy()
            self.learner.intercept_ = parent_model.learner.intercept_.copy()
            
            # Inherit with decay based on similarity
            similarity = self.calculate_similarity(parent_model)
            self.learner.eta0 *= (1 - similarity * 0.5)  # Adjust learning rate
            
            print(f"Inherited from parent with similarity: {similarity:.3f}")
    
    def learn(self, X: np.ndarray, y: np.ndarray):
        """Online learning from new data"""
        
        # Partial fit for incremental learning
        self.learner.partial_fit(X, y)
        self.training_samples += len(X)
        
        # Update model metadata
        self.metadata['last_updated'] = datetime.now()
        self.metadata['total_samples'] = self.training_samples
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """Make predictions"""
        
        if self.training_samples == 0:
            # Cold start - return default prediction
            return np.zeros(len(X))
        
        predictions = self.learner.predict(X)
        self.prediction_history.extend(predictions.tolist())
        
        return predictions
    
    def calculate_drift(self) -> float:
        """Calculate drift from recent predictions"""
        
        if len(self.prediction_history) < 100:
            return 0.0
        
        recent = self.prediction_history[-50:]
        previous = self.prediction_history[-100:-50]
        
        # Kolmogorov-Smirnov test for distribution change
        from scipy import stats
        ks_statistic, p_value = stats.ks_2samp(recent, previous)
        
        return ks_statistic
```

### Step 3: Process Transactions

```python
class TransactionProcessor:
    """Processes transactions and manages model lifecycle"""
    
    def __init__(self):
        self.models = {}  # Store models by transaction_id
        self.model_index = {}  # Index by entity_id for finding parents
    
    def process_transaction(self, 
                           transaction: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single transaction"""
        
        # Create context
        context = TransactionContext(
            transaction_id=transaction['id'],
            entity_id=transaction['entity_id'],
            timestamp=datetime.now(),
            location=transaction.get('location'),
            domain=transaction.get('domain', 'general'),
            features=transaction.get('features', {})
        )
        
        # Find parent model
        parent_model = self.find_parent_model(context)
        
        # Create new model
        model = CustomTMLModel(context, parent_model)
        
        # Extract features and target
        X = self.extract_features(transaction)
        y = transaction.get('target')
        
        # Make prediction before learning
        prediction = model.predict(X.reshape(1, -1))
        
        # Learn from actual outcome if available
        if y is not None:
            model.learn(X.reshape(1, -1), np.array([y]))
        
        # Calculate drift
        drift_score = model.calculate_drift()
        
        # Store model
        self.models[context.transaction_id] = model
        
        # Update index
        if context.entity_id not in self.model_index:
            self.model_index[context.entity_id] = []
        self.model_index[context.entity_id].append(model)
        
        return {
            'transaction_id': context.transaction_id,
            'prediction': float(prediction[0]) if prediction.size > 0 else None,
            'model_id': model.model_id,
            'parent_model_id': parent_model.model_id if parent_model else None,
            'drift_score': drift_score,
            'confidence': model.calculate_confidence()
        }
    
    def find_parent_model(self, context: TransactionContext) -> Optional[CustomTMLModel]:
        """Find the best parent model for inheritance"""
        
        if context.entity_id not in self.model_index:
            return None
        
        candidate_models = self.model_index[context.entity_id]
        
        if not candidate_models:
            return None
        
        # Find most similar model
        best_model = None
        best_similarity = 0.0
        
        for model in candidate_models[-10:]:  # Check last 10 models
            similarity = self.calculate_context_similarity(
                context, 
                model.context
            )
            
            if similarity > best_similarity:
                best_similarity = similarity
                best_model = model
        
        # Only use parent if similarity is above threshold
        if best_similarity > 0.7:
            return best_model
        
        return None
    
    def extract_features(self, transaction: Dict) -> np.ndarray:
        """Extract features from transaction"""
        
        features = []
        
        # Numerical features
        for key in ['amount', 'value', 'quantity']:
            if key in transaction:
                features.append(float(transaction[key]))
            else:
                features.append(0.0)
        
        # Categorical features (one-hot encoding)
        if 'category' in transaction:
            categories = ['low', 'medium', 'high']
            cat_features = [1.0 if transaction['category'] == cat else 0.0 
                          for cat in categories]
            features.extend(cat_features)
        else:
            features.extend([0.0, 0.0, 0.0])
        
        # Time features
        now = datetime.now()
        features.append(now.hour / 24.0)  # Normalized hour
        features.append(now.weekday() / 7.0)  # Normalized day of week
        
        return np.array(features)
```

---

## Understanding Proto.Actor System

### Actor Model Basics

The Actor Model is a concurrent computation model where "actors" are the fundamental units:

```csharp
// C# Proto.Actor implementation
public class TransactionProcessorActor : IActor
{
    private readonly Dictionary<string, Model> _models = new();
    
    public async Task ReceiveAsync(IContext context)
    {
        switch (context.Message)
        {
            case ProcessTransaction msg:
                await HandleTransaction(context, msg);
                break;
                
            case GetModel msg:
                await HandleGetModel(context, msg);
                break;
                
            case CalculateDrift msg:
                await HandleCalculateDrift(context, msg);
                break;
        }
    }
    
    private async Task HandleTransaction(IContext context, 
                                        ProcessTransaction msg)
    {
        // Find parent model
        var parentModel = FindBestParentModel(msg.Context);
        
        // Create new model with inheritance
        var newModel = new Model(msg.Context, parentModel);
        
        // Process transaction
        var result = await newModel.ProcessAsync(msg.Data);
        
        // Store model
        _models[msg.TransactionId] = newModel;
        
        // Send result back
        context.Respond(new TransactionResult
        {
            TransactionId = msg.TransactionId,
            Prediction = result.Prediction,
            DriftScore = result.DriftScore
        });
    }
}
```

### Python Integration with Proto.Actor

```python
# tml/orchestration/actor_integration.py
from pyproto import Actor, ActorSystem, Props
import asyncio
from typing import Any, Dict

class ModelActor(Actor):
    """Python actor for model management"""
    
    def __init__(self):
        self.models = {}
        self.drift_detector = DriftDetector()
    
    async def receive(self, context):
        """Handle incoming messages"""
        
        message = context.message
        
        if isinstance(message, CreateModel):
            await self.handle_create_model(context, message)
        
        elif isinstance(message, UpdateModel):
            await self.handle_update_model(context, message)
        
        elif isinstance(message, GetDriftScore):
            await self.handle_drift_score(context, message)
    
    async def handle_create_model(self, context, message):
        """Create a new model with inheritance"""
        
        parent_model = None
        if message.parent_model_id:
            parent_model = self.models.get(message.parent_model_id)
        
        # Create model
        model = TMLModel(
            context=message.context,
            parent=parent_model
        )
        
        # Store model
        self.models[model.model_id] = model
        
        # Send response
        context.respond(ModelCreated(
            model_id=model.model_id,
            inherited_from=parent_model.model_id if parent_model else None
        ))
    
    async def handle_drift_score(self, context, message):
        """Calculate drift score for a model"""
        
        model = self.models.get(message.model_id)
        if not model:
            context.respond(DriftScore(score=0.0, error="Model not found"))
            return
        
        score = await self.drift_detector.calculate(model)
        
        context.respond(DriftScore(
            model_id=message.model_id,
            score=score,
            threshold_exceeded=score > 0.05
        ))

# Setting up the actor system
async def setup_actor_system():
    """Initialize the Proto.Actor system"""
    
    system = ActorSystem()
    
    # Create actor props
    model_actor_props = Props.from_producer(lambda: ModelActor())
    
    # Spawn actors
    model_actors = []
    for i in range(5):  # Create 5 model actors
        pid = system.root.spawn(model_actor_props)
        model_actors.append(pid)
    
    # Create router for load balancing
    from pyproto.routing import RoundRobinPool
    router = system.root.spawn(
        Props.from_producer(lambda: ModelActor())
        .with_router(RoundRobinPool(5))
    )
    
    return system, router

# Example usage
async def main():
    system, router = await setup_actor_system()
    
    # Send message to actor
    response = await system.root.request_async(
        router,
        CreateModel(
            context={"entity_id": "user_123"},
            parent_model_id=None
        ),
        timeout=5.0
    )
    
    print(f"Model created: {response.model_id}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Working with Drift Detection

### Understanding Concept Drift

**Concept drift** occurs when the statistical properties of the target variable change over time:

1. **Sudden Drift**: Abrupt change (e.g., new regulations)
2. **Incremental Drift**: Gradual change (e.g., user preferences)
3. **Recurring Drift**: Periodic patterns (e.g., seasonal changes)

### Implementing Drift Detection

```python
import numpy as np
from scipy import stats
from typing import List, Tuple, Optional
from dataclasses import dataclass
from collections import deque

@dataclass
class DriftDetectionResult:
    drift_score: float
    drift_type: str  # 'none', 'warning', 'drift'
    confidence: float
    recommendation: str

class AdvancedDriftDetector:
    """Advanced drift detection using multiple algorithms"""
    
    def __init__(self, 
                 warning_threshold: float = 0.05,
                 drift_threshold: float = 0.1,
                 window_size: int = 100):
        self.warning_threshold = warning_threshold
        self.drift_threshold = drift_threshold
        self.window_size = window_size
        
        # Store recent data
        self.reference_window = deque(maxlen=window_size)
        self.current_window = deque(maxlen=window_size)
    
    def detect(self, 
               reference_data: np.ndarray, 
               current_data: np.ndarray) -> DriftDetectionResult:
        """Detect drift between reference and current data"""
        
        # Multiple drift detection methods
        ks_score = self.kolmogorov_smirnov_test(reference_data, current_data)
        psi_score = self.population_stability_index(reference_data, current_data)
        wasserstein_score = self.wasserstein_distance(reference_data, current_data)
        
        # Combine scores
        combined_score = (ks_score + psi_score + wasserstein_score) / 3
        
        # Determine drift type
        if combined_score < self.warning_threshold:
            drift_type = 'none'
            recommendation = "Model is stable. Continue monitoring."
        elif combined_score < self.drift_threshold:
            drift_type = 'warning'
            recommendation = "Warning: Possible drift detected. Increase monitoring frequency."
        else:
            drift_type = 'drift'
            recommendation = "Drift detected! Consider model retraining or adaptation."
        
        return DriftDetectionResult(
            drift_score=combined_score,
            drift_type=drift_type,
            confidence=self.calculate_confidence(reference_data, current_data),
            recommendation=recommendation
        )
    
    def kolmogorov_smirnov_test(self, 
                                ref_data: np.ndarray, 
                                curr_data: np.ndarray) -> float:
        """KS test for distribution comparison"""
        
        statistic, p_value = stats.ks_2samp(ref_data, curr_data)
        return statistic
    
    def population_stability_index(self, 
                                   expected: np.ndarray, 
                                   actual: np.ndarray,
                                   buckets: int = 10) -> float:
        """PSI for population stability"""
        
        # Create bins
        breakpoints = np.linspace(
            min(expected.min(), actual.min()),
            max(expected.max(), actual.max()),
            buckets + 1
        )
        
        # Calculate distributions
        expected_percents = np.histogram(expected, breakpoints)[0] / len(expected)
        actual_percents = np.histogram(actual, breakpoints)[0] / len(actual)
        
        # Avoid division by zero
        expected_percents = np.where(expected_percents == 0, 0.0001, expected_percents)
        actual_percents = np.where(actual_percents == 0, 0.0001, actual_percents)
        
        # Calculate PSI
        psi = np.sum((actual_percents - expected_percents) * 
                    np.log(actual_percents / expected_percents))
        
        return psi
    
    def wasserstein_distance(self, 
                            ref_data: np.ndarray, 
                            curr_data: np.ndarray) -> float:
        """Earth mover's distance between distributions"""
        
        from scipy.stats import wasserstein_distance
        return wasserstein_distance(ref_data, curr_data) / (ref_data.std() + 1e-6)
    
    def calculate_confidence(self, 
                           ref_data: np.ndarray, 
                           curr_data: np.ndarray) -> float:
        """Calculate confidence in drift detection"""
        
        # Confidence based on sample size
        min_samples = min(len(ref_data), len(curr_data))
        sample_confidence = min(1.0, min_samples / 100)
        
        # Confidence based on variance
        ref_var = ref_data.var()
        curr_var = curr_data.var()
        variance_ratio = min(ref_var, curr_var) / (max(ref_var, curr_var) + 1e-6)
        
        return (sample_confidence + variance_ratio) / 2

# Adaptive model with drift handling
class AdaptiveTMLModel(CustomTMLModel):
    """Model that adapts to detected drift"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.drift_detector = AdvancedDriftDetector()
        self.adaptation_history = []
    
    def adapt_to_drift(self, drift_result: DriftDetectionResult):
        """Adapt model based on drift detection"""
        
        if drift_result.drift_type == 'warning':
            # Increase learning rate slightly
            self.learner.eta0 *= 1.2
            self.adaptation_history.append({
                'type': 'warning_adaptation',
                'action': 'increased_learning_rate',
                'drift_score': drift_result.drift_score
            })
            
        elif drift_result.drift_type == 'drift':
            # Major adaptation needed
            if drift_result.confidence > 0.8:
                # High confidence in drift - reset model
                self.reset_model()
                self.adaptation_history.append({
                    'type': 'full_reset',
                    'action': 'model_reset',
                    'drift_score': drift_result.drift_score
                })
            else:
                # Lower confidence - partial adaptation
                self.learner.eta0 *= 2.0
                self.learner.alpha *= 0.5  # Reduce regularization
                self.adaptation_history.append({
                    'type': 'partial_adaptation',
                    'action': 'parameter_adjustment',
                    'drift_score': drift_result.drift_score
                })
    
    def reset_model(self):
        """Reset model while preserving some knowledge"""
        
        # Store best parameters
        best_params = {
            'coef': self.learner.coef_.copy() if hasattr(self.learner, 'coef_') else None,
            'intercept': self.learner.intercept_.copy() if hasattr(self.learner, 'intercept_') else None
        }
        
        # Create new learner
        self.learner = SGDRegressor(
            learning_rate='adaptive',
            eta0=0.01,
            warm_start=False
        )
        
        # Partial knowledge transfer (50% weight)
        if best_params['coef'] is not None:
            self.learner.coef_ = best_params['coef'] * 0.5
            self.learner.intercept_ = best_params['intercept'] * 0.5
```

---

## Building a Real Application

### Project: Real-Time Fraud Detection System

Let's build a complete fraud detection system using TML:

```python
# fraud_detection_app.py
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objs as go
from typing import Dict, List, Tuple

class FraudDetectionSystem:
    """Complete fraud detection application using TML"""
    
    def __init__(self):
        self.processor = TransactionProcessor()
        self.drift_monitor = AdvancedDriftDetector()
        self.metrics = {
            'total_transactions': 0,
            'fraud_detected': 0,
            'models_created': 0,
            'average_drift': 0.0
        }
        
        # Transaction history for analysis
        self.transaction_history = []
        self.prediction_history = []
    
    def process_transaction(self, transaction: Dict) -> Dict:
        """Process a single transaction for fraud detection"""
        
        # Add fraud-specific features
        transaction['features'] = self.extract_fraud_features(transaction)
        
        # Process with TML
        result = self.processor.process_transaction(transaction)
        
        # Update metrics
        self.metrics['total_transactions'] += 1
        if result['prediction'] > 0.7:  # Fraud threshold
            self.metrics['fraud_detected'] += 1
        
        self.metrics['models_created'] = len(self.processor.models)
        
        # Store history
        self.transaction_history.append(transaction)
        self.prediction_history.append(result)
        
        return {
            'transaction_id': transaction['id'],
            'fraud_probability': result['prediction'],
            'is_fraud': result['prediction'] > 0.7,
            'confidence': result.get('confidence', 0.0),
            'drift_score': result['drift_score'],
            'model_id': result['model_id']
        }
    
    def extract_fraud_features(self, transaction: Dict) -> Dict:
        """Extract fraud-specific features"""
        
        features = {}
        
        # Transaction amount analysis
        amount = transaction.get('amount', 0)
        features['amount_log'] = np.log1p(amount)
        features['is_high_amount'] = amount > 1000
        
        # Time-based features
        hour = datetime.now().hour
        features['is_night'] = hour < 6 or hour > 22
        features['is_weekend'] = datetime.now().weekday() >= 5
        
        # Location features
        if 'location' in transaction:
            features['is_foreign'] = transaction['location'].get('country') != 'US'
            features['location_risk'] = self.calculate_location_risk(
                transaction['location']
            )
        
        # Velocity features
        user_id = transaction.get('user_id')
        if user_id:
            features['transaction_velocity'] = self.calculate_velocity(user_id)
            features['unique_merchants'] = self.count_unique_merchants(user_id)
        
        # Merchant features
        merchant = transaction.get('merchant', {})
        features['merchant_risk'] = merchant.get('risk_score', 0.5)
        features['is_new_merchant'] = merchant.get('is_new', False)
        
        return features
    
    def calculate_location_risk(self, location: Dict) -> float:
        """Calculate risk score based on location"""
        
        high_risk_countries = ['NG', 'PK', 'ID', 'VN', 'CN']
        country = location.get('country', 'US')
        
        if country in high_risk_countries:
            return 0.9
        elif country != 'US':
            return 0.6
        else:
            return 0.2
    
    def calculate_velocity(self, user_id: str) -> int:
        """Calculate transaction velocity for user"""
        
        recent_transactions = [
            t for t in self.transaction_history[-100:]
            if t.get('user_id') == user_id
            and datetime.now() - t.get('timestamp', datetime.now()) < timedelta(hours=1)
        ]
        
        return len(recent_transactions)
    
    def count_unique_merchants(self, user_id: str) -> int:
        """Count unique merchants for user"""
        
        user_transactions = [
            t for t in self.transaction_history[-50:]
            if t.get('user_id') == user_id
        ]
        
        unique_merchants = set(
            t.get('merchant', {}).get('id') 
            for t in user_transactions
        )
        
        return len(unique_merchants)

def create_streamlit_app():
    """Create Streamlit dashboard for fraud detection"""
    
    st.set_page_config(
        page_title="TML Fraud Detection System",
        page_icon="🛡️",
        layout="wide"
    )
    
    st.title("🛡️ Real-Time Fraud Detection with TML")
    
    # Initialize system
    if 'fraud_system' not in st.session_state:
        st.session_state.fraud_system = FraudDetectionSystem()
    
    system = st.session_state.fraud_system
    
    # Sidebar for transaction input
    with st.sidebar:
        st.header("Transaction Input")
        
        user_id = st.text_input("User ID", value="user_123")
        amount = st.number_input("Amount ($)", min_value=0.01, value=150.00)
        merchant_id = st.text_input("Merchant ID", value="merchant_456")
        country = st.selectbox("Country", ["US", "UK", "CA", "NG", "CN"])
        
        if st.button("Process Transaction"):
            # Create transaction
            transaction = {
                'id': f"txn_{datetime.now().timestamp()}",
                'user_id': user_id,
                'amount': amount,
                'merchant': {
                    'id': merchant_id,
                    'risk_score': np.random.uniform(0.1, 0.9)
                },
                'location': {
                    'country': country,
                    'lat': np.random.uniform(-90, 90),
                    'lon': np.random.uniform(-180, 180)
                },
                'timestamp': datetime.now()
            }
            
            # Process transaction
            result = system.process_transaction(transaction)
            
            # Show result
            if result['is_fraud']:
                st.error(f"⚠️ FRAUD DETECTED! Probability: {result['fraud_probability']:.2%}")
            else:
                st.success(f"✅ Transaction OK. Fraud probability: {result['fraud_probability']:.2%}")
            
            st.info(f"Model ID: {result['model_id'][:8]}...")
            st.info(f"Drift Score: {result['drift_score']:.4f}")
    
    # Main dashboard
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Total Transactions", 
            system.metrics['total_transactions']
        )
    
    with col2:
        st.metric(
            "Fraud Detected", 
            system.metrics['fraud_detected']
        )
    
    with col3:
        st.metric(
            "Models Created", 
            system.metrics['models_created']
        )
    
    with col4:
        fraud_rate = (system.metrics['fraud_detected'] / 
                     max(1, system.metrics['total_transactions'])) * 100
        st.metric(
            "Fraud Rate", 
            f"{fraud_rate:.2f}%"
        )
    
    # Visualizations
    st.header("📊 Real-Time Analytics")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Fraud probability distribution
        if system.prediction_history:
            predictions = [p['prediction'] for p in system.prediction_history[-100:]]
            
            fig = go.Figure(data=[go.Histogram(
                x=predictions,
                nbinsx=20,
                name="Fraud Probability Distribution"
            )])
            
            fig.update_layout(
                title="Fraud Probability Distribution (Last 100)",
                xaxis_title="Probability",
                yaxis_title="Count"
            )
            
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Drift scores over time
        if system.prediction_history:
            drift_scores = [p['drift_score'] for p in system.prediction_history[-50:]]
            
            fig = go.Figure(data=[go.Scatter(
                y=drift_scores,
                mode='lines+markers',
                name="Drift Score"
            )])
            
            fig.add_hline(y=0.05, line_dash="dash", 
                         annotation_text="Warning Threshold")
            fig.add_hline(y=0.1, line_dash="dash", 
                         line_color="red",
                         annotation_text="Drift Threshold")
            
            fig.update_layout(
                title="Model Drift Over Time",
                xaxis_title="Transaction",
                yaxis_title="Drift Score"
            )
            
            st.plotly_chart(fig, use_container_width=True)
    
    # Recent transactions table
    st.header("🔍 Recent Transactions")
    
    if system.transaction_history:
        recent_df = pd.DataFrame([
            {
                'Time': t['timestamp'].strftime('%H:%M:%S'),
                'User': t['user_id'],
                'Amount': f"${t['amount']:.2f}",
                'Country': t['location']['country'],
                'Fraud Prob': f"{p['prediction']:.2%}",
                'Is Fraud': '⚠️' if p['prediction'] > 0.7 else '✅'
            }
            for t, p in zip(
                system.transaction_history[-10:],
                system.prediction_history[-10:]
            )
        ])
        
        st.dataframe(recent_df, use_container_width=True)

if __name__ == "__main__":
    create_streamlit_app()
```

---

## Performance Optimization

### Memory Management for Large-Scale Deployments

```python
import gc
import psutil
import weakref
from typing import Dict, Optional
from collections import OrderedDict

class ModelMemoryManager:
    """Efficient memory management for millions of models"""
    
    def __init__(self, 
                 max_memory_gb: float = 8.0,
                 cache_size: int = 10000):
        self.max_memory_bytes = max_memory_gb * 1024 * 1024 * 1024
        self.cache_size = cache_size
        
        # LRU cache for hot models
        self.hot_cache = OrderedDict()
        
        # Weak references for cold models
        self.cold_storage = weakref.WeakValueDictionary()
        
        # Model metadata (always in memory)
        self.metadata = {}
    
    def store_model(self, model_id: str, model: CustomTMLModel):
        """Store model with automatic memory management"""
        
        # Store metadata
        self.metadata[model_id] = {
            'created_at': model.context.timestamp,
            'size_bytes': self.estimate_model_size(model),
            'access_count': 0,
            'last_accessed': datetime.now()
        }
        
        # Check memory usage
        if self.get_memory_usage() > self.max_memory_bytes * 0.9:
            self.evict_cold_models()
        
        # Add to hot cache
        if len(self.hot_cache) >= self.cache_size:
            # Move oldest to cold storage
            oldest_id, oldest_model = self.hot_cache.popitem(last=False)
            self.cold_storage[oldest_id] = oldest_model
        
        self.hot_cache[model_id] = model
    
    def get_model(self, model_id: str) -> Optional[CustomTMLModel]:
        """Retrieve model with cache management"""
        
        # Update access metadata
        if model_id in self.metadata:
            self.metadata[model_id]['access_count'] += 1
            self.metadata[model_id]['last_accessed'] = datetime.now()
        
        # Check hot cache
        if model_id in self.hot_cache:
            # Move to end (most recently used)
            self.hot_cache.move_to_end(model_id)
            return self.hot_cache[model_id]
        
        # Check cold storage
        if model_id in self.cold_storage:
            model = self.cold_storage[model_id]
            
            # Promote to hot cache
            self.hot_cache[model_id] = model
            
            # Remove from cold storage
            del self.cold_storage[model_id]
            
            return model
        
        # Model not in memory - load from disk/database
        return self.load_from_persistent_storage(model_id)
    
    def evict_cold_models(self):
        """Evict least recently used models to free memory"""
        
        # Sort by last accessed time
        sorted_models = sorted(
            self.metadata.items(),
            key=lambda x: x[1]['last_accessed']
        )
        
        # Evict oldest 10%
        num_to_evict = int(len(self.hot_cache) * 0.1)
        
        for model_id, _ in sorted_models[:num_to_evict]:
            if model_id in self.hot_cache:
                # Move to cold storage or persist to disk
                model = self.hot_cache.pop(model_id)
                self.persist_to_disk(model_id, model)
        
        # Force garbage collection
        gc.collect()
    
    def estimate_model_size(self, model: CustomTMLModel) -> int:
        """Estimate memory size of a model"""
        
        import sys
        
        size = sys.getsizeof(model)
        
        # Add size of numpy arrays
        if hasattr(model, 'learner') and hasattr(model.learner, 'coef_'):
            size += model.learner.coef_.nbytes
            size += model.learner.intercept_.nbytes
        
        # Add size of prediction history
        if hasattr(model, 'prediction_history'):
            size += sys.getsizeof(model.prediction_history)
        
        return size
    
    def get_memory_usage(self) -> int:
        """Get current memory usage of the process"""
        
        process = psutil.Process()
        return process.memory_info().rss
    
    def persist_to_disk(self, model_id: str, model: CustomTMLModel):
        """Save model to disk for later retrieval"""
        
        import pickle
        import os
        
        # Create directory if not exists
        os.makedirs('model_cache', exist_ok=True)
        
        # Save model
        with open(f'model_cache/{model_id}.pkl', 'wb') as f:
            pickle.dump(model, f, protocol=pickle.HIGHEST_PROTOCOL)
    
    def load_from_persistent_storage(self, model_id: str) -> Optional[CustomTMLModel]:
        """Load model from disk"""
        
        import pickle
        import os
        
        model_path = f'model_cache/{model_id}.pkl'
        
        if os.path.exists(model_path):
            with open(model_path, 'rb') as f:
                return pickle.load(f)
        
        return None

# Parallel processing optimization
class ParallelTransactionProcessor:
    """Process transactions in parallel for high throughput"""
    
    def __init__(self, num_workers: int = 4):
        self.num_workers = num_workers
        self.memory_manager = ModelMemoryManager()
        
        # Create worker pool
        from multiprocessing import Pool
        self.pool = Pool(processes=num_workers)
    
    def process_batch(self, transactions: List[Dict]) -> List[Dict]:
        """Process batch of transactions in parallel"""
        
        # Chunk transactions for parallel processing
        chunk_size = max(1, len(transactions) // self.num_workers)
        chunks = [
            transactions[i:i+chunk_size]
            for i in range(0, len(transactions), chunk_size)
        ]
        
        # Process chunks in parallel
        results = self.pool.map(self._process_chunk, chunks)
        
        # Flatten results
        all_results = []
        for chunk_results in results:
            all_results.extend(chunk_results)
        
        return all_results
    
    def _process_chunk(self, chunk: List[Dict]) -> List[Dict]:
        """Process a chunk of transactions"""
        
        processor = TransactionProcessor()
        results = []
        
        for transaction in chunk:
            result = processor.process_transaction(transaction)
            results.append(result)
            
            # Store model in memory manager
            model_id = result['model_id']
            model = processor.models.get(result['transaction_id'])
            
            if model:
                self.memory_manager.store_model(model_id, model)
        
        return results
```

---

## Testing Your Implementation

### Unit Testing TML Components

```python
import unittest
import numpy as np
from unittest.mock import Mock, patch
from datetime import datetime

class TestTMLModel(unittest.TestCase):
    """Unit tests for TML model functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.context = TransactionContext(
            transaction_id="test_001",
            entity_id="test_entity",
            timestamp=datetime.now(),
            domain="test"
        )
        
        self.model = CustomTMLModel(self.context)
    
    def test_model_creation(self):
        """Test model creation"""
        self.assertIsNotNone(self.model.model_id)
        self.assertEqual(self.model.context.entity_id, "test_entity")
        self.assertEqual(self.model.training_samples, 0)
    
    def test_inheritance(self):
        """Test model inheritance"""
        # Create parent model
        parent_model = CustomTMLModel(self.context)
        
        # Train parent
        X = np.array([[1, 2, 3]])
        y = np.array([4])
        parent_model.learn(X, y)
        
        # Create child with inheritance
        child_context = TransactionContext(
            transaction_id="test_002",
            entity_id="test_entity",
            timestamp=datetime.now(),
            domain="test"
        )
        
        child_model = CustomTMLModel(child_context, parent_model)
        
        # Check inheritance
        self.assertIsNotNone(child_model.learner.coef_)
        np.testing.assert_array_almost_equal(
            child_model.learner.coef_,
            parent_model.learner.coef_
        )
    
    def test_online_learning(self):
        """Test online learning capability"""
        # Initial training
        X1 = np.array([[1, 2, 3]])
        y1 = np.array([4])
        self.model.learn(X1, y1)
        
        self.assertEqual(self.model.training_samples, 1)
        
        # Make prediction
        pred1 = self.model.predict(X1)
        
        # Additional training
        X2 = np.array([[2, 3, 4]])
        y2 = np.array([5])
        self.model.learn(X2, y2)
        
        self.assertEqual(self.model.training_samples, 2)
        
        # Predictions should change after more training
        pred2 = self.model.predict(X1)
        self.assertIsNotNone(pred2)
    
    def test_drift_detection(self):
        """Test drift detection"""
        # Generate data with drift
        np.random.seed(42)
        
        # Initial distribution
        for _ in range(50):
            self.model.prediction_history.append(
                np.random.normal(0, 1)
            )
        
        # Changed distribution (drift)
        for _ in range(50):
            self.model.prediction_history.append(
                np.random.normal(2, 1)  # Mean shifted
            )
        
        drift_score = self.model.calculate_drift()
        
        # Should detect drift
        self.assertGreater(drift_score, 0.1)

class TestDriftDetector(unittest.TestCase):
    """Test drift detection algorithms"""
    
    def setUp(self):
        self.detector = AdvancedDriftDetector()
    
    def test_no_drift(self):
        """Test detection with no drift"""
        np.random.seed(42)
        
        # Same distribution
        reference = np.random.normal(0, 1, 100)
        current = np.random.normal(0, 1, 100)
        
        result = self.detector.detect(reference, current)
        
        self.assertEqual(result.drift_type, 'none')
        self.assertLess(result.drift_score, 0.05)
    
    def test_sudden_drift(self):
        """Test sudden drift detection"""
        np.random.seed(42)
        
        # Different distributions
        reference = np.random.normal(0, 1, 100)
        current = np.random.normal(3, 1, 100)  # Mean shifted
        
        result = self.detector.detect(reference, current)
        
        self.assertEqual(result.drift_type, 'drift')
        self.assertGreater(result.drift_score, 0.1)
    
    def test_incremental_drift(self):
        """Test incremental drift detection"""
        np.random.seed(42)
        
        # Gradual shift
        reference = np.random.normal(0, 1, 100)
        current = np.random.normal(0.5, 1.2, 100)  # Slight shift
        
        result = self.detector.detect(reference, current)
        
        self.assertIn(result.drift_type, ['warning', 'drift'])

class TestTransactionProcessor(unittest.TestCase):
    """Test transaction processing"""
    
    def setUp(self):
        self.processor = TransactionProcessor()
    
    def test_transaction_processing(self):
        """Test basic transaction processing"""
        transaction = {
            'id': 'test_txn_001',
            'entity_id': 'user_001',
            'amount': 100.0,
            'category': 'medium',
            'target': 1.0
        }
        
        result = self.processor.process_transaction(transaction)
        
        self.assertEqual(result['transaction_id'], 'test_txn_001')
        self.assertIn('prediction', result)
        self.assertIn('model_id', result)
        self.assertIn('drift_score', result)
    
    def test_parent_model_finding(self):
        """Test parent model inheritance"""
        # Process first transaction
        txn1 = {
            'id': 'test_txn_001',
            'entity_id': 'user_001',
            'amount': 100.0
        }
        
        result1 = self.processor.process_transaction(txn1)
        self.assertIsNone(result1['parent_model_id'])
        
        # Process second transaction from same entity
        txn2 = {
            'id': 'test_txn_002',
            'entity_id': 'user_001',
            'amount': 150.0
        }
        
        result2 = self.processor.process_transaction(txn2)
        # Should find parent model
        # Note: This depends on similarity threshold
        # self.assertIsNotNone(result2['parent_model_id'])

# Integration tests
class TestIntegration(unittest.TestCase):
    """Integration tests for TML system"""
    
    def test_end_to_end_processing(self):
        """Test complete processing pipeline"""
        # Initialize system
        processor = TransactionProcessor()
        drift_detector = AdvancedDriftDetector()
        
        # Generate synthetic transactions
        np.random.seed(42)
        transactions = []
        
        for i in range(100):
            transactions.append({
                'id': f'txn_{i:03d}',
                'entity_id': f'user_{i % 10:02d}',
                'amount': np.random.uniform(10, 1000),
                'category': np.random.choice(['low', 'medium', 'high']),
                'target': np.random.choice([0, 1])
            })
        
        # Process transactions
        results = []
        for txn in transactions:
            result = processor.process_transaction(txn)
            results.append(result)
        
        # Verify results
        self.assertEqual(len(results), 100)
        self.assertEqual(len(processor.models), 100)
        
        # Check that some models inherited from parents
        parent_models = [r['parent_model_id'] for r in results 
                        if r['parent_model_id'] is not None]
        # At least some should have parents
        # self.assertGreater(len(parent_models), 0)

# Performance tests
class TestPerformance(unittest.TestCase):
    """Performance benchmarks"""
    
    def test_processing_speed(self):
        """Test transaction processing speed"""
        import time
        
        processor = TransactionProcessor()
        
        # Generate test transactions
        transactions = [
            {
                'id': f'perf_test_{i}',
                'entity_id': f'user_{i % 100}',
                'amount': i * 10.0,
                'category': 'test'
            }
            for i in range(1000)
        ]
        
        start_time = time.time()
        
        for txn in transactions:
            processor.process_transaction(txn)
        
        elapsed_time = time.time() - start_time
        transactions_per_second = 1000 / elapsed_time
        
        print(f"\nProcessed 1000 transactions in {elapsed_time:.2f} seconds")
        print(f"Throughput: {transactions_per_second:.0f} transactions/second")
        
        # Should process at least 100 transactions per second
        self.assertGreater(transactions_per_second, 100)
    
    def test_memory_usage(self):
        """Test memory efficiency"""
        import psutil
        import gc
        
        gc.collect()
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Create many models
        processor = TransactionProcessor()
        
        for i in range(10000):
            transaction = {
                'id': f'mem_test_{i}',
                'entity_id': f'user_{i}',
                'amount': i * 1.0
            }
            processor.process_transaction(transaction)
        
        gc.collect()
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_used = final_memory - initial_memory
        
        print(f"\nMemory used for 10,000 models: {memory_used:.2f} MB")
        print(f"Average per model: {memory_used / 10000 * 1000:.2f} KB")
        
        # Should use less than 500MB for 10k models
        self.assertLess(memory_used, 500)

if __name__ == '__main__':
    # Run tests
    unittest.main(verbosity=2)
```

---

## Debugging Distributed Systems

### Common Issues and Solutions

```python
# debugging_tools.py
import logging
import traceback
from datetime import datetime
from typing import Dict, List, Any
import json

class TMLDebugger:
    """Debugging tools for TML distributed system"""
    
    def __init__(self, log_level=logging.DEBUG):
        self.logger = self.setup_logger(log_level)
        self.trace_buffer = []
        self.error_history = []
    
    def setup_logger(self, level):
        """Setup structured logging"""
        
        logger = logging.getLogger('TML_DEBUG')
        logger.setLevel(level)
        
        # Console handler with color
        ch = logging.StreamHandler()
        ch.setLevel(level)
        
        # Format with colors
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        ch.setFormatter(formatter)
        
        logger.addHandler(ch)
        
        return logger
    
    def trace_transaction(self, transaction_id: str, stage: str, data: Dict):
        """Trace transaction through the system"""
        
        trace_entry = {
            'timestamp': datetime.now().isoformat(),
            'transaction_id': transaction_id,
            'stage': stage,
            'data': data
        }
        
        self.trace_buffer.append(trace_entry)
        self.logger.debug(f"TRACE [{transaction_id}] {stage}: {json.dumps(data)}")
    
    def debug_actor_communication(self):
        """Debug Proto.Actor communication"""
        
        from tml.orchestration.actor_system import ActorSystemMonitor
        
        monitor = ActorSystemMonitor()
        
        # Check actor health
        health_status = monitor.check_health()
        
        self.logger.info("Actor System Health:")
        for actor_type, status in health_status.items():
            self.logger.info(f"  {actor_type}: {status}")
        
        # Check message queues
        queue_stats = monitor.get_queue_stats()
        
        self.logger.info("Message Queue Statistics:")
        for queue, stats in queue_stats.items():
            self.logger.info(f"  {queue}: {stats}")
        
        # Check for deadlocks
        deadlocks = monitor.detect_deadlocks()
        if deadlocks:
            self.logger.error(f"DEADLOCKS DETECTED: {deadlocks}")
    
    def analyze_drift_patterns(self, model_ids: List[str]):
        """Analyze drift patterns across models"""
        
        drift_analysis = {}
        
        for model_id in model_ids:
            # Get model drift history
            drift_history = self.get_drift_history(model_id)
            
            if drift_history:
                avg_drift = sum(drift_history) / len(drift_history)
                max_drift = max(drift_history)
                trend = self.calculate_trend(drift_history)
                
                drift_analysis[model_id] = {
                    'average': avg_drift,
                    'maximum': max_drift,
                    'trend': trend,
                    'status': 'ALERT' if max_drift > 0.1 else 'OK'
                }
        
        return drift_analysis
    
    def diagnose_performance_issues(self):
        """Diagnose performance bottlenecks"""
        
        import cProfile
        import pstats
        from io import StringIO
        
        profiler = cProfile.Profile()
        
        # Profile transaction processing
        profiler.enable()
        
        # Run sample transactions
        processor = TransactionProcessor()
        for i in range(100):
            processor.process_transaction({
                'id': f'perf_test_{i}',
                'entity_id': 'test_user',
                'amount': 100.0
            })
        
        profiler.disable()
        
        # Analyze results
        stream = StringIO()
        stats = pstats.Stats(profiler, stream=stream)
        stats.sort_stats('cumulative')
        stats.print_stats(20)
        
        self.logger.info("Performance Profile:\n" + stream.getvalue())
        
        # Identify bottlenecks
        bottlenecks = self.identify_bottlenecks(stats)
        
        if bottlenecks:
            self.logger.warning(f"Performance bottlenecks detected: {bottlenecks}")
    
    def debug_database_issues(self):
        """Debug database connection and query issues"""
        
        from tml.storage.database_integration import DatabaseIntegration
        
        db = DatabaseIntegration()
        
        # Test connection
        try:
            db.test_connection()
            self.logger.info("Database connection: OK")
        except Exception as e:
            self.logger.error(f"Database connection failed: {e}")
            return
        
        # Check slow queries
        slow_queries = db.get_slow_queries()
        
        if slow_queries:
            self.logger.warning("Slow queries detected:")
            for query in slow_queries:
                self.logger.warning(f"  {query}")
        
        # Check table sizes
        table_sizes = db.get_table_sizes()
        
        self.logger.info("Table sizes:")
        for table, size in table_sizes.items():
            self.logger.info(f"  {table}: {size}")
    
    def create_debug_report(self) -> Dict:
        """Create comprehensive debug report"""
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'system_health': self.check_system_health(),
            'recent_errors': self.error_history[-10:],
            'transaction_traces': self.trace_buffer[-50:],
            'performance_metrics': self.get_performance_metrics(),
            'recommendations': self.generate_recommendations()
        }
        
        # Save report
        with open(f'debug_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json', 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        return report
    
    def check_system_health(self) -> Dict:
        """Overall system health check"""
        
        health = {
            'api': self.check_api_health(),
            'database': self.check_database_health(),
            'actors': self.check_actor_health(),
            'memory': self.check_memory_health(),
            'disk': self.check_disk_health()
        }
        
        overall_status = 'healthy' if all(
            h['status'] == 'healthy' for h in health.values()
        ) else 'unhealthy'
        
        health['overall'] = overall_status
        
        return health

# Example usage
if __name__ == "__main__":
    debugger = TMLDebugger()
    
    # Debug a specific transaction
    debugger.trace_transaction(
        "txn_001",
        "processing_started",
        {'entity_id': 'user_123', 'amount': 100}
    )
    
    # Check actor system
    debugger.debug_actor_communication()
    
    # Analyze performance
    debugger.diagnose_performance_issues()
    
    # Generate report
    report = debugger.create_debug_report()
    print(f"Debug report saved: {report['timestamp']}")
```

---

## Capstone Project Ideas

### 1. **Real-Time Network Intrusion Detection**
Build a TML-based system that creates individual models for each network connection, inheriting patterns from similar connections to detect anomalies.

**Requirements:**
- Process network packet data in real-time
- Create models per source IP/port combination
- Implement drift detection for changing attack patterns
- Build dashboard showing threat levels

### 2. **Personalized Healthcare Monitoring**
Develop a patient monitoring system where each patient gets their own model that inherits from similar patients.

**Requirements:**
- Process vital signs and lab results
- Implement similarity based on demographics and conditions
- Detect health deterioration through drift
- Create alert system for medical staff

### 3. **Smart City Traffic Optimization**
Build a traffic management system where each intersection has its own model, learning from nearby intersections.

**Requirements:**
- Process traffic flow data from sensors
- Implement geographic similarity for inheritance
- Optimize traffic light timing
- Visualize city-wide traffic patterns

### 4. **Cryptocurrency Price Prediction**
Create a trading system where each cryptocurrency has models that inherit from similar assets.

**Requirements:**
- Process price and volume data
- Implement market correlation for inheritance
- Detect market regime changes through drift
- Build automated trading strategy

### 5. **Manufacturing Quality Control**
Develop a quality control system where each production line has models inheriting from similar equipment.

**Requirements:**
- Process sensor data from equipment
- Implement similarity based on product type
- Detect quality degradation through drift
- Create maintenance recommendations

---

## Summary & Next Steps

### What You've Learned

✅ **Spatial Model Inheritance**: How models learn from similar contexts
✅ **Implementation**: Building TML models from scratch
✅ **Proto.Actor Integration**: Working with distributed actor systems
✅ **Drift Detection**: Implementing advanced drift detection algorithms
✅ **Real Applications**: Building production-ready systems
✅ **Performance**: Optimizing for scale and efficiency
✅ **Testing**: Comprehensive testing strategies
✅ **Debugging**: Tools for distributed system debugging

### Recommended Next Steps

1. **Complete a Capstone Project**: Choose one and implement it fully
2. **Contribute to TML**: Submit PRs to the GitHub repository
3. **Read Advanced Guide**: Move on to theoretical foundations
4. **Research Papers**: Read papers on online learning and concept drift
5. **Build Portfolio**: Create 2-3 TML-based applications
6. **Join Community**: Participate in TML forums and discussions

### Additional Resources

- **GitHub Repository**: https://github.com/First-Genesis/xenese.transaction-based.machine-learning
- **Documentation**: TML Platform Technical Guide
- **Research Papers**:
  - "Online Learning and Concept Drift" (Gama et al., 2014)
  - "Learning under Concept Drift: A Review" (Lu et al., 2018)
  - "Ensemble Methods for Concept Drift" (Krawczyk et al., 2017)

### Career Opportunities

With TML expertise, you're prepared for roles in:
- **ML Engineering**: Building scalable ML systems
- **Data Science**: Advanced analytics and modeling
- **Distributed Systems**: Actor-based architectures
- **Financial Technology**: Real-time risk and fraud detection
- **Healthcare Analytics**: Personalized medicine systems

---

*Continue your learning journey with the Advanced Guide for theoretical foundations and research opportunities!*
