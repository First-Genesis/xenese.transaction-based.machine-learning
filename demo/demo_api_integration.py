#!/usr/bin/env python3
"""
Demo UI Integration with Docker C# Proto.Actor
Add this to your Streamlit app to explicitly use the Docker API
"""

import streamlit as st
import requests
import json
import time
import pandas as pd

API_URL = "http://localhost:5001"

def add_api_processing_section():
    """
    Add this function to your Streamlit app.py to create
    a section for Docker C# Proto.Actor processing
    """
    
    st.markdown("---")
    st.header("🐳 Docker C# Proto.Actor Processing")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.info("""
        **Production Processing via Docker API**
        
        This uses the C# Proto.Actor system running in Docker:
        - TransactionProcessorActor (C#)
        - ModelActor (C#)
        - PhysicsValidatorActor (C#)
        """)
    
    with col2:
        # Check API status
        try:
            response = requests.get(f"{API_URL}/health", timeout=1)
            if response.status_code == 200:
                st.success("✅ Docker API Connected")
            else:
                st.error("❌ Docker API Error")
        except:
            st.warning("⚠️ Docker API Offline")
    
    # Processing options
    st.subheader("Send Data to Docker C# Proto.Actor")
    
    # Input fields
    col1, col2, col3 = st.columns(3)
    with col1:
        x_coord = st.number_input("X Coordinate", value=100, step=2)
    with col2:
        y_coord = st.number_input("Y Coordinate", value=850, step=5)
    with col3:
        thickness = st.number_input("Thickness (mm)", value=19.5, step=0.1, format="%.1f")
    
    # Process button
    if st.button("🚀 Process with C# Proto.Actor (Docker)", type="primary"):
        with st.spinner("Processing via Docker API..."):
            
            # Create transaction
            transaction = {
                "data": {
                    "xCoord": x_coord,
                    "yCoord": y_coord,
                    "thickness": thickness,
                    "minThickness": 15.0,
                    "quality": 0.95,
                    "features": {"feature1": 1.0, "feature2": 2.0}
                },
                "source": "streamlit-ui",
                "metadata": {
                    "timestamp": time.time(),
                    "ui_test": True
                }
            }
            
            # Send to Docker API
            try:
                response = requests.post(
                    f"{API_URL}/api/transactions",
                    json=transaction,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    result = response.json()
                    
                    # Display results
                    st.success("✅ Processed by C# Proto.Actor!")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Transaction ID", result['transactionId'][:8] + "...")
                        st.metric("Processing Time", f"{result['processingTimeMs']:.2f}ms")
                        st.metric("Status", result['status'])
                    
                    with col2:
                        st.metric("Model ID", result['modelId'][:8] + "...")
                        st.metric("Physics Valid", "✅" if result['physicsValid'] else "❌")
                        st.metric("Confidence", f"{result.get('confidence', 0):.1%}")
                    
                    # Show raw response
                    with st.expander("📋 Full Response from C# Proto.Actor"):
                        st.json(result)
                else:
                    st.error(f"Error: {response.status_code}")
            
            except Exception as e:
                st.error(f"Connection Error: {e}")
    
    # Batch processing
    st.subheader("Batch Processing with C# Proto.Actor")
    
    num_points = st.slider("Number of points to process", 1, 20, 5)
    
    if st.button("🔄 Batch Process with C# Proto.Actor"):
        results = []
        progress = st.progress(0)
        status = st.empty()
        
        for i in range(num_points):
            status.text(f"Processing point {i+1}/{num_points}...")
            
            # Create transaction with varying data
            transaction = {
                "data": {
                    "xCoord": 100 + (i * 2),
                    "yCoord": 850 + (i % 10),
                    "thickness": 19.5 - (i * 0.3),
                    "minThickness": 15.0,
                    "quality": 0.95,
                    "features": {"feature1": 1.0, "feature2": 2.0}
                },
                "source": "batch-test",
                "metadata": {"batch_index": i}
            }
            
            try:
                response = requests.post(
                    f"{API_URL}/api/transactions",
                    json=transaction,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    results.append(response.json())
            except:
                pass
            
            progress.progress((i + 1) / num_points)
            time.sleep(0.1)
        
        status.text(f"✅ Processed {len(results)} transactions via C# Proto.Actor")
        
        if results:
            # Show summary
            df = pd.DataFrame(results)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                avg_time = df['processingTimeMs'].mean()
                st.metric("Avg Processing Time", f"{avg_time:.2f}ms")
            with col2:
                valid_count = df['physicsValid'].sum()
                st.metric("Physics Valid", f"{valid_count}/{len(results)}")
            with col3:
                st.metric("Success Rate", f"{len(results)}/{num_points}")
            
            # Show dataframe
            st.dataframe(df[['transactionId', 'status', 'processingTimeMs', 'physicsValid']])

# Example of how to add to existing app.py:
"""
# In your demo/app.py, add this near the bottom of your main app:

# Import the function
from demo_api_integration import add_api_processing_section

# Add it to your Streamlit app
add_api_processing_section()
"""

if __name__ == "__main__":
    # Standalone test
    st.set_page_config(page_title="C# Proto.Actor Integration", layout="wide")
    st.title("🐳 Docker C# Proto.Actor Direct Access")
    add_api_processing_section()
