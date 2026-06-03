-- Initialize TML Platform Database

-- Create MLflow database
CREATE DATABASE mlflow;
GRANT ALL PRIVILEGES ON DATABASE mlflow TO tml;

-- Create TML platform tables
CREATE TABLE IF NOT EXISTS models (
    id SERIAL PRIMARY KEY,
    model_id VARCHAR(255) UNIQUE NOT NULL,
    parent_model_id VARCHAR(255),
    model_type VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS model_metrics (
    id SERIAL PRIMARY KEY,
    model_id VARCHAR(255) NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    metric_value FLOAT NOT NULL,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (model_id) REFERENCES models(model_id)
);

CREATE TABLE IF NOT EXISTS transactions (
    id SERIAL PRIMARY KEY,
    transaction_id VARCHAR(255) UNIQUE NOT NULL,
    user_id VARCHAR(255),
    session_id VARCHAR(255),
    model_id VARCHAR(255),
    features JSONB,
    prediction JSONB,
    actual_outcome JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (model_id) REFERENCES models(model_id)
);

CREATE TABLE IF NOT EXISTS model_inheritance (
    id SERIAL PRIMARY KEY,
    child_model_id VARCHAR(255) NOT NULL,
    parent_model_id VARCHAR(255) NOT NULL,
    inheritance_type VARCHAR(50) DEFAULT 'full',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (child_model_id) REFERENCES models(model_id),
    FOREIGN KEY (parent_model_id) REFERENCES models(model_id)
);

-- Create indexes for performance
CREATE INDEX idx_models_model_id ON models(model_id);
CREATE INDEX idx_models_parent_id ON models(parent_model_id);
CREATE INDEX idx_models_created_at ON models(created_at);
CREATE INDEX idx_transactions_model_id ON transactions(model_id);
CREATE INDEX idx_transactions_user_id ON transactions(user_id);
CREATE INDEX idx_transactions_created_at ON transactions(created_at);
CREATE INDEX idx_model_metrics_model_id ON model_metrics(model_id);
CREATE INDEX idx_model_inheritance_child ON model_inheritance(child_model_id);
CREATE INDEX idx_model_inheritance_parent ON model_inheritance(parent_model_id);

-- Insert sample data
INSERT INTO models (model_id, model_type, metadata) VALUES 
('base_model_001', 'logistic_regression', '{"description": "Base model for inheritance"}'),
('demo_model_001', 'logistic_regression', '{"description": "Demo model for testing"}');

-- Create views for analytics
CREATE VIEW model_lineage AS
SELECT 
    m1.model_id as child_model,
    m1.model_type as child_type,
    m1.created_at as child_created,
    m2.model_id as parent_model,
    m2.model_type as parent_type,
    m2.created_at as parent_created,
    mi.inheritance_type
FROM models m1
LEFT JOIN model_inheritance mi ON m1.model_id = mi.child_model_id
LEFT JOIN models m2 ON mi.parent_model_id = m2.model_id;

CREATE VIEW model_performance AS
SELECT 
    m.model_id,
    m.model_type,
    m.created_at,
    COUNT(t.id) as total_transactions,
    AVG(CASE WHEN mm.metric_name = 'accuracy' THEN mm.metric_value END) as avg_accuracy,
    MAX(CASE WHEN mm.metric_name = 'total_updates' THEN mm.metric_value END) as total_updates
FROM models m
LEFT JOIN transactions t ON m.model_id = t.model_id
LEFT JOIN model_metrics mm ON m.model_id = mm.model_id
GROUP BY m.model_id, m.model_type, m.created_at;
