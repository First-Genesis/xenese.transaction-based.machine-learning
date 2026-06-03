// TML Platform UI JavaScript - API Integration Version

// API configuration
const API_BASE_URL = 'http://localhost:8000';
let isConnected = false;

// Initialize UI
document.addEventListener('DOMContentLoaded', async () => {
    await checkConnection();
    await refreshModels();
    setInterval(updateStats, 2000);
    addLog('TML Platform UI initialized with API integration', 'info');
});

// Check API connection
async function checkConnection() {
    try {
        const response = await fetch(`${API_BASE_URL}/health`);
        if (response.ok) {
            const data = await response.json();
            isConnected = true;
            document.getElementById('connectionText').textContent = 'Connected to TML API';
            document.getElementById('connectionStatus').style.color = 'var(--success-color)';
            addLog(`Connected to TML API - ${data.models_active} models active`, 'success');
            return true;
        }
    } catch (error) {
        isConnected = false;
        document.getElementById('connectionText').textContent = 'API Offline - Start API server';
        document.getElementById('connectionStatus').style.color = 'var(--danger-color)';
        addLog('API not available. Start the API server: python ui_api_server.py', 'error');
        return false;
    }
}

// Create new model using API
async function createModel() {
    if (!isConnected) {
        await checkConnection();
        if (!isConnected) {
            addLog('Cannot create model - API is offline', 'error');
            return;
        }
    }
    
    const transactionId = document.getElementById('transactionId').value || `txn_${Date.now()}`;
    const userId = document.getElementById('userId').value || 'anonymous';
    const parentModelId = document.getElementById('parentModel').value || null;
    const modelType = document.getElementById('modelType').value;
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/models/create`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                transaction_id: transactionId,
                user_id: userId,
                parent_model_id: parentModelId,
                model_type: modelType,
                session_id: `session_${Date.now()}`
            })
        });
        
        if (response.ok) {
            const model = await response.json();
            addLog(`Created ${parentModelId ? 'child' : 'base'} model ${model.id} for transaction ${transactionId}`, 'success');
            await refreshModels();
            await updateStats();
        } else {
            const error = await response.json();
            addLog(`Failed to create model: ${error.detail}`, 'error');
        }
    } catch (error) {
        addLog(`Error creating model: ${error.message}`, 'error');
    }
}

// Train selected model using API
async function trainModel() {
    if (!isConnected) {
        await checkConnection();
        if (!isConnected) {
            addLog('Cannot train model - API is offline', 'error');
            return;
        }
    }
    
    const modelId = document.getElementById('modelToTrain').value;
    if (!modelId) {
        addLog('Please select a model to train', 'warning');
        return;
    }
    
    const features = {
        amount: parseFloat(document.getElementById('trainAmount').value),
        category: document.getElementById('trainCategory').value,
        hour: parseInt(document.getElementById('trainHour').value)
    };
    
    const target = document.getElementById('trainTarget').value === 'true';
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/models/train`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                model_id: modelId,
                features: features,
                target: target
            })
        });
        
        if (response.ok) {
            const result = await response.json();
            addLog(`Trained model ${modelId} - Updates: ${result.updates}, Accuracy: ${(result.accuracy * 100).toFixed(1)}%`, 'success');
            await refreshModels();
            await updateStats();
        } else {
            const error = await response.json();
            addLog(`Failed to train model: ${error.detail}`, 'error');
        }
    } catch (error) {
        addLog(`Error training model: ${error.message}`, 'error');
    }
}

