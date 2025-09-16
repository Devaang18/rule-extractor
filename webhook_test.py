#!/usr/bin/env python3
"""
Simple webhook receiver for testing Rule Extractor API
Run this, then use the ngrok URL as your webhook_url in Bruno
"""

from flask import Flask, request, jsonify
import json
from datetime import datetime

app = Flask(__name__)

@app.route('/', methods=['POST'])
def webhook_receiver():
    """Receive and display webhook notifications"""
    try:
        # Get headers
        headers = dict(request.headers)
        
        # Get JSON payload
        payload = request.get_json()
        
        # Print formatted webhook info
        print("\n" + "="*50)
        print(f"🎯 WEBHOOK RECEIVED: {datetime.now().strftime('%H:%M:%S')}")
        print("="*50)
        
        # Print important headers
        event_type = headers.get('X-Event', 'unknown')
        job_id = headers.get('X-Job-Process-Id', 'unknown')
        
        print(f"📋 Event Type: {event_type}")
        print(f"🆔 Job ID: {job_id}")
        print(f"📊 Status: {payload.get('status', 'unknown')}")
        
        if payload.get('status') == 'success':
            rules_count = len(payload.get('rules', []))
            print(f"✅ SUCCESS: {rules_count} rules extracted")
            
            # Show first rule as example
            if rules_count > 0:
                first_rule = payload['rules'][0]
                print(f"📝 First Rule: {first_rule.get('rule_text', '')[:100]}...")
                print(f"🏷️  Category: {first_rule.get('category', 'unknown')}")
        
        elif payload.get('status') == 'failure':
            print(f"❌ FAILURE: {payload.get('error', 'unknown error')}")
        
        elif payload.get('status') == 'processing':
            print(f"⏳ PROCESSING: {payload.get('message', 'Job started')}")
        
        print("\n📦 Full Payload:")
        print(json.dumps(payload, indent=2))
        print("="*50 + "\n")
        
        return jsonify({"received": True}), 200
        
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("🚀 Starting Webhook Test Server...")
    print("📡 Listening for webhooks on http://localhost:5000")
    print("💡 Use ngrok to expose this for testing!")
    app.run(host='0.0.0.0', port=5000, debug=True)
