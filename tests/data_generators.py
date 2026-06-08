"""
Real Data Generators for End-to-End TML Testing

Generates realistic datasets for different engineering domains:
- Heat Exchanger Operations
- Fluid Flow Systems
- Manufacturing Processes
- Financial Transactions
- IoT Sensor Networks
"""

import math
import random
from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta
from typing import Any
from typing import Dict
from typing import List
from typing import Tuple

import numpy as np
import pandas as pd


@dataclass
class TestDataset:
    """Container for test dataset with metadata"""

    name: str
    domain: str
    transactions: List[Dict[str, Any]]
    expected_physics_violations: int
    expected_model_count: int
    description: str


class HeatExchangerDataGenerator:
    """Generate realistic heat exchanger operation data"""

    def __init__(self, seed: int = 42):
        np.random.seed(seed)
        random.seed(seed)

    def generate_transactions(self, count: int = 100) -> List[Dict[str, Any]]:
        """Generate heat exchanger transaction data"""
        transactions = []

        # Base operating conditions
        base_hot_temp = 400.0  # K
        base_cold_temp = 300.0  # K
        base_flow_rate = 10.0  # kg/s
        base_heat_coeff = 500.0  # W/m²K
        area = 50.0  # m²

        for i in range(count):
            # Add realistic variations and trends
            time_factor = i / count
            seasonal_variation = math.sin(2 * math.pi * time_factor) * 0.1

            # Hot side conditions
            hot_temp = base_hot_temp + np.random.normal(0, 10) + seasonal_variation * 20
            hot_flow = base_flow_rate + np.random.normal(0, 1) + seasonal_variation * 2

            # Cold side conditions
            cold_temp = (
                base_cold_temp + np.random.normal(0, 5) + seasonal_variation * 10
            )
            cold_flow = base_flow_rate + np.random.normal(0, 0.5)

            # Heat transfer coefficient (varies with flow)
            reynolds_factor = (hot_flow + cold_flow) / (2 * base_flow_rate)
            heat_coeff = base_heat_coeff * (reynolds_factor**0.8)

            # Calculate theoretical heat transfer
            delta_t = hot_temp - cold_temp
            theoretical_heat = heat_coeff * area * delta_t

            # Add measurement noise and efficiency losses
            actual_heat = theoretical_heat * (0.85 + np.random.normal(0, 0.05))

            # Energy balance calculations
            cp_hot = 4180.0  # J/kg·K (water)
            cp_cold = 4180.0

            hot_temp_out = hot_temp - actual_heat / (hot_flow * cp_hot)
            cold_temp_out = cold_temp + actual_heat / (cold_flow * cp_cold)

            # Introduce some physics violations (5% of data)
            physics_violation = random.random() < 0.05
            if physics_violation:
                # Violate energy conservation
                actual_heat *= random.uniform(1.2, 1.5)

            transaction = {
                "transaction_id": f"hx_txn_{i+1:04d}",
                "timestamp": datetime.now() + timedelta(minutes=i * 5),
                "features": {
                    "hot_inlet_temp": hot_temp,
                    "cold_inlet_temp": cold_temp,
                    "hot_flow_rate": hot_flow,
                    "cold_flow_rate": cold_flow,
                    "heat_transfer_coeff": heat_coeff,
                    "area": area,
                },
                "target": actual_heat,  # Heat transfer rate to predict
                "physics_parameters": {
                    "energy_input": hot_flow * cp_hot * hot_temp,
                    "energy_output": hot_flow * cp_hot * hot_temp_out
                    + cold_flow * cp_cold * cold_temp_out,
                    "energy_stored": 0.0,  # Steady state assumption
                    "hot_outlet_temp": hot_temp_out,
                    "cold_outlet_temp": cold_temp_out,
                },
                "context": {
                    "equipment": "shell_tube_heat_exchanger",
                    "data_type": "streaming",
                    "complexity": "medium",
                    "physics_violation": physics_violation,
                },
            }

            transactions.append(transaction)

        return transactions


