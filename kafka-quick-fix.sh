#!/bin/bash

echo "🔧 Quick Kafka Fix - Resolving Message Size Issues"
echo "=================================================="
echo ""

echo "❗ Issue detected: Kafka is receiving oversized messages"
echo "   Current max: 100MB"
echo "   Attempting to receive: 1.1GB+"
echo ""

# Update Kafka configuration to handle larger messages
echo "📝 Updating Kafka configuration..."

# Create a fixed configuration
docker exec tml-kafka-1 bash -c "cat >> /etc/kafka/server.properties << 'EOF'

# Increase message size limits
message.max.bytes=1073741824
replica.fetch.max.bytes=1073741824
socket.request.max.bytes=1073741824
socket.send.buffer.bytes=1073741824
socket.receive.buffer.bytes=1073741824
EOF"

echo "🔄 Restarting Kafka with new configuration..."
docker restart tml-kafka-1

echo "⏳ Waiting for Kafka to restart (30 seconds)..."
sleep 30

# Verify Kafka is working
echo ""
echo "🔍 Verifying Kafka status..."
if docker exec tml-kafka-1 kafka-topics --bootstrap-server localhost:9092 --list > /dev/null 2>&1; then
    echo "✅ Kafka is responding!"
else
    echo "⚠️  Kafka may still be starting. Wait a bit longer."
fi

# Create TML topics
echo ""
echo "📋 Creating TML topics..."
docker exec tml-kafka-1 kafka-topics --bootstrap-server localhost:9092 --create --topic tml-transactions --partitions 10 --replication-factor 1 2>/dev/null || echo "   Topic tml-transactions already exists"
docker exec tml-kafka-1 kafka-topics --bootstrap-server localhost:9092 --create --topic tml-models --partitions 5 --replication-factor 1 2>/dev/null || echo "   Topic tml-models already exists"
docker exec tml-kafka-1 kafka-topics --bootstrap-server localhost:9092 --create --topic tml-predictions --partitions 10 --replication-factor 1 2>/dev/null || echo "   Topic tml-predictions already exists"

echo ""
echo "📊 Current Kafka topics:"
docker exec tml-kafka-1 kafka-topics --bootstrap-server localhost:9092 --list

echo ""
echo "✅ Kafka configuration updated!"
echo ""
echo "💡 If you're still having issues, try:"
echo "   1. Clear the problematic producer: docker restart <producer-container>"
echo "   2. Use smaller batch sizes in your application"
echo "   3. Check producer configuration for 'max.request.size'"
echo ""
echo "📝 To prevent this in the future, configure producers with:"
echo "   max.request.size=104857600  # 100MB"
echo "   batch.size=16384"
echo "   linger.ms=10"
