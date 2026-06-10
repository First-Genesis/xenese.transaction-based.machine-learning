#!/usr/bin/env python3
"""
Simple test for the optimization button
"""

import streamlit as st
import mlflow
import numpy as np
import time

st.title("🔬 Test Optimization Button")

# Configuration
optimizer = st.selectbox("Optimizer:", ["TPE", "Random", "CMA-ES"])
trials = st.slider("Trials:", 5, 20, 10)

# Test button
if st.button("🚀 Start Optimization", type="primary"):
    st.write("✅ Button clicked successfully!")
    
    with st.spinner("Running optimization..."):
        try:
            # Connect to MLflow
            mlflow.set_tracking_uri("http://localhost:5003")
            st.write("✅ Connected to MLflow")
            
            # Get experiments
            experiments = mlflow.search_experiments()
            st.write(f"✅ Found {len(experiments)} experiments")
            
            # Find a non-default experiment
            exp = None
            for e in experiments:
                if e.name != "Default":
                    exp = e
                    break
            
            if exp:
                st.write(f"✅ Using experiment: {exp.name}")
                
                # Create MLflow run
                run_name = f"test_{int(time.time())}"
                with mlflow.start_run(experiment_id=exp.experiment_id, run_name=run_name):
                    # Log parameters
                    mlflow.log_param("optimizer", optimizer)
                    mlflow.log_param("trials", trials)
                    
                    # Simulate optimization
                    best = 0.6
                    for i in range(5):
                        score = 0.6 + i * 0.05 + np.random.normal(0, 0.01)
                        if score > best:
                            best = score
                        mlflow.log_metric("accuracy", score, step=i)
                        time.sleep(0.1)
                    
                    mlflow.log_metric("final_accuracy", best)
                
                st.success(f"✅ Optimization complete! Best accuracy: {best:.4f}")
                st.info(f"Run '{run_name}' created in experiment '{exp.name}'")
            else:
                st.error("No experiments found")
                
        except Exception as e:
            st.error(f"Error: {e}")
            st.code(str(e))

# MLflow status
st.subheader("MLflow Status")
try:
    mlflow.set_tracking_uri("http://localhost:5003")
    experiments = mlflow.search_experiments()
    st.success(f"✅ MLflow connected - {len(experiments)} experiments")
except Exception as e:
    st.error(f"❌ MLflow not connected: {e}")
