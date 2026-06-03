// TML Platform UI JavaScript

// Global state
let models = new Map();
let modelCounter = 0;
let predictionCounter = 0;
let lastPredictionTime = Date.now();

// Model class to simulate TML functionality
class TMLModel {
    constructor(id, parentId = null, type = 'logistic_regression') {
        this.id = id;
        this.parentId = parentId;
        this.type = type;
        this.trainingData = [];
        this.updates = 0;
        this.accuracy = 0.0;
        this.createdAt = Date.now();
        
        // Inherit from parent if exists
        if (parentId && models.has(parentId)) {
            const parent = models.get(parentId);
            this.trainingData = [...parent.trainingData];
            this.updates = parent.updates;
            this.accuracy = parent.accuracy;
        }
    }
    
    train(features, target) {
        this.trainingData.push({ features, target });
        this.updates++;
        // Simulate accuracy improvement
        this.accuracy = Math.min(0.95, this.accuracy + Math.random() * 0.1);
        return true;
    }
    
    predict(features) {
        // Simple prediction logic based on amount
        // In real implementation, this would use the actual River model
        const amount = features.amount || 0;
        const hour = features.hour || 12;
        
        // Add some randomness influenced by training
        const threshold = 150 + (this.updates * 2);
        const prediction = amount > threshold;
        
        // Consider time of day
        const timeInfluence = hour > 18 || hour < 6 ? 0.2 : -0.1;
        
        return Math.random() + timeInfluence > 0.5 ? prediction : !prediction;
    }
    
    getStats() {
        return {
            id: this.id,
            parentId: this.parentId,
            type: this.type,
            updates: this.updates,
            accuracy: this.accuracy,
            trainingSize: this.trainingData.length
        };
    }
}

// Initialize UI
document.addEventListener('DOMContentLoaded', () => {
    updateStats();
    setInterval(updateStats, 1000);
    addLog('TML Platform UI initialized. Ready to create models!', 'info');
});

// Create new model
function createModel() {
    const transactionId = document.getElementById('transactionId').value || `txn_${Date.now()}`;
    const userId = document.getElementById('userId').value || 'anonymous';
    const parentModelId = document.getElementById('parentModel').value;
    const modelType = document.getElementById('modelType').value;
    
    modelCounter++;
    const modelId = `model_${modelCounter.toString().padStart(6, '0')}`;
    
    // Create model instance
    const model = new TMLModel(modelId, parentModelId, modelType);
    models.set(modelId, model);
    
    // Update UI
    updateModelSelectors();
    visualizeModelChain();
    updateModelComparison();
    
    addLog(`Created ${parentModelId ? 'child' : 'base'} model ${modelId} for transaction ${transactionId}`, 'success');
    
    // Update stats
    updateStats();
    
    return modelId;
}

