#!/usr/bin/env python3
"""
DUPR Bot MCP Server
MCP server that integrates DUPR monitoring with iMessage/poke.com
Use keyword "DUPRBOT" to interact with the DUPR monitoring system
"""

import os
import json
import time
import threading
from datetime import datetime
from typing import Dict, List, Optional, Any
from loguru import logger
from dotenv import load_dotenv

from dupr_client import DuprClient

# Load environment variables
load_dotenv()

# Configuration
PLAYERS = {
    "Trevor": {
        "dupr_id": "6552489258",
        "short_id": "PKQX0G",
        "email": "trevor.jin@gmail.com",
        "color": "#FF6B6B"
    },
    "Jared": {
        "dupr_id": "4847895806",
        "short_id": "W6YQXG",
        "email": "jaredfuelberth@gmail.com",
        "color": "#4ECDC4"
    },
    "Jon": {
        "dupr_id": "4405492894",
        "short_id": "0YVNWN",
        "email": "pbislife@jonchui.com",
        "color": "#45B7D1"
    }
}

TARGET_SUM = 11.3
MATCH_TO_TRACK = "QPENOLOGN"
BOT_KEYWORD = "DUPRBOT"

# Global state
dupr_client = None
current_scores = {}
score_history = []
monitor_running = False
monitor_paused = False
last_check_time = None


class DuprBotMCP:
    """MCP server for DUPR bot integration"""
    
    def __init__(self):
        self.dupr_client = DuprClient()
        self.authenticated = False
        
        # Setup logging
        logger.add("dupr_bot_mcp.log", rotation="1 day", retention="7 days")
    
    def authenticate(self) -> bool:
        """Authenticate with DUPR API"""
        try:
            username = os.getenv("DUPR_USERNAME")
            password = os.getenv("DUPR_PASSWORD")
            
            if not username or not password:
                logger.error("DUPR_USERNAME and DUPR_PASSWORD must be set in .env file")
                return False
                
            rc = self.dupr_client.auth_user(username, password)
            if rc == 0:
                self.authenticated = True
                logger.info("Successfully authenticated with DUPR API")
                return True
            else:
                logger.error(f"Failed to authenticate with DUPR API: {rc}")
                return False
                
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return False
    
    def get_player_rating(self, dupr_id: str) -> Optional[float]:
        """Get current doubles rating for a player"""
        try:
            rc, player_data = self.dupr_client.get_player(dupr_id)
            if rc == 200 and player_data:
                ratings = player_data.get("ratings", {})
                doubles_rating = ratings.get("doubles")
                
                if doubles_rating and doubles_rating != "NR":
                    return float(doubles_rating)
                else:
                    logger.warning(f"No doubles rating found for {dupr_id}")
                    return None
            else:
                logger.error(f"Failed to get player data for {dupr_id}: {rc}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting rating for {dupr_id}: {e}")
            return None
    
    def get_current_status(self) -> Dict[str, Any]:
        """Get current DUPR status"""
        if not self.authenticated:
            return {"error": "Not authenticated with DUPR API"}
        
        current_scores = {}
        total_sum = 0
        
        for name, player_info in PLAYERS.items():
            dupr_id = player_info["dupr_id"]
            rating = self.get_player_rating(dupr_id)
            
            if rating is not None:
                current_scores[name] = rating
                total_sum += rating
        
        gap = total_sum - TARGET_SUM
        progress_percent = max(0, min(100, (TARGET_SUM / total_sum) * 100)) if total_sum > 0 else 0
        
        return {
            "scores": current_scores,
            "total_sum": total_sum,
            "target_sum": TARGET_SUM,
            "gap": gap,
            "progress_percent": progress_percent,
            "monitor_running": monitor_running,
            "monitor_paused": monitor_paused,
            "last_check": last_check_time,
            "timestamp": datetime.now().isoformat()
        }
    
    def process_command(self, command: str) -> str:
        """Process DUPR bot command"""
        try:
            parts = command.lower().strip().split()
            if not parts:
                return self._get_help()
            
            cmd = parts[0]
            args = parts[1:] if len(parts) > 1 else []
            
            if cmd == "status":
                return self._handle_status()
            elif cmd == "start":
                return self._handle_start()
            elif cmd == "stop":
                return self._handle_stop()
            elif cmd == "pause":
                return self._handle_pause()
            elif cmd == "resume":
                return self._handle_resume()
            elif cmd == "target":
                return self._handle_target(args)
            elif cmd == "estimate":
                return self._handle_estimate()
            elif cmd == "help":
                return self._get_help()
            else:
                return f"Unknown command: {cmd}. Type '{BOT_KEYWORD} help' for available commands."
                
        except Exception as e:
            logger.error(f"Error processing command {command}: {e}")
            return f"Error processing command: {e}"
    
    def _handle_status(self) -> str:
        """Handle status command"""
        status = self.get_current_status()
        if "error" in status:
            return f"❌ {status['error']}"
        
        scores_text = "\n".join([f"  {name}: {score:.3f}" for name, score in status["scores"].items()])
        
        return f"""🏓 DUPR Bot Status

Current Scores:
{scores_text}

Combined: {status['total_sum']:.3f}
Target: {status['target_sum']}
Gap: {status['gap']:+.3f} {'(UNDER TARGET!)' if status['gap'] <= 0 else '(still over)'}

Monitoring: {'Paused' if status['monitor_paused'] else ('Running' if status['monitor_running'] else 'Stopped')}
Last Check: {status['last_check'] or 'Never'}

Type '{BOT_KEYWORD} help' for commands."""
    
    def _handle_start(self) -> str:
        """Handle start command"""
        global monitor_running
        if not self.authenticated:
            return "❌ Not authenticated with DUPR API. Check credentials."
        
        if monitor_running:
            return "🔄 Monitoring already running."
        
        monitor_running = True
        return "▶️ DUPR monitoring started!"
    
    def _handle_stop(self) -> str:
        """Handle stop command"""
        global monitor_running, monitor_paused
        monitor_running = False
        monitor_paused = False
        return "⏹️ DUPR monitoring stopped."
    
    def _handle_pause(self) -> str:
        """Handle pause command"""
        global monitor_paused
        monitor_paused = True
        return "⏸️ DUPR monitoring paused."
    
    def _handle_resume(self) -> str:
        """Handle resume command"""
        global monitor_paused
        monitor_paused = False
        return "▶️ DUPR monitoring resumed."
    
    def _handle_target(self, args: List[str]) -> str:
        """Handle target command"""
        if not args:
            return f"Current target: {TARGET_SUM}"
        
        try:
            new_target = float(args[0])
            return f"🎯 Target would change from {TARGET_SUM} to {new_target} (restart monitor to apply)"
        except ValueError:
            return "Invalid target. Use: target <number> (e.g., target 11.5)"
    
    def _handle_estimate(self) -> str:
        """Handle estimate command"""
        return """📈 Rating Estimates (from QPENOLOGN match):

Jon: +0.035 (beat higher rated opponents)
Jared: -0.045 (lost as expected)
Trevor: -0.045 (lost as expected)

Estimated new total: ~11.63-11.66
Still over by ~0.33-0.36"""
    
    def _get_help(self) -> str:
        """Get help message"""
        return f"""🤖 DUPR Bot Commands

Usage: {BOT_KEYWORD} <command>

Commands:
• status - Get current DUPR scores and status
• start - Start monitoring
• stop - Stop monitoring
• pause - Pause monitoring
• resume - Resume monitoring
• target <number> - Show target change info
• estimate - Show rating estimates
• help - Show this help

Examples:
• {BOT_KEYWORD} status
• {BOT_KEYWORD} start
• {BOT_KEYWORD} pause
• {BOT_KEYWORD} target 11.5

Current target: {TARGET_SUM}"""


