#!/usr/bin/env python3
"""
Command handler for the Stock News Bot
Run this in a separate terminal to interact with the bot
"""

import requests
import json
import time
from datetime import datetime

# Configuration - make sure these match your bot.py settings
TG_BOT_TOKEN = "your_telegram_bot_token_here"  # Replace with your actual token
TG_CHAT_ID = "your_telegram_chat_id_here"      # Replace with your actual chat ID

def send_telegram_message(message: str) -> bool:
    """Send message to Telegram"""
    if not TG_BOT_TOKEN or TG_BOT_TOKEN == "your_telegram_bot_token_here":
        print("[ERROR] Please configure your Telegram credentials in this script")
        return False
        
    TG_API_URL = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    try:
        response = requests.post(TG_API_URL, json=payload, timeout=10)
        response.raise_for_status()
        print(f"[TELEGRAM] Message sent successfully")
        return True
    except Exception as e:
        print(f"[ERROR] Telegram send failed: {e}")
        return False

def manual_report():
    """Send a manual test report to Telegram"""
    test_message = f"""📈 *Manual Trading Alert Test*

This is a test message from your Stock News Bot.

*Test Event 1:*
🟢 **BULLISH** $AAPL
Apple reports strong Q4 earnings beat
Confidence: 85%
Reasons: Revenue growth, iPhone sales surge, Services expansion

*Test Event 2:*
🔴 **BEARISH** $TSLA  
Tesla warns of production delays
Confidence: 75%
Reasons: Supply chain issues, delivery delays, competition concerns

_Manual report generated at {datetime.now().strftime('%H:%M:%S')}_"""

    print("[MANUAL] Sending test report to Telegram...")
    if send_telegram_message(test_message):
        print("[SUCCESS] Test report sent!")
    else:
        print("[FAILED] Could not send test report")

def main():
    print("🤖 Stock News Bot Command Handler")
    print("=" * 40)
    print("Commands:")
    print("  'test' - Send test message to Telegram")
    print("  'quit' - Exit")
    print()
    
    while True:
        try:
            command = input("Enter command: ").strip().lower()
            
            if command == 'test':
                manual_report()
            elif command == 'quit':
                print("Goodbye!")
                break
            elif command == '':
                continue
            else:
                print(f"Unknown command: '{command}'. Available: test, quit")
                
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    main()