// Make predictions with all models using API
async function predictAllModels() {
    if (!isConnected) {
        await checkConnection();
        if (!isConnected) {
            addLog('Cannot make predictions - API is offline', 'error');
            return;
        }
    }
    
    const features = {
        amount: parseFloat(document.getElementById('predictAmount').value),
        category: document.getElementById('predictCategory').value,
        hour: parseInt(document.getElementById('predictHour').value)
    };
    
    const resultsDiv = document.getElementById('predictionResults');
    resultsDiv.innerHTML = '<h3>Prediction Results</h3>';
    
    try {
        // Get all models first
        const modelsResponse = await fetch(`${API_BASE_URL}/api/models`);
        const models = await modelsResponse.json();
        
        if (models.length === 0) {
            resultsDiv.innerHTML += '<p style="color: var(--text-secondary);">No models available. Create a model first!</p>';
            return;
        }
        
        // Make predictions
        const response = await fetch(`${API_BASE_URL}/api/predict`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                features: features
            })
        });
        
        if (response.ok) {
            const predictions = await response.json();
            
            // Display results
            predictions.forEach(pred => {
                const model = models.find(m => m.id === pred.model_id);
                const resultCard = document.createElement('div');
                resultCard.className = 'prediction-card';
                resultCard.innerHTML = `
                    <div>
                        <span class="prediction-model">${pred.model_id}</span>
                        <span style="color: var(--text-secondary); font-size: 0.875rem; margin-left: 1rem;">
                            Updates: ${model ? model.updates : 0} | Accuracy: ${model ? (model.accuracy * 100).toFixed(1) : 0}%
                        </span>
                    </div>
                    <span class="prediction-value ${pred.prediction}">${pred.prediction ? 'TRUE' : 'FALSE'}</span>
                `;
                resultsDiv.appendChild(resultCard);
            });
            
            addLog(`Made predictions for features: ${JSON.stringify(features)}`, 'info');
            await updateStats();
        } else {
            const error = await response.json();
            addLog(`Failed to make predictions: ${error.detail}`, 'error');
        }
    } catch (error) {
        addLog(`Error making predictions: ${error.message}`, 'error');
    }
}

// Refresh models from API
async function refreshModels() {
    if (!isConnected) return;
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/models`);
        if (response.ok) {
            const models = await response.json();
            
            // Update parent model selector
            const parentSelect = document.getElementById('parentModel');
            const currentParent = parentSelect.value;
            parentSelect.innerHTML = '<option value="">None (Base Model)</option>';
            
            models.forEach(model => {
                const option = document.createElement('option');
                option.value = model.id;
                option.textContent = `${model.id} (${model.updates} updates)`;
                parentSelect.appendChild(option);
            });
            
            if (currentParent) {
                parentSelect.value = currentParent;
            }
            
            // Update model to train selector
            const trainSelect = document.getElementById('modelToTrain');
            const currentTrain = trainSelect.value;
            trainSelect.innerHTML = '<option value="">Select a model...</option>';
            
            models.forEach(model => {
                const option = document.createElement('option');
                option.value = model.id;
                option.textContent = `${model.id} (${model.updates} updates)`;
                trainSelect.appendChild(option);
            });
            
            if (currentTrain) {
                trainSelect.value = currentTrain;
            }
            
            // Update visualizations
            visualizeModelChain(models);
            updateModelComparison(models);
        }
    } catch (error) {
        console.error('Error refreshing models:', error);
    }
}

// Visualize model inheritance chain
function visualizeModelChain(models) {
    const chainDiv = document.getElementById('modelChain');
    
    if (!models || models.length === 0) {
        chainDiv.innerHTML = `
            <div class="chain-placeholder">
                <i class="fas fa-link"></i>
                <p>No models created yet. Create your first model to start the chain!</p>
            </div>
        `;
        return;
    }
    
    chainDiv.innerHTML = '';
    
    // Build inheritance tree
    const rootModels = models.filter(m => !m.parent_id);
    
    rootModels.forEach(root => {
        const chainElement = document.createElement('div');
        chainElement.style.marginBottom = '1rem';
        
        // Add root model
        let html = `<div class="model-node base">
            <div class="model-node-id">${root.id}</div>
            <div class="model-node-stats">Base Model<br>Updates: ${root.updates}</div>
        </div>`;
        
        // Add children recursively
        const children = models.filter(m => m.parent_id === root.id);
        children.forEach(child => {
            html += `<span class="model-arrow">→</span>`;
            html += `<div class="model-node">
                <div class="model-node-id">${child.id}</div>
                <div class="model-node-stats">Updates: ${child.updates}<br>Acc: ${(child.accuracy * 100).toFixed(1)}%</div>
            </div>`;
        });
        
        chainElement.innerHTML = html;
        chainDiv.appendChild(chainElement);
    });
}

// Update model comparison
function updateModelComparison(models) {
    const comparisonDiv = document.getElementById('modelComparison');
    
    if (!models || models.length === 0) {
        comparisonDiv.innerHTML = `
            <div class="comparison-placeholder">
                <i class="fas fa-chart-line"></i>
                <p>Create and train models to see comparison</p>
            </div>
        `;
        return;
    }
    
    comparisonDiv.innerHTML = '';
    
    models.forEach(model => {
        const card = document.createElement('div');
        card.className = 'comparison-card';
        card.innerHTML = `
            <h3>${model.id}</h3>
            <div class="comparison-metric">
                <span class="metric-label">Parent</span>
                <span class="metric-value">${model.parent_id || 'None'}</span>
            </div>
            <div class="comparison-metric">
                <span class="metric-label">Updates</span>
                <span class="metric-value">${model.updates}</span>
            </div>
            <div class="comparison-metric">
                <span class="metric-label">Accuracy</span>
                <span class="metric-value">${(model.accuracy * 100).toFixed(1)}%</span>
            </div>
            <div class="comparison-metric">
                <span class="metric-label">Predictions</span>
                <span class="metric-value">${model.predictions}</span>
            </div>
        `;
        comparisonDiv.appendChild(card);
    });
}

// Update stats
async function updateStats() {
    if (!isConnected) return;
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/stats`);
        if (response.ok) {
            const stats = await response.json();
            document.getElementById('activeModels').textContent = stats.total_models;
            document.getElementById('predictionsPerSec').textContent = (stats.total_predictions / 10).toFixed(1); // Approximate
            document.getElementById('avgAccuracy').textContent = `${(stats.average_accuracy * 100).toFixed(1)}%`;
        }
    } catch (error) {
        console.error('Error updating stats:', error);
    }
}

