# Telegram Bot Setup Guide

## 🤖 **Step 1: Create a Telegram Bot**

1. **Open Telegram** and search for `@BotFather`
2. **Start a chat** with BotFather
3. **Send command**: `/newbot`
4. **Enter bot name**: `Stock News Bot` (or any name you prefer)
5. **Enter bot username**: `your_stock_news_bot` (must end with 'bot')
6. **Copy the bot token** - it looks like: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`

## 💬 **Step 2: Get Your Chat ID**

### Method 1: Using @userinfobot
1. **Search for** `@userinfobot` in Telegram
2. **Start a chat** and send `/start`
3. **Copy your user ID** (it's a number like `123456789`)

### Method 2: Using @getidsbot
1. **Search for** `@getidsbot` in Telegram
2. **Start a chat** and send `/start`
3. **Copy your user ID**

### Method 3: Using your bot
1. **Start a chat** with your bot
2. **Send any message** to your bot
3. **Visit**: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
4. **Look for** `"chat":{"id":123456789}` in the response

## ⚙️ **Step 3: Configure Environment Variables**

Create a `.env` file in your project directory:

```bash
# OpenAI API Configuration
OPENAI_API_KEY=your_openai_api_key_here

# Telegram Bot Configuration
TG_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TG_CHAT_ID=123456789
```

**Replace the values with your actual:**
- `TG_BOT_TOKEN`: The token from BotFather
- `TG_CHAT_ID`: Your user ID from step 2

## 🧪 **Step 4: Test Your Configuration**

Run the command handler to test:

```bash
python command_handler.py
```

Type `test` to send a test message.

## 🔍 **Common Issues & Solutions**

### **401 Unauthorized Error**
- **Cause**: Invalid bot token
- **Solution**: Double-check your `TG_BOT_TOKEN` in `.env`
- **Format**: Should be `bot_id:token` (numbers:letters)

### **400 Bad Request Error**
- **Cause**: Invalid chat ID
- **Solution**: Double-check your `TG_CHAT_ID` in `.env`
- **Format**: Should be a number (like `123456789`)

### **Bot Not Responding**
- **Cause**: Bot hasn't been started
- **Solution**: Send `/start` to your bot in Telegram first

### **Message Not Delivered**
- **Cause**: Chat ID is wrong or bot is blocked
- **Solution**: Make sure you've started a chat with your bot

## 📝 **Example .env File**

```bash
# Copy this template and fill in your actual values
OPENAI_API_KEY=sk-1234567890abcdef...
TG_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TG_CHAT_ID=123456789
```

## ✅ **Verification Steps**

1. **Check bot token format**: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`
2. **Check chat ID format**: `123456789` (just numbers)
3. **Test with command handler**: `python command_handler.py`
4. **Send test message**: Type `test` in command handler
5. **Check Telegram**: You should receive the test message

## 🆘 **Still Having Issues?**

1. **Verify bot token**: Visit `https://api.telegram.org/bot<YOUR_TOKEN>/getMe`
2. **Verify chat ID**: Visit `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
3. **Check .env file**: Make sure there are no extra spaces or quotes
4. **Restart bot**: Stop and restart `python bot.py`