class FluidFlowDataGenerator:
    """Generate realistic fluid flow system data"""

    def __init__(self, seed: int = 42):
        np.random.seed(seed)
        random.seed(seed)

    def generate_transactions(self, count: int = 100) -> List[Dict[str, Any]]:
        """Generate fluid flow transaction data"""
        transactions = []

        # Pipe system parameters
        pipe_diameter = 0.2  # m
        pipe_length = 100.0  # m
        pipe_roughness = 0.0001  # m
        fluid_density = 1000.0  # kg/m³
        fluid_viscosity = 0.001  # Pa·s
        g = 9.81  # m/s²

        for i in range(count):
            # Flow conditions with realistic variations
            velocity = 2.0 + np.random.normal(0, 0.3) + 0.5 * math.sin(i * 0.1)
            velocity = max(0.5, velocity)  # Minimum flow

            # Calculate Reynolds number
            reynolds = fluid_density * velocity * pipe_diameter / fluid_viscosity

            # Friction factor (Moody diagram approximation)
            if reynolds < 2300:  # Laminar
                friction_factor = 64 / reynolds
            else:  # Turbulent
                # Colebrook-White approximation
                friction_factor = 0.02 + 0.001 * np.random.normal(0, 0.1)

            # Pressure drop calculation
            pressure_drop = (
                friction_factor
                * (pipe_length / pipe_diameter)
                * (fluid_density * velocity**2 / 2)
            )

            # Pump head and power
            flow_rate = velocity * math.pi * (pipe_diameter / 2) ** 2
            pump_head = pressure_drop / (fluid_density * g) + 10.0  # 10m static head
            pump_efficiency = 0.75 + np.random.normal(0, 0.05)
            pump_power = (fluid_density * g * flow_rate * pump_head) / pump_efficiency

            # Introduce physics violations (3% of data)
            physics_violation = random.random() < 0.03
            if physics_violation:
                # Violate Bernoulli's equation
                pressure_drop *= random.uniform(0.5, 0.8)

            transaction = {
                "transaction_id": f"flow_txn_{i+1:04d}",
                "timestamp": datetime.now() + timedelta(minutes=i * 2),
                "features": {
                    "velocity": velocity,
                    "pipe_diameter": pipe_diameter,
                    "pipe_length": pipe_length,
                    "fluid_density": fluid_density,
                    "fluid_viscosity": fluid_viscosity,
                    "pipe_roughness": pipe_roughness,
                },
                "target": pressure_drop,  # Pressure drop to predict
                "physics_parameters": {
                    "reynolds_number": reynolds,
                    "friction_factor": friction_factor,
                    "flow_rate": flow_rate,
                    "pump_power": pump_power,
                    "pump_head": pump_head,
                    "pressure_1": 200000.0,  # Pa (upstream)
                    "pressure_2": 200000.0 - pressure_drop,  # Pa (downstream)
                    "velocity_1": velocity,
                    "velocity_2": velocity,  # Constant diameter
                    "height_1": 0.0,
                    "height_2": 0.0,  # Horizontal pipe
                    "density": fluid_density,
                },
                "context": {
                    "equipment": "centrifugal_pump_system",
                    "data_type": "streaming",
                    "complexity": "high",
                    "physics_violation": physics_violation,
                },
            }

            transactions.append(transaction)

        return transactions


