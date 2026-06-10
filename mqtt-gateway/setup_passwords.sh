#!/bin/bash

# TML MQTT Gateway - Password Setup Script
# Creates password file for Mosquitto MQTT broker

echo "🔐 Setting up MQTT broker passwords..."

# Create password file
PASSWD_FILE="mosquitto/config/passwd"

# Remove existing password file
rm -f $PASSWD_FILE

# Add users with passwords
echo "Creating MQTT users..."

# Admin user
docker run --rm -v $(pwd)/mosquitto/config:/mosquitto/config eclipse-mosquitto:2.0.18 \
    mosquitto_passwd -c /mosquitto/config/passwd tml_admin
echo "tml_secure_2026" | docker run --rm -i -v $(pwd)/mosquitto/config:/mosquitto/config eclipse-mosquitto:2.0.18 \
    mosquitto_passwd -b /mosquitto/config/passwd tml_admin tml_secure_2026

# Gateway user
echo "tml_gateway_2026" | docker run --rm -i -v $(pwd)/mosquitto/config:/mosquitto/config eclipse-mosquitto:2.0.18 \
    mosquitto_passwd -b /mosquitto/config/passwd tml_gateway tml_gateway_2026

# Test device users
echo "device_pass_001" | docker run --rm -i -v $(pwd)/mosquitto/config:/mosquitto/config eclipse-mosquitto:2.0.18 \
    mosquitto_passwd -b /mosquitto/config/passwd temp_sensor_001 device_pass_001

echo "device_pass_002" | docker run --rm -i -v $(pwd)/mosquitto/config:/mosquitto/config eclipse-mosquitto:2.0.18 \
    mosquitto_passwd -b /mosquitto/config/passwd camera_001 device_pass_002

echo "device_pass_003" | docker run --rm -i -v $(pwd)/mosquitto/config:/mosquitto/config eclipse-mosquitto:2.0.18 \
    mosquitto_passwd -b /mosquitto/config/passwd valve_001 device_pass_003

echo "✅ MQTT passwords configured successfully"
echo "📋 Users created:"
echo "   - tml_admin (admin access)"
echo "   - tml_gateway (gateway access)"
echo "   - temp_sensor_001 (device access)"
echo "   - camera_001 (device access)"
echo "   - valve_001 (device access)"
