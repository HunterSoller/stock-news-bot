#!/usr/bin/env python3
"""
Telegram Configuration Test Script
Use this to test and debug your Telegram bot setup
"""

import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_telegram_config():
    """Test Telegram bot configuration"""
    print("🤖 Testing Telegram Bot Configuration")
    print("=" * 50)
    
    # Get configuration
    TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "").strip()
    TG_CHAT_ID = os.getenv("TG_CHAT_ID", "").strip()
    
    print(f"Bot Token: {TG_BOT_TOKEN[:10]}...{TG_BOT_TOKEN[-10:] if len(TG_BOT_TOKEN) > 20 else 'INVALID'}")
    print(f"Chat ID: {TG_CHAT_ID}")
    print()
    
    # Validate token format
    if not TG_BOT_TOKEN:
        print("❌ ERROR: TG_BOT_TOKEN is not set")
        return False
    
    if ':' not in TG_BOT_TOKEN:
        print("❌ ERROR: TG_BOT_TOKEN format is invalid (should be 'bot_id:token')")
        return False
    
    if not TG_CHAT_ID:
        print("❌ ERROR: TG_CHAT_ID is not set")
        return False
    
    if not TG_CHAT_ID.isdigit():
        print("❌ ERROR: TG_CHAT_ID should be numeric")
        return False
    
    print("✅ Configuration format looks correct")
    
    # Test bot info
    print("\n🔍 Testing bot information...")
    bot_info_url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/getMe"
    
    try:
        response = requests.get(bot_info_url, timeout=10)
        if response.status_code == 401:
            print("❌ ERROR: Bot token is invalid or unauthorized")
            print("   Make sure you copied the token correctly from @BotFather")
            return False
        elif response.status_code == 200:
            bot_data = response.json()
            if bot_data.get('ok'):
                bot_info = bot_data['result']
                print(f"✅ Bot found: @{bot_info['username']} ({bot_info['first_name']})")
            else:
                print("❌ ERROR: Bot API returned error")
                return False
        else:
            print(f"❌ ERROR: Unexpected response code {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ ERROR: Failed to test bot info: {e}")
        return False
    
    # Test sending message
    print("\n📤 Testing message sending...")
    send_url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    
    test_message = "🧪 Test message from Stock News Bot setup script"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": test_message
    }
    
    try:
        response = requests.post(send_url, json=payload, timeout=10)
        
        if response.status_code == 401:
            print("❌ ERROR: Bot token is invalid")
            return False
        elif response.status_code == 400:
            print("❌ ERROR: Chat ID is invalid or bot hasn't been started")
            print("   Make sure you've sent /start to your bot in Telegram")
            return False
        elif response.status_code == 200:
            print("✅ Test message sent successfully!")
            print("   Check your Telegram - you should have received the test message")
            return True
        else:
            print(f"❌ ERROR: Unexpected response code {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: Failed to send test message: {e}")
        return False

def main():
    print("🚀 Telegram Bot Configuration Test")
    print("This script will test your Telegram bot setup\n")
    
    success = test_telegram_config()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 SUCCESS: Your Telegram bot is configured correctly!")
        print("   You can now run the main bot: python bot.py")
    else:
        print("❌ FAILED: Please fix the issues above")
        print("   Check the TELEGRAM_SETUP.md file for detailed instructions")
    
    print("\n📚 For help, see: TELEGRAM_SETUP.md")

if __name__ == "__main__":
    main()