class ManufacturingDataGenerator:
    """Generate realistic manufacturing process data"""

    def __init__(self, seed: int = 42):
        np.random.seed(seed)
        random.seed(seed)

    def generate_transactions(self, count: int = 100) -> List[Dict[str, Any]]:
        """Generate manufacturing transaction data"""
        transactions = []

        for i in range(count):
            # Production parameters
            production_rate = 100 + np.random.normal(0, 10)  # units/hour
            machine_speed = 1500 + np.random.normal(0, 50)  # RPM
            temperature = 180 + np.random.normal(0, 5)  # °C
            pressure = 5.0 + np.random.normal(0, 0.2)  # bar

            # Quality metrics
            defect_rate = max(0, 0.02 + np.random.normal(0, 0.005))  # 2% baseline

            # Energy consumption
            base_power = 50.0  # kW
            speed_power = (machine_speed / 1500) ** 2 * 30.0  # Speed-dependent power
            temp_power = max(0, (temperature - 150) * 0.5)  # Heating power
            total_power = base_power + speed_power + temp_power

            # Material balance
            raw_material_input = production_rate * 1.1  # 10% waste
            finished_product = production_rate * (1 - defect_rate)
            waste_output = raw_material_input - finished_product

            # Introduce violations (2% of data)
            physics_violation = random.random() < 0.02
            if physics_violation:
                # Violate mass conservation
                waste_output *= random.uniform(0.3, 0.7)

            transaction = {
                "transaction_id": f"mfg_txn_{i+1:04d}",
                "timestamp": datetime.now() + timedelta(minutes=i),
                "features": {
                    "machine_speed": machine_speed,
                    "temperature": temperature,
                    "pressure": pressure,
                    "raw_material_feed": raw_material_input,
                    "cycle_time": 3600 / production_rate,  # seconds per unit
                },
                "target": defect_rate,  # Quality metric to predict
                "physics_parameters": {
                    "energy_input": total_power,  # kW
                    "energy_output": total_power * 0.7,  # 70% efficiency
                    "energy_stored": total_power * 0.05,  # Thermal mass
                    "mass_flow_in": raw_material_input,
                    "mass_flow_out": finished_product + waste_output,
                    "production_rate": production_rate,
                    "efficiency": finished_product / raw_material_input,
                },
                "context": {
                    "equipment": "injection_molding_machine",
                    "data_type": "batch",
                    "complexity": "medium",
                    "physics_violation": physics_violation,
                },
            }

            transactions.append(transaction)

        return transactions


class FinancialDataGenerator:
    """Generate realistic financial transaction data"""

    def __init__(self, seed: int = 42):
        np.random.seed(seed)
        random.seed(seed)

    def generate_transactions(self, count: int = 100) -> List[Dict[str, Any]]:
        """Generate financial transaction data"""
        transactions = []

        # Market parameters
        base_volatility = 0.2
        risk_free_rate = 0.03

        for i in range(count):
            # Transaction characteristics
            amount = np.random.lognormal(8, 1.5)  # Log-normal distribution
            transaction_type = random.choice(["payment", "transfer", "investment"])

            # Risk factors
            credit_score = random.randint(300, 850)
            account_age = random.randint(1, 120)  # months
            transaction_frequency = random.randint(1, 50)  # per month

            # Market conditions
            market_volatility = base_volatility + np.random.normal(0, 0.05)
            interest_rate = risk_free_rate + np.random.normal(0, 0.01)

            # Fraud probability calculation
            fraud_score = 0.01  # Base 1% fraud rate

            # Risk factors
            if amount > 10000:
                fraud_score += 0.02
            if credit_score < 600:
                fraud_score += 0.03
            if transaction_frequency > 30:
                fraud_score += 0.01

            fraud_score = min(0.95, fraud_score)  # Cap at 95%

            # Actual fraud (for testing)
            is_fraud = random.random() < fraud_score

            transaction = {
                "transaction_id": f"fin_txn_{i+1:04d}",
                "timestamp": datetime.now() + timedelta(seconds=i * 30),
                "features": {
                    "amount": amount,
                    "credit_score": credit_score,
                    "account_age": account_age,
                    "transaction_frequency": transaction_frequency,
                    "market_volatility": market_volatility,
                    "interest_rate": interest_rate,
                    "transaction_type": transaction_type,
                },
                "target": 1.0 if is_fraud else 0.0,  # Fraud detection
                "physics_parameters": {
                    # Financial "physics" - conservation of money
                    "account_balance_before": 10000 + np.random.normal(0, 5000),
                    "transaction_amount": (
                        amount if transaction_type != "payment" else -amount
                    ),
                    "fees": amount * 0.01 if transaction_type == "transfer" else 0,
                    "interest_earned": 0.0,  # Simplified
                },
                "context": {
                    "equipment": "payment_processor",
                    "data_type": "streaming",
                    "complexity": "low",
                    "physics_violation": False,  # Financial conservation always holds
                },
            }

            # Calculate balance after
            balance_before = transaction["physics_parameters"]["account_balance_before"]
            transaction_amt = transaction["physics_parameters"]["transaction_amount"]
            fees = transaction["physics_parameters"]["fees"]

            transaction["physics_parameters"]["account_balance_after"] = (
                balance_before + transaction_amt - fees
            )

            transactions.append(transaction)

        return transactions