// Run full demo using API
async function runFullDemo() {
    if (!isConnected) {
        await checkConnection();
        if (!isConnected) {
            addLog('Cannot run demo - API is offline', 'error');
            return;
        }
    }
    
    const output = document.getElementById('demoOutput');
    output.innerHTML = '';
    
    const log = (message) => {
        output.innerHTML += message + '\n';
        output.scrollTop = output.scrollHeight;
    };
    
    log('🚀 Starting TML Platform Demonstration with Real Models');
    log('='.repeat(50));
    
    try {
        // Create demo chain
        log('\n📝 Creating demonstration model chain...');
        const response = await fetch(`${API_BASE_URL}/api/demo/create_chain`, {
            method: 'POST'
        });
        
        if (response.ok) {
            const result = await response.json();
            log(`✅ ${result.message}`);
            
            // Make test prediction
            log('\n🔮 Making predictions with all models...');
            const testCase = {amount: 175, category: 'electronics', hour: 14};
            log(`Test case: ${JSON.stringify(testCase)}`);
            
            const predResponse = await fetch(`${API_BASE_URL}/api/predict`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    features: testCase
                })
            });
            
            if (predResponse.ok) {
                const predictions = await predResponse.json();
                predictions.forEach(pred => {
                    log(`  ${pred.model_id}: ${pred.prediction ? 'TRUE' : 'FALSE'}`);
                });
            }
            
            log('\n' + '='.repeat(50));
            log('✅ DEMONSTRATION COMPLETE!');
            log('Real TML models created and tested successfully!');
            
            await refreshModels();
            await updateStats();
            addLog('Full demo completed with real TML models!', 'success');
        } else {
            const error = await response.json();
            log(`❌ Error: ${error.detail || error.message}`);
            addLog('Demo failed - check API server', 'error');
        }
    } catch (error) {
        log(`❌ Error: ${error.message}`);
        addLog(`Demo error: ${error.message}`, 'error');
    }
}