# Global bot instance
dupr_bot = DuprBotMCP()


def process_message(message: str) -> Optional[str]:
    """
    Process incoming message and return response if it's a DUPR bot command
    
    Args:
        message: Incoming message text
        
    Returns:
        Response message if command was processed, None otherwise
    """
    try:
        # Check if message starts with bot keyword
        if not message.upper().startswith(BOT_KEYWORD):
            return None
        
        # Extract command after keyword
        command = message[len(BOT_KEYWORD):].strip()
        
        # Process command
        response = dupr_bot.process_command(command)
        
        logger.info(f"Processed DUPR command: {command}")
        return response
        
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        return f"❌ Error processing command: {e}"


def initialize_bot() -> bool:
    """Initialize the DUPR bot"""
    return dupr_bot.authenticate()


# MCP Server Integration Functions
# These can be easily integrated into your existing MCP server

def get_dupr_status() -> Dict[str, Any]:
    """Get current DUPR status for MCP server"""
    return dupr_bot.get_current_status()


def handle_dupr_command(command: str) -> str:
    """Handle DUPR command for MCP server"""
    return dupr_bot.process_command(command)


def is_dupr_message(message: str) -> bool:
    """Check if message is a DUPR bot command"""
    return message.upper().startswith(BOT_KEYWORD)


# Example integration for your MCP server:
"""
# Add this to your existing MCP server message handler:

def handle_message(message_text: str, sender: str):
    # Check if it's a DUPR bot command
    if is_dupr_message(message_text):
        response = process_message(message_text)
        if response:
            # Send response back to sender
            send_message(sender, response)
        return True  # Message was handled
    
    # Your existing message handling...
    return False  # Message not handled
"""


def main():
    """Test the DUPR bot MCP server"""
    print(f"🤖 DUPR Bot MCP Server")
    print("=" * 40)
    print(f"Bot keyword: {BOT_KEYWORD}")
    print()
    
    # Initialize bot
    if not initialize_bot():
        print("❌ Failed to initialize DUPR bot")
        return 1
    
    print("✅ DUPR bot initialized successfully!")
    print()
    print("Test commands:")
    print(f"• {BOT_KEYWORD} status")
    print(f"• {BOT_KEYWORD} help")
    print()
    
    # Interactive test
    while True:
        try:
            user_input = input("Enter command: ").strip()
            if not user_input:
                continue
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                break
            
            response = process_message(user_input)
            if response:
                print(f"Bot: {response}")
            else:
                print("Not a DUPR bot command")
            
            print()
            
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
    
    return 0


if __name__ == "__main__":
    exit(main())