class IoTSensorDataGenerator:
    """Generate realistic IoT sensor network data"""

    def __init__(self, seed: int = 42):
        np.random.seed(seed)
        random.seed(seed)

    def generate_transactions(self, count: int = 100) -> List[Dict[str, Any]]:
        """Generate IoT sensor transaction data"""
        transactions = []

        # Sensor network parameters
        num_sensors = 50
        base_temp = 25.0  # °C
        base_humidity = 50.0  # %
        base_pressure = 1013.25  # hPa

        for i in range(count):
            # Select random sensor
            sensor_id = random.randint(1, num_sensors)

            # Environmental conditions with correlations
            time_of_day = (i % 24) / 24.0  # Simulate daily cycle
            daily_temp_variation = 10 * math.sin(2 * math.pi * time_of_day)

            temperature = base_temp + daily_temp_variation + np.random.normal(0, 2)

            # Humidity inversely correlated with temperature
            humidity = (
                base_humidity - (temperature - base_temp) * 1.5 + np.random.normal(0, 5)
            )
            humidity = max(10, min(90, humidity))  # Physical limits

            # Pressure with weather patterns
            pressure = base_pressure + np.random.normal(0, 10) + math.sin(i * 0.05) * 20

            # Battery level (decreasing over time)
            battery_level = 100 - (i / count) * 80 + np.random.normal(0, 5)
            battery_level = max(5, battery_level)

            # Signal strength (distance and interference effects)
            base_signal = -60  # dBm
            distance_factor = random.uniform(0.8, 1.2)
            interference = np.random.normal(0, 5)
            signal_strength = base_signal * distance_factor + interference

            # Anomaly detection target
            # Anomalies: extreme values, sensor failures, network issues
            is_anomaly = False

            # Temperature anomaly
            if abs(temperature - (base_temp + daily_temp_variation)) > 15:
                is_anomaly = True

            # Battery failure
            if battery_level < 10:
                is_anomaly = True

            # Signal loss
            if signal_strength < -90:
                is_anomaly = True

            # Random sensor failures (1% rate)
            if random.random() < 0.01:
                is_anomaly = True
                temperature = np.random.uniform(-50, 100)  # Sensor malfunction

            transaction = {
                "transaction_id": f"iot_txn_{i+1:04d}",
                "timestamp": datetime.now() + timedelta(seconds=i * 10),
                "features": {
                    "sensor_id": sensor_id,
                    "temperature": temperature,
                    "humidity": humidity,
                    "pressure": pressure,
                    "battery_level": battery_level,
                    "signal_strength": signal_strength,
                    "time_of_day": time_of_day,
                },
                "target": 1.0 if is_anomaly else 0.0,  # Anomaly detection
                "physics_parameters": {
                    # Thermodynamic relationships
                    "absolute_temperature": temperature + 273.15,  # Kelvin
                    "vapor_pressure": 6.112
                    * math.exp(17.67 * temperature / (temperature + 243.5)),
                    "relative_humidity": humidity,
                    "atmospheric_pressure": pressure,
                    "dew_point": temperature - ((100 - humidity) / 5.0),
                },
                "context": {
                    "equipment": "wireless_sensor_network",
                    "data_type": "streaming",
                    "complexity": "low",
                    "physics_violation": False,  # Thermodynamic relationships hold
                },
            }

            transactions.append(transaction)

        return transactions


