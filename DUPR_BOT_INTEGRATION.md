# DUPR Bot MCP Integration Example

## How to integrate DUPR Bot into your existing MCP server

### 1. Add to your MCP server imports:
```python
from dupr_bot_mcp import (
    process_message, 
    initialize_bot, 
    is_dupr_message,
    get_dupr_status,
    handle_dupr_command
)
```

### 2. Initialize the bot in your server startup:
```python
def start_server():
    # Your existing initialization...
    
    # Initialize DUPR bot
    if initialize_bot():
        print("✅ DUPR Bot initialized")
    else:
        print("❌ DUPR Bot failed to initialize")
    
    # Rest of your server startup...
```

### 3. Add to your message handler:
```python
def handle_incoming_message(message_text: str, sender: str):
    """Handle incoming messages"""
    
    # Check if it's a DUPR bot command
    if is_dupr_message(message_text):
        response = process_message(message_text)
        if response:
            # Send response back to sender
            send_message_to_sender(sender, response)
            return True  # Message was handled
    
    # Your existing message handling logic...
    return False  # Message not handled by DUPR bot
```

### 4. Available DUPR Bot Commands:

Users can send these commands via iMessage:

- `DUPRBOT status` - Get current DUPR scores and monitoring status
- `DUPRBOT start` - Start DUPR monitoring
- `DUPRBOT stop` - Stop DUPR monitoring  
- `DUPRBOT pause` - Pause monitoring
- `DUPRBOT resume` - Resume monitoring
- `DUPRBOT target 11.5` - Show target change info
- `DUPRBOT estimate` - Show rating estimates
- `DUPRBOT help` - Show all commands

### 5. Example Usage:

User sends: `DUPRBOT status`

Bot responds:
```
🏓 DUPR Bot Status

Current Scores:
  Trevor: 4.049
  Jared: 3.757
  Jon: 3.891

Combined: 11.697
Target: 11.3
Gap: +0.397 (still over)

Monitoring: Stopped
Last Check: Never

Type 'DUPRBOT help' for commands.
```

### 6. Environment Variables Needed:

Add to your `.env` file:
```bash
DUPR_USERNAME=your_email@example.com
DUPR_PASSWORD=your_password
```

### 7. Integration Benefits:

- ✅ **Easy Integration**: Just add a few lines to existing MCP server
- ✅ **Keyword-based**: Uses "DUPRBOT" keyword for easy recognition
- ✅ **iMessage Compatible**: Works with your existing poke.com setup
- ✅ **Command Interface**: Terminal-like commands via text
- ✅ **Real-time Status**: Get current DUPR scores anytime
- ✅ **Control Interface**: Start/stop/pause monitoring remotely

### 8. Advanced Integration (Optional):

You can also add periodic status updates:

```python
def send_periodic_updates():
    """Send periodic DUPR updates to subscribed users"""
    if monitor_running and not monitor_paused:
        status = get_dupr_status()
        if status.get('gap', 0) <= 0:  # Target reached!
            message = f"🎯 TARGET REACHED! Combined: {status['total_sum']:.3f}"
            send_to_subscribers(message)
```

This gives you a complete DUPR monitoring and control system integrated into your existing iMessage/poke.com workflow! 🎯