// Run scalability test using API
async function runScalabilityTest() {
    if (!isConnected) {
        await checkConnection();
        if (!isConnected) {
            addLog('Cannot run test - API is offline', 'error');
            return;
        }
    }
    
    const output = document.getElementById('demoOutput');
    output.innerHTML = '';
    
    const log = (message) => {
        output.innerHTML += message + '\n';
        output.scrollTop = output.scrollHeight;
    };
    
    log('⚡ Starting Scalability Test with Real Models');
    log('='.repeat(50));
    
    const startTime = Date.now();
    const numModels = 20; // Reduced for real model testing
    
    log(`Creating ${numModels} real models in chain...`);
    
    try {
        let parentId = null;
        for (let i = 1; i <= numModels; i++) {
            const response = await fetch(`${API_BASE_URL}/api/models/create`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    transaction_id: `scale_txn_${String(i).padStart(3, '0')}`,
                    user_id: `scale_user_${i}`,
                    parent_model_id: parentId,
                    model_type: 'logistic_regression'
                })
            });
            
            if (response.ok) {
                const model = await response.json();
                parentId = model.id;
                
                if (i % 5 === 0) {
                    log(`  Created ${i} models...`);
                }
            } else {
                throw new Error('Failed to create model');
            }
        }
        
        const endTime = Date.now();
        const totalTime = (endTime - startTime) / 1000;
        const avgTime = (totalTime / numModels) * 1000;
        
        log(`\n✅ Created ${numModels} real models in ${totalTime.toFixed(2)} seconds`);
        log(`📊 Average time per model: ${avgTime.toFixed(2)}ms`);
        
        log('\n' + '='.repeat(50));
        log('🎉 Scalability Test Complete!');
        
        await refreshModels();
        await updateStats();
        addLog(`Scalability test completed: ${numModels} real models created`, 'success');
    } catch (error) {
        log(`❌ Error: ${error.message}`);
        addLog(`Scalability test error: ${error.message}`, 'error');
    }
}

// Clear all models using API
async function clearAll() {
    if (!isConnected) {
        await checkConnection();
        if (!isConnected) {
            addLog('Cannot clear models - API is offline', 'error');
            return;
        }
    }
    
    if (confirm('Are you sure you want to clear all models? This cannot be undone.')) {
        try {
            const response = await fetch(`${API_BASE_URL}/api/models`, {
                method: 'DELETE'
            });
            
            if (response.ok) {
                const result = await response.json();
                await refreshModels();
                await updateStats();
                document.getElementById('predictionResults').innerHTML = '';
                document.getElementById('demoOutput').innerHTML = '';
                addLog(result.message, 'warning');
            } else {
                const error = await response.json();
                addLog(`Failed to clear models: ${error.detail}`, 'error');
            }
        } catch (error) {
            addLog(`Error clearing models: ${error.message}`, 'error');
        }
    }
}

// Generate random training data
function generateRandomTraining() {
    const categories = ['electronics', 'books', 'clothing', 'luxury', 'home'];
    
    document.getElementById('trainAmount').value = Math.floor(Math.random() * 500) + 10;
    document.getElementById('trainCategory').value = categories[Math.floor(Math.random() * categories.length)];
    document.getElementById('trainHour').value = Math.floor(Math.random() * 24);
    document.getElementById('trainTarget').value = Math.random() > 0.5 ? 'true' : 'false';
    
    addLog('Generated random training data', 'info');
}

// Add log entry
function addLog(message, type = 'info') {
    const logDiv = document.getElementById('activityLog');
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    
    const icons = {
        info: 'fa-info-circle',
        success: 'fa-check-circle',
        warning: 'fa-exclamation-triangle',
        error: 'fa-times-circle'
    };
    
    entry.innerHTML = `
        <i class="fas ${icons[type]}"></i>
        <span>${message}</span>
        <span class="timestamp">${new Date().toLocaleTimeString()}</span>
    `;
    
    logDiv.insertBefore(entry, logDiv.firstChild);
    
    // Keep only last 20 entries
    while (logDiv.children.length > 20) {
        logDiv.removeChild(logDiv.lastChild);
    }
}

// Helper function for async delays
function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}
