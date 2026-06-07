#!/usr/bin/env python3
"""
A/B Testing Dashboard for TML Platform
Interactive visualization and management of model experiments
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
from scipy import stats

API_URL = "http://localhost:5001"

def show_ab_testing_dashboard():
    """Main A/B Testing dashboard"""
    
    st.title("🎲 A/B Testing Dashboard")
    st.markdown("""
    **Advanced ML Feature**: Run controlled experiments to compare model performance.
    Deploy multiple model variants simultaneously and automatically determine the winner.
    """)
    
    # Tabs for different sections
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🚀 Create Experiment", "📊 Active Experiments", "📈 Results Analysis", 
        "🏆 Concluded Experiments", "🔬 Experiment Simulator"
    ])
    
    with tab1:
        show_create_experiment()
    
    with tab2:
        show_active_experiments()
    
    with tab3:
        show_results_analysis()
    
    with tab4:
        show_concluded_experiments()
    
    with tab5:
        show_experiment_simulator()

def show_create_experiment():
    """Create new A/B test experiment"""
    st.subheader("🚀 Create New Experiment")
    
    col1, col2 = st.columns(2)
    
    with col1:
        experiment_name = st.text_input("Experiment Name", placeholder="e.g., Model Performance Test v2")
        description = st.text_area("Description", placeholder="Describe the hypothesis and goals")
        primary_metric = st.selectbox("Primary Metric", 
            ["Conversion Rate", "Accuracy", "Processing Time", "Confidence Score"])
    
    with col2:
        min_sample_size = st.number_input("Minimum Sample Size", min_value=100, value=1000, step=100)
        confidence_level = st.slider("Confidence Level", 0.90, 0.99, 0.95, 0.01)
        min_duration_days = st.number_input("Minimum Duration (days)", min_value=1, value=7)
    
    st.subheader("Configure Variants")
    
    num_variants = st.number_input("Number of Variants", min_value=2, max_value=5, value=2)
    
    variants = []
    cols = st.columns(num_variants)
    
    for i, col in enumerate(cols[:num_variants]):
        with col:
            st.write(f"**Variant {i+1}**")
            variant_name = st.text_input(f"Name", key=f"v_name_{i}", 
                value=f"{'Control' if i == 0 else f'Treatment {i}'}")
            
            # Generate sample model IDs for demo
            model_id = st.text_input(f"Model ID", key=f"v_model_{i}",
                value=f"{str(np.random.randint(1000, 9999))}-{str(np.random.randint(1000, 9999))}")
            
            traffic_pct = st.slider(f"Traffic %", 0, 100, 100//num_variants, key=f"v_traffic_{i}")
            
            is_control = st.checkbox("Control", value=(i == 0), key=f"v_control_{i}")
            
            variants.append({
                "name": variant_name,
                "model_id": model_id,
                "traffic": traffic_pct,
                "is_control": is_control
            })
    
    # Validate traffic allocation
    total_traffic = sum(v["traffic"] for v in variants)
    if total_traffic != 100:
        st.error(f"⚠️ Traffic allocation must sum to 100% (currently {total_traffic}%)")
    
    # Additional settings
    with st.expander("Advanced Settings"):
        allocation_type = st.selectbox("Allocation Type", 
            ["Random", "Round Robin", "Weighted", "User Based"])
        use_sticky = st.checkbox("Use Sticky Sessions", value=True)
        enable_early_stop = st.checkbox("Enable Early Stopping", value=True)
        mde = st.slider("Minimum Detectable Effect", 0.01, 0.20, 0.05, 0.01,
            help="Smallest effect size you want to detect")
    
    if st.button("🚀 Launch Experiment", type="primary"):
        if experiment_name and total_traffic == 100:
            create_experiment_api(
                experiment_name, description, variants, primary_metric,
                min_sample_size, confidence_level, min_duration_days,
                allocation_type, use_sticky, mde
            )
        else:
            st.error("Please fill all required fields and ensure traffic sums to 100%")

def show_active_experiments():
    """Display active experiments"""
    st.subheader("📊 Active Experiments")
    
    # Fetch active experiments (simulated for demo)
    experiments = fetch_active_experiments()
    
    if not experiments:
        st.info("No active experiments running")
        return
    
    for exp in experiments:
        with st.expander(f"🔬 {exp['name']} - {exp['status']}"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Duration", f"{exp['duration_days']} days")
                st.metric("Total Samples", exp['total_samples'])
            
            with col2:
                st.metric("Variants", exp['variant_count'])
                st.metric("Conversion Rate", f"{exp['overall_conversion']:.2%}")
            
            with col3:
                st.metric("Statistical Power", f"{exp['power']:.0%}")
                if exp['is_significant']:
                    st.success("✅ Statistically Significant")
                else:
                    st.warning("⏳ Gathering Data")
            
            # Variant performance
            st.write("**Variant Performance:**")
            
            variant_data = pd.DataFrame(exp['variants'])
            
            # Create comparison chart
            fig = go.Figure()
            
            for idx, variant in variant_data.iterrows():
                color = 'green' if variant['is_control'] else 'blue'
                fig.add_trace(go.Bar(
                    x=[variant['name']],
                    y=[variant['conversion_rate']],
                    error_y=dict(type='data', array=[variant['confidence_interval']]),
                    marker_color=color,
                    name=variant['name'],
                    text=f"{variant['conversion_rate']:.2%}",
                    textposition='auto'
                ))
            
            fig.update_layout(
                title="Conversion Rate by Variant",
                yaxis_title="Conversion Rate",
                showlegend=False,
                height=300
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Action buttons
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button(f"📈 View Details", key=f"view_{exp['id']}"):
                    st.session_state.selected_experiment = exp['id']
            
            with col2:
                if st.button(f"🏁 Conclude", key=f"conclude_{exp['id']}"):
                    conclude_experiment(exp['id'])
            
            with col3:
                if st.button(f"⏸️ Pause", key=f"pause_{exp['id']}"):
                    pause_experiment(exp['id'])

def show_results_analysis():
    """Detailed analysis of experiment results"""
    st.subheader("📈 Experiment Results Analysis")
    
    # Select experiment
    experiment_id = st.selectbox("Select Experiment", 
        options=["exp-001", "exp-002", "exp-003"],
        format_func=lambda x: f"Experiment {x}")
    
    if experiment_id:
        # Fetch results (simulated)
        results = analyze_experiment_results(experiment_id)
        
        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Winner", results['winner'], 
                delta=f"+{results['winner_lift']:.1%}" if results['winner_lift'] > 0 else None)
        
        with col2:
            st.metric("Confidence", f"{results['confidence']:.1%}")
        
        with col3:
            st.metric("P-Value", f"{results['p_value']:.4f}",
                help="Lower is better (< 0.05 for significance)")
        
        with col4:
            st.metric("Sample Size", f"{results['total_samples']:,}")
        
        # Statistical significance test
        st.subheader("Statistical Analysis")
        
        # Create significance visualization
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=("Conversion Rate Distribution", "Cumulative Conversions",
                          "Statistical Power Over Time", "Confidence Intervals"),
            specs=[[{"type": "violin"}, {"type": "scatter"}],
                   [{"type": "scatter"}, {"type": "bar"}]]
        )
        
        # Conversion rate distributions
        for variant in results['variants']:
            samples = generate_conversion_samples(
                variant['conversion_rate'],
                variant['sample_size']
            )
            fig.add_trace(
                go.Violin(y=samples, name=variant['name'], side='positive'),
                row=1, col=1
            )
        
        # Cumulative conversions over time
        time_points = np.arange(0, results['duration_hours'])
        for variant in results['variants']:
            cumulative = np.cumsum(np.random.binomial(
                1, variant['conversion_rate'], len(time_points)
            ))
            fig.add_trace(
                go.Scatter(x=time_points, y=cumulative, name=variant['name'],
                          mode='lines'),
                row=1, col=2
            )
        
        # Statistical power over time
        power_timeline = calculate_power_timeline(results)
        fig.add_trace(
            go.Scatter(x=power_timeline['time'], y=power_timeline['power'],
                      mode='lines+markers', name='Statistical Power'),
            row=2, col=1
        )
        fig.add_hline(y=0.8, line_dash="dash", line_color="red",
                     annotation_text="Target Power (80%)", row=2, col=1)
        
        # Confidence intervals
        for variant in results['variants']:
            fig.add_trace(
                go.Bar(
                    x=[variant['name']],
                    y=[variant['conversion_rate']],
                    error_y=dict(
                        type='data',
                        symmetric=False,
                        array=[variant['ci_upper'] - variant['conversion_rate']],
                        arrayminus=[variant['conversion_rate'] - variant['ci_lower']]
                    ),
                    name=variant['name']
                ),
                row=2, col=2
            )
        
        fig.update_layout(height=700, showlegend=True)
        st.plotly_chart(fig, use_container_width=True)
        
        # Detailed metrics table
        st.subheader("Detailed Metrics")
        
        metrics_df = pd.DataFrame(results['variants'])
        metrics_df['lift'] = metrics_df['lift'].apply(lambda x: f"{x:.2%}" if x else "—")
        metrics_df['conversion_rate'] = metrics_df['conversion_rate'].apply(lambda x: f"{x:.3%}")
        metrics_df['p_value'] = metrics_df['p_value'].apply(lambda x: f"{x:.4f}" if x else "—")
        
        st.dataframe(metrics_df, use_container_width=True)
        
        # Recommendations
        st.subheader("📋 Recommendations")
        
        recommendations = generate_recommendations(results)
        for rec in recommendations:
            if rec['type'] == 'success':
                st.success(rec['message'])
            elif rec['type'] == 'warning':
                st.warning(rec['message'])
            else:
                st.info(rec['message'])

def show_concluded_experiments():
    """Display concluded experiments"""
    st.subheader("🏆 Concluded Experiments")
    
    # Fetch concluded experiments (simulated)
    concluded = fetch_concluded_experiments()
    
    if not concluded:
        st.info("No concluded experiments")
        return
    
    # Summary statistics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Experiments", len(concluded))
    
    with col2:
        successful = sum(1 for e in concluded if e['was_successful'])
        success_rate = successful/len(concluded) if concluded else 0
        st.metric("Successful", successful, 
                 delta=f"{success_rate:.0%}")
    
    with col3:
        avg_lift = np.mean([e['winner_lift'] for e in concluded if e['winner_lift']])
        st.metric("Average Lift", f"{avg_lift:.1%}")
    
    with col4:
        avg_duration = np.mean([e['duration_days'] for e in concluded])
        st.metric("Avg Duration", f"{avg_duration:.1f} days")
    
    # Experiments table
    exp_df = pd.DataFrame(concluded)
    exp_df['concluded_at'] = pd.to_datetime(exp_df['concluded_at'])
    exp_df = exp_df.sort_values('concluded_at', ascending=False)
    
    # Format columns
    exp_df['winner_lift'] = exp_df['winner_lift'].apply(lambda x: f"+{x:.1%}" if x > 0 else f"{x:.1%}}")
    exp_df['confidence'] = exp_df['confidence'].apply(lambda x: f"{x:.0%}")
    
    st.dataframe(
        exp_df[['name', 'winner', 'winner_lift', 'confidence', 'duration_days', 'concluded_at']],
        use_container_width=True
    )
    
    # Success rate over time
    st.subheader("Success Rate Trend")
    
    exp_df['month'] = exp_df['concluded_at'].dt.to_period('M')
    monthly_stats = exp_df.groupby('month').agg({
        'was_successful': 'mean',
        'winner_lift': 'mean'
    })
    
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=("Success Rate Over Time", "Average Lift Over Time")
    )
    
    fig.add_trace(
        go.Scatter(
            x=monthly_stats.index.astype(str),
            y=monthly_stats['was_successful'],
            mode='lines+markers',
            name='Success Rate',
            line=dict(color='green')
        ),
        row=1, col=1
    )
    
    fig.add_trace(
        go.Bar(
            x=monthly_stats.index.astype(str),
            y=monthly_stats['winner_lift'],
            name='Average Lift',
            marker_color='blue'
        ),
        row=1, col=2
    )
    
    fig.update_layout(height=400, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

def show_experiment_simulator():
    """Interactive experiment simulator"""
    st.subheader("🔬 Experiment Simulator")
    st.markdown("""
    Simulate an A/B test to understand statistical power and sample size requirements.
    """)
    
    col1, col2 = st.columns(2)
    
    with col1:
        control_rate = st.slider("Control Conversion Rate", 0.01, 0.50, 0.10, 0.01)
        effect_size = st.slider("Expected Lift", 0.01, 0.50, 0.10, 0.01)
        sample_size = st.number_input("Sample Size per Variant", 100, 100000, 1000, 100)
    
    with col2:
        confidence = st.slider("Confidence Level", 0.90, 0.99, 0.95, 0.01)
        power_target = st.slider("Target Power", 0.70, 0.95, 0.80, 0.05)
        num_simulations = st.number_input("Simulations", 100, 10000, 1000, 100)
    
    if st.button("🎲 Run Simulation"):
        simulate_experiment(
            control_rate, effect_size, sample_size,
            confidence, power_target, num_simulations
        )

# Helper functions

def create_experiment_api(name, description, variants, primary_metric,
                         min_sample_size, confidence_level, min_duration_days,
                         allocation_type, use_sticky, mde):
    """Create experiment via API"""
    try:
        # Format request
        request = {
            "name": name,
            "description": description,
            "variants": [
                {
                    "name": v["name"],
                    "modelId": v["model_id"],
                    "trafficPercentage": v["traffic"],
                    "isControl": v["is_control"]
                }
                for v in variants
            ],
            "primaryMetric": primary_metric,
            "minSampleSize": min_sample_size,
            "confidenceLevel": confidence_level,
            "minDurationDays": min_duration_days,
            "allocationType": allocation_type,
            "useStickySessions": use_sticky,
            "minimumDetectableEffect": mde
        }
        
        response = requests.post(f"{API_URL}/api/experiment", json=request, timeout=5)
        
        if response.status_code == 200:
            result = response.json()
            st.success(f"✅ Experiment created: {result['experimentId']}")
            st.balloons()
        else:
            st.error(f"Failed to create experiment: {response.status_code}")
    except Exception as e:
        st.error(f"Error creating experiment: {e}")

def fetch_active_experiments():
    """Fetch active experiments (simulated for demo)"""
    # In production, this would call the API
    return [
        {
            "id": "exp-001",
            "name": "Model Optimization Test",
            "status": "Running",
            "duration_days": 5,
            "total_samples": 5420,
            "variant_count": 2,
            "overall_conversion": 0.125,
            "power": 0.75,
            "is_significant": False,
            "variants": [
                {
                    "name": "Control",
                    "is_control": True,
                    "conversion_rate": 0.12,
                    "confidence_interval": 0.015,
                    "sample_size": 2710
                },
                {
                    "name": "Treatment",
                    "is_control": False,
                    "conversion_rate": 0.13,
                    "confidence_interval": 0.016,
                    "sample_size": 2710
                }
            ]
        }
    ]

def analyze_experiment_results(experiment_id):
    """Analyze experiment results (simulated)"""
    return {
        "winner": "Treatment A",
        "winner_lift": 0.152,
        "confidence": 0.96,
        "p_value": 0.0234,
        "total_samples": 10000,
        "duration_hours": 168,
        "variants": [
            {
                "name": "Control",
                "conversion_rate": 0.10,
                "sample_size": 5000,
                "lift": 0,
                "p_value": None,
                "ci_lower": 0.092,
                "ci_upper": 0.108
            },
            {
                "name": "Treatment A",
                "conversion_rate": 0.115,
                "sample_size": 5000,
                "lift": 0.15,
                "p_value": 0.0234,
                "ci_lower": 0.106,
                "ci_upper": 0.124
            }
        ]
    }

def fetch_concluded_experiments():
    """Fetch concluded experiments (simulated)"""
    return [
        {
            "name": "Homepage Redesign",
            "winner": "Variant B",
            "winner_lift": 0.23,
            "confidence": 0.98,
            "duration_days": 14,
            "concluded_at": datetime.now() - timedelta(days=5),
            "was_successful": True
        },
        {
            "name": "Checkout Flow",
            "winner": "Control",
            "winner_lift": 0.0,
            "confidence": 0.85,
            "duration_days": 7,
            "concluded_at": datetime.now() - timedelta(days=12),
            "was_successful": False
        }
    ]

def generate_conversion_samples(rate, size):
    """Generate conversion rate samples for visualization"""
    return np.random.beta(rate * 100, (1 - rate) * 100, size)

def calculate_power_timeline(results):
    """Calculate statistical power over time"""
    time_points = np.linspace(100, results['total_samples'], 50)
    power_values = []
    
    for n in time_points:
        # Simplified power calculation
        effect_size = 0.15
        z_alpha = stats.norm.ppf(0.975)
        z_beta = np.sqrt(n) * effect_size - z_alpha
        power = stats.norm.cdf(z_beta)
        power_values.append(power)
    
    return {
        "time": time_points,
        "power": power_values
    }

def generate_recommendations(results):
    """Generate recommendations based on results"""
    recommendations = []
    
    if results['confidence'] > 0.95 and results['p_value'] < 0.05:
        recommendations.append({
            "type": "success",
            "message": f"✅ Experiment is statistically significant. {results['winner']} is the clear winner."
        })
    elif results['p_value'] > 0.10:
        recommendations.append({
            "type": "warning",
            "message": "⚠️ Results are not statistically significant. Consider running longer or increasing sample size."
        })
    
    if results['total_samples'] < 1000:
        recommendations.append({
            "type": "info",
            "message": "📊 Sample size is relatively small. Results may not be reliable."
        })
    
    return recommendations

def simulate_experiment(control_rate, effect_size, sample_size, confidence, power_target, num_simulations):
    """Run experiment simulation"""
    with st.spinner(f"Running {num_simulations} simulations..."):
        treatment_rate = control_rate * (1 + effect_size)
        significant_count = 0
        
        for _ in range(num_simulations):
            # Generate samples
            control_conversions = np.random.binomial(sample_size, control_rate)
            treatment_conversions = np.random.binomial(sample_size, treatment_rate)
            
            # Perform chi-square test
            contingency = np.array([
                [control_conversions, sample_size - control_conversions],
                [treatment_conversions, sample_size - treatment_conversions]
            ])
            _, p_value, _, _ = stats.chi2_contingency(contingency)
            
            if p_value < (1 - confidence):
                significant_count += 1
        
        observed_power = significant_count / num_simulations
        
        # Display results
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("Observed Power", f"{observed_power:.1%}",
                     delta=f"{observed_power - power_target:.1%}")
        
        with col2:
            required_n = calculate_required_sample_size(
                control_rate, treatment_rate, confidence, power_target
            )
            st.metric("Required Sample Size", f"{required_n:,}")
        
        if observed_power < power_target:
            st.warning(f"⚠️ Current sample size ({sample_size:,}) is insufficient to achieve {power_target:.0%} power")
        else:
            st.success(f"✅ Current sample size is adequate for {power_target:.0%} power")

def calculate_required_sample_size(p1, p2, confidence, power):
    """Calculate required sample size for given parameters"""
    z_alpha = stats.norm.ppf(1 - (1 - confidence) / 2)
    z_beta = stats.norm.ppf(power)
    
    p_bar = (p1 + p2) / 2
    n = ((z_alpha * np.sqrt(2 * p_bar * (1 - p_bar)) + 
          z_beta * np.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2) / ((p1 - p2) ** 2)
    
    return int(np.ceil(n))

def conclude_experiment(experiment_id):
    """Conclude an experiment"""
    st.info(f"Concluding experiment {experiment_id}...")

def pause_experiment(experiment_id):
    """Pause an experiment"""
    st.info(f"Pausing experiment {experiment_id}...")

# Main app
if __name__ == "__main__":
    st.set_page_config(
        page_title="TML A/B Testing",
        page_icon="🎲",
        layout="wide"
    )
    
    show_ab_testing_dashboard()
