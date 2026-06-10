#!/usr/bin/env python3
"""
Live Transaction Generator for TML Dashboard
Continuously sends realistic transaction data to Kafka for dashboard demonstration
"""

import json
from kafka import KafkaProducer
import time
import random
import uuid
import sys
from datetime import datetime

def generate_transaction():
    """Generate a realistic transaction"""
    
    # Transaction types with different probability distributions
    transaction_types = {
        'purchase': {'weight': 0.6, 'amount_range': (10, 300)},
        'transfer': {'weight': 0.25, 'amount_range': (50, 1000)},
        'refund': {'weight': 0.10, 'amount_range': (15, 200)},
        'subscription': {'weight': 0.05, 'amount_range': (5, 50)}
    }
    
    # Select transaction type based on weights
    transaction_type = random.choices(
        list(transaction_types.keys()),
        weights=[t['weight'] for t in transaction_types.values()]
    )[0]
    
    # Generate amount based on type
    amount_range = transaction_types[transaction_type]['amount_range']
    amount = round(random.uniform(*amount_range), 2)
    
    # Status distribution
    status_weights = {'completed': 0.8, 'pending': 0.15, 'processing': 0.05}
    status = random.choices(
        list(status_weights.keys()),
        weights=list(status_weights.values())
    )[0]
    
    # Generate realistic user patterns
    user_id = f"user_{random.randint(1000, 9999)}"
    
    # Add some realistic metadata
    sources = ['web_app', 'mobile_app', 'api', 'pos_terminal']
    source = random.choice(sources)
    
    # Geographic regions for spatial analysis
    regions = ['US-East', 'US-West', 'EU', 'Asia-Pacific', 'Canada']
    region = random.choice(regions)
    
    return {
        'transaction_id': f'tx_{uuid.uuid4().hex[:8]}',
        'amount': amount,
        'status': status,
        'timestamp': time.time(),
        'user_id': user_id,
        'type': transaction_type,
        'source': source,
        'region': region,
        'currency': 'USD',
        'metadata': {
            'session_id': f'sess_{uuid.uuid4().hex[:12]}',
            'device_type': random.choice(['desktop', 'mobile', 'tablet']),
            'risk_score': round(random.uniform(0.1, 0.9), 3)
        }
    }

def main():
    """Main transaction generator"""
    
    print("🔄 TML Live Transaction Generator")
    print("="*50)
    
    try:
        # Create Kafka producer
        producer = KafkaProducer(
            bootstrap_servers=['localhost:29092'],
            value_serializer=lambda x: json.dumps(x).encode('utf-8'),
            batch_size=1,  # Send immediately
            linger_ms=0    # No delay
        )
        
        print("✅ Connected to Kafka")
        print("📊 Generating live transactions...")
        print("🎯 Topic: tml-transactions")
        print("⏹️  Press Ctrl+C to stop")
        print("="*50)
        
        transaction_count = 0
        
        while True:
            # Generate and send transaction
            transaction = generate_transaction()
            
            producer.send('tml-transactions', transaction)
            transaction_count += 1
            
            # Display transaction info
            timestamp = datetime.now().strftime('%H:%M:%S')
            print(f"[{timestamp}] #{transaction_count:4d} | "
                  f"{transaction['transaction_id']} | "
                  f"${transaction['amount']:7.2f} | "
                  f"{transaction['status']:10s} | "
                  f"{transaction['type']}")
            
            # Flush every 5 transactions
            if transaction_count % 5 == 0:
                producer.flush()
            
            # Variable delay to simulate realistic patterns
            # Higher frequency during "business hours"
            current_hour = datetime.now().hour
            if 9 <= current_hour <= 17:  # Business hours
                delay = random.uniform(0.5, 2.0)
            else:  # Off hours
                delay = random.uniform(2.0, 5.0)
            
            time.sleep(delay)
            
    except KeyboardInterrupt:
        print(f"\n🛑 Stopping transaction generator...")
        print(f"📊 Generated {transaction_count} transactions")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    
    finally:
        try:
            producer.flush()
            producer.close()
            print("✅ Kafka producer closed")
        except:
            pass
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