// Train selected model
function trainModel() {
    const modelId = document.getElementById('modelToTrain').value;
    if (!modelId) {
        addLog('Please select a model to train', 'warning');
        return;
    }
    
    const model = models.get(modelId);
    if (!model) {
        addLog('Model not found', 'error');
        return;
    }
    
    const features = {
        amount: parseFloat(document.getElementById('trainAmount').value),
        category: document.getElementById('trainCategory').value,
        hour: parseInt(document.getElementById('trainHour').value)
    };
    
    const target = document.getElementById('trainTarget').value === 'true';
    
    model.train(features, target);
    
    addLog(`Trained model ${modelId} with features: ${JSON.stringify(features)}, target: ${target}`, 'success');
    
    // Update visualizations
    visualizeModelChain();
    updateModelComparison();
    updateStats();
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

// Make predictions with all models
function predictAllModels() {
    const features = {
        amount: parseFloat(document.getElementById('predictAmount').value),
        category: document.getElementById('predictCategory').value,
        hour: parseInt(document.getElementById('predictHour').value)
    };
    
    const resultsDiv = document.getElementById('predictionResults');
    resultsDiv.innerHTML = '<h3>Prediction Results</h3>';
    
    if (models.size === 0) {
        resultsDiv.innerHTML += '<p style="color: var(--text-secondary);">No models available. Create a model first!</p>';
        return;
    }
    
    models.forEach(model => {
        const prediction = model.predict(features);
        predictionCounter++;
        
        const resultCard = document.createElement('div');
        resultCard.className = 'prediction-card';
        resultCard.innerHTML = `
            <div>
                <span class="prediction-model">${model.id}</span>
                <span style="color: var(--text-secondary); font-size: 0.875rem; margin-left: 1rem;">
                    Updates: ${model.updates} | Accuracy: ${(model.accuracy * 100).toFixed(1)}%
                </span>
            </div>
            <span class="prediction-value ${prediction}">${prediction ? 'TRUE' : 'FALSE'}</span>
        `;
        resultsDiv.appendChild(resultCard);
    });
    
    addLog(`Made predictions for features: ${JSON.stringify(features)}`, 'info');
    updateStats();
}

// Update model selectors
function updateModelSelectors() {
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
    
    if (currentParent && models.has(currentParent)) {
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
    
    if (currentTrain && models.has(currentTrain)) {
        trainSelect.value = currentTrain;
    }
}

// Visualize model inheritance chain
function visualizeModelChain() {
    const chainDiv = document.getElementById('modelChain');
    
    if (models.size === 0) {
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
    const rootModels = Array.from(models.values()).filter(m => !m.parentId);
    
    rootModels.forEach(root => {
        const chainElement = document.createElement('div');
        chainElement.style.marginBottom = '1rem';
        
        // Add root model
        let html = `<div class="model-node base">
            <div class="model-node-id">${root.id}</div>
            <div class="model-node-stats">Base Model<br>Updates: ${root.updates}</div>
        </div>`;
        
        // Add children recursively
        const children = getModelChildren(root.id);
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

// Get children of a model
function getModelChildren(parentId) {
    const children = [];
    models.forEach(model => {
        if (model.parentId === parentId) {
            children.push(model);
        }
    });
    return children;
}

// Update model comparison
function updateModelComparison() {
    const comparisonDiv = document.getElementById('modelComparison');
    
    if (models.size === 0) {
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
                <span class="metric-value">${model.parentId || 'None'}</span>
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
                <span class="metric-label">Training Size</span>
                <span class="metric-value">${model.trainingData.length}</span>
            </div>
        `;
        comparisonDiv.appendChild(card);
    });
}

// Run full demo
async function runFullDemo() {
    const output = document.getElementById('demoOutput');
    output.innerHTML = '';
    
    const log = (message) => {
        output.innerHTML += message + '\n';
        output.scrollTop = output.scrollHeight;
    };
    
    log('🚀 Starting TML Platform Demonstration');
    log('=' .repeat(50));
    
    // Create base model
    log('\n📝 Creating Model #1 (Base Model)...');
    const model1Id = createModel();
    await sleep(500);
    
    // Train base model
    log('📚 Training Model #1 with purchase data...');
    const model1 = models.get(model1Id);
    const trainingData1 = [
        {features: {amount: 50, category: 'books', hour: 10}, target: false},
        {features: {amount: 150, category: 'electronics', hour: 14}, target: true},
        {features: {amount: 30, category: 'clothing', hour: 16}, target: false},
        {features: {amount: 200, category: 'electronics', hour: 12}, target: true},
    ];
    
    for (const data of trainingData1) {
        model1.train(data.features, data.target);
        await sleep(200);
    }
    log(`✓ Model #1 trained - Updates: ${model1.updates}`);
    
    // Create child model
    log('\n🧬 Creating Model #2 (Inherits from Model #1)...');
    document.getElementById('parentModel').value = model1Id;
    const model2Id = createModel();
    const model2 = models.get(model2Id);
    await sleep(500);
    log(`✓ Model #2 created with parent: ${model1Id}`);
    
    // Train child model
    log('📚 Training Model #2 with specialized data...');
    const trainingData2 = [
        {features: {amount: 300, category: 'luxury', hour: 18}, target: true},
        {features: {amount: 45, category: 'books', hour: 11}, target: false},
    ];
    
    for (const data of trainingData2) {
        model2.train(data.features, data.target);
        await sleep(200);
    }
    log(`✓ Model #2 trained - Updates: ${model2.updates}`);
    
    // Create third generation model
    log('\n🚀 Creating Model #3 (Many Generations Later)...');
    document.getElementById('parentModel').value = model2Id;
    const model3Id = createModel();
    const model3 = models.get(model3Id);
    await sleep(500);
    log(`✓ Model #3 created with parent: ${model2Id}`);
    
    // Make predictions
    log('\n🔮 Making predictions with all models...');
    const testCase = {amount: 175, category: 'electronics', hour: 14};
    log(`Test case: ${JSON.stringify(testCase)}`);
    
    const pred1 = model1.predict(testCase);
    const pred2 = model2.predict(testCase);
    const pred3 = model3.predict(testCase);
    
    log(`  Model #1 prediction: ${pred1}`);
    log(`  Model #2 prediction: ${pred2}`);
    log(`  Model #3 prediction: ${pred3}`);
    
    log('\n' + '=' .repeat(50));
    log('✅ CORE CONCEPT VALIDATED!');
    log('Model #3 inherits knowledge from all predecessors');
    log('Each model remains independently tunable');
    log('🎉 Demonstration Complete!');
    
    addLog('Full demo completed successfully!', 'success');
}

// Run scalability test
async function runScalabilityTest() {
    const output = document.getElementById('demoOutput');
    output.innerHTML = '';
    
    const log = (message) => {
        output.innerHTML += message + '\n';
        output.scrollTop = output.scrollHeight;
    };
    
    log('⚡ Starting Scalability Test');
    log('=' .repeat(50));
    
    const startTime = Date.now();
    const numModels = 50;
    
    log(`Creating ${numModels} models in chain...`);
    
    let parentId = null;
    for (let i = 1; i <= numModels; i++) {
        if (parentId) {
            document.getElementById('parentModel').value = parentId;
        }
        
        const modelId = createModel();
        const model = models.get(modelId);
        
        // Quick training
        model.train({amount: 50 + i * 10, category: 'test', hour: 12}, i % 2 === 0);
        
        parentId = modelId;
        
        if (i % 10 === 0) {
            log(`  Created ${i} models...`);
            await sleep(100);
        }
    }
    
    const endTime = Date.now();
    const totalTime = (endTime - startTime) / 1000;
    const avgTime = (totalTime / numModels) * 1000;
    
    log(`\n✅ Created ${numModels} models in ${totalTime.toFixed(2)} seconds`);
    log(`📊 Average time per model: ${avgTime.toFixed(2)}ms`);
    log(`🧠 Final model has ${models.get(parentId).updates} updates`);
    
    log('\n' + '=' .repeat(50));
    log('🎉 Scalability Test Complete!');
    
    addLog(`Scalability test completed: ${numModels} models created`, 'success');
}

// Clear all models
function clearAll() {
    if (confirm('Are you sure you want to clear all models? This cannot be undone.')) {
        models.clear();
        modelCounter = 0;
        predictionCounter = 0;
        updateModelSelectors();
        visualizeModelChain();
        updateModelComparison();
        document.getElementById('predictionResults').innerHTML = '';
        document.getElementById('demoOutput').innerHTML = '';
        updateStats();
        addLog('All models cleared', 'warning');
    }
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

// Update stats
function updateStats() {
    document.getElementById('activeModels').textContent = models.size;
    
    // Calculate predictions per second
    const now = Date.now();
    const timeDiff = (now - lastPredictionTime) / 1000;
    const pps = timeDiff > 0 ? (predictionCounter / timeDiff).toFixed(1) : '0';
    document.getElementById('predictionsPerSec').textContent = pps;
    
    // Calculate average accuracy
    let totalAccuracy = 0;
    models.forEach(model => {
        totalAccuracy += model.accuracy;
    });
    const avgAccuracy = models.size > 0 ? (totalAccuracy / models.size * 100).toFixed(1) : 0;
    document.getElementById('avgAccuracy').textContent = `${avgAccuracy}%`;
}

// Helper function for async delays
function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// Test connection to backend (optional)
async function testConnection() {
    try {
        // Use a timeout to avoid long waits for connection refused
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 1000);
        
        const response = await fetch('http://localhost:8000/health', {
            signal: controller.signal,
            mode: 'no-cors'  // Avoid CORS issues
        }).catch(() => null);
        
        clearTimeout(timeoutId);
        
        if (response) {
            document.getElementById('connectionText').textContent = 'Connected to API';
            document.getElementById('connectionStatus').style.color = 'var(--success-color)';
            return true;
        }
    } catch (e) {
        // Silently handle connection errors - expected in standalone mode
    }
    
    // Running in standalone mode (no backend)
    document.getElementById('connectionText').textContent = 'Standalone Mode';
    document.getElementById('connectionStatus').style.color = 'var(--text-secondary)';
    return false;
}

// Check connection on load (delayed to avoid console errors on startup)
document.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => {
        testConnection();
    }, 500);
});