def create_test_datasets() -> List[TestDataset]:
    """Create comprehensive test datasets for all domains"""

    datasets = []

    # Heat Exchanger Dataset
    hx_generator = HeatExchangerDataGenerator(seed=42)
    hx_transactions = hx_generator.generate_transactions(200)
    hx_violations = sum(1 for t in hx_transactions if t["context"]["physics_violation"])

    datasets.append(
        TestDataset(
            name="heat_exchanger_operations",
            domain="thermal_engineering",
            transactions=hx_transactions,
            expected_physics_violations=hx_violations,
            expected_model_count=200,
            description="Heat exchanger operations with energy balance validation",
        )
    )

    # Fluid Flow Dataset
    flow_generator = FluidFlowDataGenerator(seed=43)
    flow_transactions = flow_generator.generate_transactions(150)
    flow_violations = sum(
        1 for t in flow_transactions if t["context"]["physics_violation"]
    )

    datasets.append(
        TestDataset(
            name="fluid_flow_systems",
            domain="fluid_mechanics",
            transactions=flow_transactions,
            expected_physics_violations=flow_violations,
            expected_model_count=150,
            description="Fluid flow systems with Bernoulli equation validation",
        )
    )

    # Manufacturing Dataset
    mfg_generator = ManufacturingDataGenerator(seed=44)
    mfg_transactions = mfg_generator.generate_transactions(100)
    mfg_violations = sum(
        1 for t in mfg_transactions if t["context"]["physics_violation"]
    )

    datasets.append(
        TestDataset(
            name="manufacturing_processes",
            domain="industrial_engineering",
            transactions=mfg_transactions,
            expected_physics_violations=mfg_violations,
            expected_model_count=100,
            description="Manufacturing processes with mass/energy conservation",
        )
    )

    # Financial Dataset
    fin_generator = FinancialDataGenerator(seed=45)
    fin_transactions = fin_generator.generate_transactions(300)

    datasets.append(
        TestDataset(
            name="financial_transactions",
            domain="fintech",
            transactions=fin_transactions,
            expected_physics_violations=0,  # Financial conservation always holds
            expected_model_count=300,
            description="Financial transactions with money conservation laws",
        )
    )

    # IoT Sensor Dataset
    iot_generator = IoTSensorDataGenerator(seed=46)
    iot_transactions = iot_generator.generate_transactions(250)

    datasets.append(
        TestDataset(
            name="iot_sensor_network",
            domain="sensor_networks",
            transactions=iot_transactions,
            expected_physics_violations=0,  # Thermodynamic relationships hold
            expected_model_count=250,
            description="IoT sensor network with thermodynamic validation",
        )
    )

    return datasets


def save_datasets_to_files(datasets: List[TestDataset], output_dir: str = "test_data"):
    """Save datasets to JSON files for testing"""
    import json
    import os

    os.makedirs(output_dir, exist_ok=True)

    for dataset in datasets:
        filename = f"{output_dir}/{dataset.name}.json"

        # Convert datetime objects to strings for JSON serialization
        serializable_transactions = []
        for transaction in dataset.transactions:
            serializable_transaction = transaction.copy()
            if isinstance(serializable_transaction["timestamp"], datetime):
                serializable_transaction["timestamp"] = serializable_transaction[
                    "timestamp"
                ].isoformat()
            serializable_transactions.append(serializable_transaction)

        dataset_dict = {
            "name": dataset.name,
            "domain": dataset.domain,
            "description": dataset.description,
            "expected_physics_violations": dataset.expected_physics_violations,
            "expected_model_count": dataset.expected_model_count,
            "transaction_count": len(dataset.transactions),
            "transactions": serializable_transactions,
        }

        with open(filename, "w") as f:
            json.dump(dataset_dict, f, indent=2)

        print(f"Saved {len(dataset.transactions)} transactions to {filename}")


if __name__ == "__main__":
    # Generate and save test datasets
    print("Generating realistic test datasets...")

    datasets = create_test_datasets()

    print(f"\nGenerated {len(datasets)} datasets:")
    for dataset in datasets:
        print(
            f"- {dataset.name}: {len(dataset.transactions)} transactions, "
            f"{dataset.expected_physics_violations} expected violations"
        )

    # Save to files
    save_datasets_to_files(datasets)

    print(
        f"\nTotal transactions across all datasets: {sum(len(d.transactions) for d in datasets)}"
    )
    print("Test datasets ready for end-to-end testing!")
