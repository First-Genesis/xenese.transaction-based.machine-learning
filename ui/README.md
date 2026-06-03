# TML Platform UI

A beautiful, interactive web interface for demonstrating the Transaction-based Machine Learning (TML) Platform concepts.

## Features

- **🎨 Modern Design**: Dark theme with gradient accents and smooth animations
- **🧠 Live Model Creation**: Create models that inherit from parent models
- **📚 Interactive Training**: Train models with custom or random data
- **🔮 Real-time Predictions**: See how different models make different predictions
- **📊 Visual Comparisons**: Compare model performance and statistics
- **⚡ Scalability Testing**: Test creating many models rapidly
- **📈 Live Metrics**: Track active models, predictions/sec, and accuracy

## Quick Start

### Method 1: Python Server (Recommended)

```bash
# Navigate to UI directory
cd TML/ui

# Start the server
python3 server.py

# Open browser to http://localhost:8080
```

### Method 2: Direct File Access

Simply open `index.html` in your web browser:
```bash
open TML/ui/index.html  # macOS
xdg-open TML/ui/index.html  # Linux
start TML/ui/index.html  # Windows
```

## How to Use

### 1. Create Your First Model

1. Enter a Transaction ID (e.g., "txn_001")
2. Enter a User ID (e.g., "user_alice")
3. Leave "Parent Model" as "None" for your first model
4. Click "Create Model"

### 2. Train the Model

1. Select your model from the "Select Model to Train" dropdown
2. Enter training data:
   - Amount: Purchase amount in dollars
   - Category: Type of purchase
   - Hour: Hour of day (0-23)
   - Target: Whether the transaction was successful
3. Click "Train Model" or use "Generate Random Data" for quick testing

### 3. Create Child Models

1. Create another model
2. This time, select your first model as the "Parent Model"
3. The child model inherits all knowledge from its parent!

### 4. Make Predictions

1. Enter test data in the Prediction section
2. Click "Predict with All Models"
3. See how each model makes different predictions based on its training

### 5. Run Demonstrations

- **Full Demo**: Automatically creates and trains a chain of models
- **Scalability Test**: Creates 50 models rapidly to test performance
- **Clear All**: Reset everything to start fresh

## UI Components

### Navigation Bar
- Shows live statistics: active models, predictions/sec, average accuracy

### Model Inheritance Chain
- Visual representation of how models inherit from each other
- Shows parent-child relationships and update counts

### Model Comparison Grid
- Side-by-side comparison of all models
- Shows parent, updates, accuracy, and training size

### Activity Log
- Real-time log of all actions and events
- Color-coded by type (info, success, warning, error)

## Core Concepts Demonstrated

1. **Model Inheritance**: Child models start with parent's knowledge
2. **Independent Learning**: Each model can be trained separately
3. **Incremental Updates**: Models learn continuously without retraining
4. **Scalability**: Create and manage many models efficiently
5. **Unique Predictions**: Each model makes predictions based on its specialized training

## Technical Details

- **Pure JavaScript**: No framework dependencies
- **Responsive Design**: Works on desktop and mobile
- **Standalone Mode**: Works without backend API
- **API Integration Ready**: Can connect to TML backend when available

## Browser Compatibility

- Chrome/Edge 90+
- Firefox 88+
- Safari 14+
- Opera 76+

## Customization

Edit `styles.css` to change:
- Color scheme (CSS variables in `:root`)
- Layout and spacing
- Animations and transitions

Edit `app.js` to change:
- Model behavior
- Prediction logic
- Demo scenarios

## Screenshots

The UI features:
- Gradient header with animated brain icon
- Card-based sections for each functionality
- Real-time model chain visualization
- Color-coded prediction results
- Live activity monitoring

## Future Enhancements

- [ ] Connect to real TML backend API
- [ ] Add data visualization charts
- [ ] Export/import model configurations
- [ ] Advanced training scenarios
- [ ] Performance benchmarking graphs
- [ ] WebSocket support for real-time updates

## License

MIT License - Part of the TML Platform project
