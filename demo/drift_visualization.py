#!/usr/bin/env python3
"""
Drift Detection Visualization for TML Platform Demo
Shows real-time model drift monitoring and alerts
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import requests
import json
from datetime import datetime, timedelta
import time

API_URL = "http://localhost:5001"

def show_drift_dashboard():
    """Main drift detection dashboard"""
    
    st.title("🔍 Model Drift Detection Dashboard")
    st.markdown("""
    **Advanced ML Feature**: Real-time monitoring of data drift and concept drift across all TML models.
    This system automatically detects when models need retraining due to distribution shifts.
    """)
    
    # Get drift summary
    summary = fetch_drift_summary()
    
    # Show service status banner
    if summary.get('status') == 'simulated':
        st.info("🟡 **Service Status**: Using simulated data - Backend service unavailable")
        
        # Add service diagnostic tools
        with st.expander("🔧 Service Diagnostics"):
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔄 Test Redis Connection"):
                    test_redis_connection()
            with col2:
                if st.button("🚀 Initialize Drift Service"):
                    initialize_drift_service()
    else:
        st.success("🟢 **Service Status**: Connected to drift detection backend")
    
    # Display key metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Models Monitored",
            summary.get('totalModelsMonitored', 0),
            help="Total number of active models being monitored"
        )
    
    with col2:
        drift_count = summary.get('modelsWithDrift', 0)
        total = summary.get('totalModelsMonitored', 1)
        drift_pct = (drift_count / max(total, 1)) * 100
        st.metric(
            "Models with Drift",
            f"{drift_count} ({drift_pct:.1f}%)",
            delta=f"+{drift_count}" if drift_count > 0 else "0",
            delta_color="inverse",
            help="Models showing significant drift"
        )
    
    with col3:
        avg_drift = summary.get('averageDataDriftScore', 0)
        st.metric(
            "Avg Data Drift",
            f"{avg_drift:.3f}",
            delta=f"+{avg_drift:.3f}" if avg_drift > 0.1 else None,
            delta_color="inverse",
            help="Average PSI score across all models"
        )
    
    with col4:
        critical = summary.get('criticalModels', 0)
        st.metric(
            "Critical Models",
            critical,
            delta=f"⚠️ {critical}" if critical > 0 else "✅ 0",
            delta_color="inverse" if critical > 0 else "normal",
            help="Models requiring immediate attention"
        )
    
    # Tabs for different views
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Overview", "🚨 Alerts", "📈 Trends", "🔬 Feature Analysis", "🔄 Retraining"
    ])
    
    with tab1:
        show_drift_overview(summary)
    
    with tab2:
        show_drift_alerts()
    
    with tab3:
        show_drift_trends()
    
    with tab4:
        show_feature_analysis()
    
    with tab5:
        show_retraining_panel()

def show_drift_overview(summary):
    """Display drift overview visualization"""
    st.subheader("Drift Detection Overview")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Drift severity distribution
        fig = create_drift_severity_chart(summary)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Drift type comparison
        fig = create_drift_type_comparison(summary)
        st.plotly_chart(fig, use_container_width=True)
    
    # Live drift detection simulation
    st.subheader("Live Drift Detection")
    
    if st.button("🔄 Simulate Drift Detection"):
        simulate_drift_detection()

def show_drift_alerts():
    """Display recent drift alerts"""
    st.subheader("🚨 Recent Drift Alerts")
    
    alerts = fetch_drift_alerts()
    
    if alerts:
        for alert in alerts[:10]:
            severity = alert.get('severity', 'Unknown')
            severity_icon = get_severity_icon(severity)
            
            with st.expander(f"{severity_icon} Model {alert.get('modelId', 'Unknown')[:8]}... - {alert.get('timestamp', '')}"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"**Data Drift Score**: {alert.get('dataDriftScore', 0):.3f}")
                    st.write(f"**Concept Drift Score**: {alert.get('conceptDriftScore', 0):.3f}")
                    st.write(f"**Severity**: {severity}")
                
                with col2:
                    st.write(f"**Affected Features**: {', '.join(alert.get('affectedFeatures', []))}")
                    st.write(f"**Recommended Action**: {alert.get('recommendedAction', 'Monitor')}")
                
                st.write(f"**Description**: {alert.get('description', '')}")
    else:
        st.info("No recent drift alerts")

def show_drift_trends():
    """Display drift trends over time"""
    st.subheader("📈 Drift Trends Analysis")
    
    # Generate sample trend data
    dates = pd.date_range(end=datetime.now(), periods=30, freq='D')
    
    # Create trend data
    trend_data = pd.DataFrame({
        'Date': dates,
        'Data Drift': np.cumsum(np.random.randn(30) * 0.01) + 0.1,
        'Concept Drift': np.cumsum(np.random.randn(30) * 0.008) + 0.08,
        'Models Affected': np.random.poisson(5, 30)
    })
    
    # Drift scores over time
    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=("Drift Scores Over Time", "Models Affected"),
        vertical_spacing=0.15,
        specs=[[{"secondary_y": False}], [{"secondary_y": False}]]
    )
    
    # Add drift score traces
    fig.add_trace(
        go.Scatter(
            x=trend_data['Date'],
            y=trend_data['Data Drift'],
            mode='lines+markers',
            name='Data Drift',
            line=dict(color='#FF6B6B', width=2)
        ),
        row=1, col=1
    )
    
    fig.add_trace(
        go.Scatter(
            x=trend_data['Date'],
            y=trend_data['Concept Drift'],
            mode='lines+markers',
            name='Concept Drift',
            line=dict(color='#4ECDC4', width=2)
        ),
        row=1, col=1
    )
    
    # Add threshold lines
    fig.add_hline(y=0.2, line_dash="dash", line_color="red", 
                  annotation_text="Critical Threshold", row=1, col=1)
    fig.add_hline(y=0.1, line_dash="dash", line_color="orange", 
                  annotation_text="Warning Threshold", row=1, col=1)
    
    # Add models affected
    fig.add_trace(
        go.Bar(
            x=trend_data['Date'],
            y=trend_data['Models Affected'],
            name='Models with Drift',
            marker_color='#95E1D3'
        ),
        row=2, col=1
    )
    
    fig.update_layout(height=600, showlegend=True)
    fig.update_xaxes(title_text="Date", row=2, col=1)
    fig.update_yaxes(title_text="Drift Score", row=1, col=1)
    fig.update_yaxes(title_text="Count", row=2, col=1)
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Statistical summary
    st.subheader("Statistical Summary")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.info(f"""
        **Data Drift Statistics**
        - Mean: {trend_data['Data Drift'].mean():.3f}
        - Std Dev: {trend_data['Data Drift'].std():.3f}
        - Max: {trend_data['Data Drift'].max():.3f}
        """)
    
    with col2:
        st.info(f"""
        **Concept Drift Statistics**
        - Mean: {trend_data['Concept Drift'].mean():.3f}
        - Std Dev: {trend_data['Concept Drift'].std():.3f}
        - Max: {trend_data['Concept Drift'].max():.3f}
        """)
    
    with col3:
        st.info(f"""
        **Model Impact**
        - Total Affected: {trend_data['Models Affected'].sum()}
        - Daily Average: {trend_data['Models Affected'].mean():.1f}
        - Peak Day: {trend_data['Models Affected'].max()}
        """)

def show_feature_analysis():
    """Display feature-level drift analysis"""
    st.subheader("🔬 Feature Drift Analysis")
    
    # Feature selection
    features = ['thickness', 'xCoord', 'yCoord', 'quality', 'minThickness']
    selected_feature = st.selectbox("Select Feature", features)
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        hours = st.slider("Time Window (hours)", 1, 168, 24)
    
    with col2:
        if st.button("Analyze Feature Drift"):
            analyze_feature_drift(selected_feature, hours)
    
    # Display feature drift visualization
    st.subheader(f"Feature: {selected_feature}")
    
    # Generate sample data for visualization
    timestamps = pd.date_range(end=datetime.now(), periods=100, freq='15min')
    
    # Simulate feature values with drift
    baseline_mean = 19.5 if selected_feature == 'thickness' else 100
    baseline_std = 0.5 if selected_feature == 'thickness' else 10
    
    # Add drift after point 60
    values = []
    drift_scores = []
    for i in range(100):
        if i < 60:
            val = np.random.normal(baseline_mean, baseline_std)
            drift = np.random.uniform(0, 0.05)
        else:
            # Introduce drift
            val = np.random.normal(baseline_mean - 0.5, baseline_std * 1.5)
            drift = np.random.uniform(0.1, 0.3)
        values.append(val)
        drift_scores.append(drift)
    
    # Create subplot figure
    fig = make_subplots(
        rows=3, cols=1,
        subplot_titles=(
            f"{selected_feature} Values Over Time",
            "Distribution Comparison",
            "Drift Score Timeline"
        ),
        row_heights=[0.4, 0.3, 0.3],
        vertical_spacing=0.12
    )
    
    # Feature values over time
    fig.add_trace(
        go.Scatter(
            x=timestamps,
            y=values,
            mode='lines',
            name=selected_feature,
            line=dict(color='#3498db')
        ),
        row=1, col=1
    )
    
    # Mark drift point
    fig.add_vline(x=timestamps[60], line_dash="dash", line_color="red",
                  annotation_text="Drift Detected", row=1, col=1)
    
    # Distribution comparison
    fig.add_trace(
        go.Histogram(
            x=values[:60],
            name='Baseline',
            opacity=0.7,
            marker_color='green',
            nbinsx=20
        ),
        row=2, col=1
    )
    
    fig.add_trace(
        go.Histogram(
            x=values[60:],
            name='Current',
            opacity=0.7,
            marker_color='red',
            nbinsx=20
        ),
        row=2, col=1
    )
    
    # Drift scores
    fig.add_trace(
        go.Scatter(
            x=timestamps,
            y=drift_scores,
            mode='lines',
            fill='tozeroy',
            name='Drift Score',
            line=dict(color='#e74c3c')
        ),
        row=3, col=1
    )
    
    fig.add_hline(y=0.1, line_dash="dash", line_color="orange",
                  annotation_text="Threshold", row=3, col=1)
    
    fig.update_layout(height=800, showlegend=True)
    st.plotly_chart(fig, use_container_width=True)
    
    # Feature statistics
    st.subheader("Feature Statistics")
    
    stats_df = pd.DataFrame({
        'Metric': ['PSI Score', 'KS Statistic', 'Mean Shift', 'Variance Ratio'],
        'Value': [0.245, 0.312, 0.5, 1.8],
        'Status': ['⚠️ Warning', '🔴 Critical', '⚠️ Warning', '🔴 Critical']
    })
    
    st.dataframe(stats_df, use_container_width=True)

def show_retraining_panel():
    """Display model retraining interface"""
    st.subheader("🔄 Model Retraining Management")
    
    # Retraining queue
    st.info("**Automatic Retraining Queue**")
    
    queue_data = pd.DataFrame({
        'Model ID': ['model_001', 'model_002', 'model_003'],
        'Drift Score': [0.35, 0.28, 0.22],
        'Priority': ['🔴 High', '⚠️ Medium', '⚠️ Medium'],
        'Status': ['⏳ Queued', '🔄 Processing', '⏳ Queued'],
        'Requested': ['2 mins ago', '5 mins ago', '10 mins ago']
    })
    
    st.dataframe(queue_data, use_container_width=True)
    
    # Manual retraining
    st.subheader("Manual Retraining Request")
    
    col1, col2 = st.columns(2)
    
    with col1:
        model_id = st.text_input("Model ID", placeholder="Enter model GUID")
        reason = st.text_area("Reason for Retraining", placeholder="Describe why retraining is needed")
    
    with col2:
        priority = st.selectbox("Priority", ["Normal", "High", "Critical"])
        
        if st.button("🚀 Trigger Retraining", type="primary"):
            if model_id:
                trigger_retraining(model_id, reason, priority)
            else:
                st.error("Please enter a Model ID")
    
    # Retraining history
    st.subheader("Recent Retraining History")
    
    history_data = pd.DataFrame({
        'Model': ['model_abc', 'model_def', 'model_ghi'],
        'Triggered': ['1 hour ago', '3 hours ago', '6 hours ago'],
        'Reason': ['Drift detected', 'Manual request', 'Scheduled'],
        'Result': ['✅ Success', '✅ Success', '❌ Failed'],
        'Improvement': ['+5.2%', '+3.1%', 'N/A']
    })
    
    st.dataframe(history_data, use_container_width=True)

# Helper functions

def fetch_drift_summary():
    """Fetch drift summary from API with enhanced error handling"""
    try:
        response = requests.get(f"{API_URL}/api/drift/summary", timeout=3)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 500:
            st.error("🔴 **Drift Service Error**: Internal server error (check Redis/DB connections)")
        elif response.status_code == 404:
            st.warning("🟡 **Drift Service**: Endpoints not found (service may not be configured)")
        else:
            st.warning(f"🟡 **Drift Service**: API returned status {response.status_code}")
    except requests.exceptions.Timeout:
        st.warning("🟡 **Drift Service**: Request timed out (service may be overloaded)")
    except requests.exceptions.ConnectionError:
        st.info("🟡 **Drift Service**: Connection failed (using simulated data)")
    except Exception as e:
        st.error(f"🔴 **Drift Service Error**: {str(e)}")
    
    # Return enhanced sample data if API unavailable
    return {
        'totalModelsMonitored': 150,
        'modelsWithDrift': 23,
        'averageDataDriftScore': 0.085,
        'averageConceptDriftScore': 0.062,
        'criticalModels': 5,
        'timestamp': datetime.now().isoformat(),
        'status': 'simulated'
    }

def fetch_drift_alerts():
    """Fetch recent drift alerts"""
    try:
        response = requests.get(f"{API_URL}/api/drift/alerts?limit=10", timeout=2)
        if response.status_code == 200:
            return response.json().get('alerts', [])
    except:
        pass
    
    # Return sample alerts if API unavailable
    return [
        {
            'modelId': 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
            'timestamp': datetime.now().isoformat(),
            'dataDriftScore': 0.312,
            'conceptDriftScore': 0.145,
            'severity': 'High',
            'affectedFeatures': ['thickness', 'quality'],
            'recommendedAction': 'Immediate retraining required',
            'description': 'Significant drift detected in thickness measurements'
        }
    ]

def create_drift_severity_chart(summary):
    """Create drift severity distribution chart"""
    
    # Calculate severity distribution
    total = summary.get('totalModelsMonitored', 1)
    critical = summary.get('criticalModels', 0)
    with_drift = summary.get('modelsWithDrift', 0)
    
    high = critical
    medium = max(0, with_drift - critical) // 2
    low = max(0, with_drift - critical - medium)
    none = max(0, total - with_drift)
    
    fig = go.Figure(data=[
        go.Bar(
            x=['None', 'Low', 'Medium', 'High', 'Critical'],
            y=[none, low, medium, high, critical],
            marker_color=['#27ae60', '#f39c12', '#e67e22', '#e74c3c', '#c0392b']
        )
    ])
    
    fig.update_layout(
        title="Drift Severity Distribution",
        xaxis_title="Severity Level",
        yaxis_title="Number of Models",
        showlegend=False
    )
    
    return fig

def create_drift_type_comparison(summary):
    """Create drift type comparison chart"""
    
    fig = go.Figure(data=[
        go.Scatterpolar(
            r=[summary.get('averageDataDriftScore', 0) * 100,
               summary.get('averageConceptDriftScore', 0) * 100,
               (summary.get('modelsWithDrift', 0) / max(summary.get('totalModelsMonitored', 1), 1)) * 100],
            theta=['Data Drift', 'Concept Drift', 'Models Affected'],
            fill='toself',
            name='Current Status'
        ),
        go.Scatterpolar(
            r=[10, 10, 10],
            theta=['Data Drift', 'Concept Drift', 'Models Affected'],
            fill='toself',
            name='Threshold',
            line=dict(dash='dash')
        )
    ])
    
    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 50]
            )
        ),
        title="Drift Type Analysis",
        showlegend=True
    )
    
    return fig

def simulate_drift_detection():
    """Simulate live drift detection"""
    
    placeholder = st.empty()
    
    for i in range(10):
        with placeholder.container():
            st.write(f"🔄 Checking model batch {i+1}/10...")
            
            # Simulate detection
            models_checked = (i + 1) * 15
            drift_found = np.random.randint(0, 3)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Models Checked", models_checked)
            with col2:
                st.metric("Drift Detected", drift_found)
            with col3:
                st.metric("Processing Time", f"{np.random.uniform(50, 150):.1f}ms")
            
            if drift_found > 0:
                st.warning(f"⚠️ Drift detected in {drift_found} models!")
            
            time.sleep(0.5)
    
    placeholder.success("✅ Drift detection cycle complete!")

def analyze_feature_drift(feature, hours):
    """Analyze drift for specific feature"""
    try:
        response = requests.get(
            f"{API_URL}/api/drift/features/{feature}?hours={hours}",
            timeout=5
        )
        if response.status_code == 200:
            result = response.json()
            st.success(f"✅ Analysis complete for {feature}")
            st.json(result)
        else:
            st.error(f"Failed to analyze feature drift: {response.status_code}")
    except Exception as e:
        st.error(f"Error analyzing feature drift: {e}")

def trigger_retraining(model_id, reason, priority):
    """Trigger model retraining via API"""
    try:
        response = requests.post(
            f"{API_URL}/api/drift/retrain/{model_id}",
            json={"reason": reason, "priority": priority},
            timeout=5
        )
        if response.status_code == 200:
            st.success("✅ Retraining request submitted successfully!")
            st.json(response.json())
        else:
            st.error(f"Failed to trigger retraining: {response.status_code}")
    except Exception as e:
        st.error(f"Error triggering retraining: {e}")

def get_severity_icon(severity):
    """Get icon for severity level"""
    icons = {
        'Critical': '🔴',
        'High': '🟠',
        'Medium': '🟡',
        'Low': '🔵',
        'None': '🟢'
    }
    return icons.get(severity, '⚪')

def test_redis_connection():
    """Test Redis connection and display results"""
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, decode_responses=True)
        
        # Test basic connection
        r.ping()
        st.success("✅ Redis connection successful")
        
        # Test read/write
        test_key = "tml:test:connection"
        r.set(test_key, "test_value", ex=10)  # Expire in 10 seconds
        value = r.get(test_key)
        
        if value == "test_value":
            st.success("✅ Redis read/write operations working")
        else:
            st.warning("⚠️ Redis read/write test failed")
            
        # Show Redis info
        info = r.info()
        st.info(f"📊 Redis version: {info.get('redis_version', 'Unknown')}")
        st.info(f"📊 Connected clients: {info.get('connected_clients', 'Unknown')}")
        
    except ImportError:
        st.error("❌ Redis Python client not installed")
    except Exception as e:
        st.error(f"❌ Redis connection failed: {str(e)}")

def initialize_drift_service():
    """Initialize the drift detection service with sample data"""
    try:
        # Try to initialize via API
        response = requests.post(f"{API_URL}/api/drift/initialize", timeout=5)
        if response.status_code == 200:
            st.success("✅ Drift service initialized successfully")
        else:
            # Fallback: Initialize Redis directly
            initialize_redis_drift_data()
    except:
        # Fallback: Initialize Redis directly
        initialize_redis_drift_data()

def initialize_redis_drift_data():
    """Initialize Redis with sample drift data"""
    try:
        import redis
        import json
        
        r = redis.Redis(host='localhost', port=6379, decode_responses=True)
        
        # Initialize drift summary
        summary_data = {
            'totalModelsMonitored': 0,
            'modelsWithDrift': 0,
            'averageDataDriftScore': 0.0,
            'averageConceptDriftScore': 0.0,
            'criticalModels': 0,
            'timestamp': datetime.now().isoformat()
        }
        
        r.set("drift:summary:latest", json.dumps(summary_data), ex=3600)
        st.success("✅ Initialized Redis with default drift data")
        st.info("🔄 Refresh the page to see updated drift metrics")
        
    except ImportError:
        st.error("❌ Redis Python client not installed")
    except Exception as e:
        st.error(f"❌ Failed to initialize Redis data: {str(e)}")

# Main app
if __name__ == "__main__":
    st.set_page_config(
        page_title="TML Drift Detection",
        page_icon="🔍",
        layout="wide"
    )
    
    show_drift_dashboard()
