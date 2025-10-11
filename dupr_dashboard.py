#!/usr/bin/env python3
"""
DUPR Dashboard - Real-time Web Interface
Flask web application with WebSocket support for live DUPR score monitoring
"""

import os
import json
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO, emit
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

# Flask app setup
app = Flask(__name__)
app.config['SECRET_KEY'] = 'dupr-dashboard-secret-key'
socketio = SocketIO(app, cors_allowed_origins="*")

# Global state
current_scores = {}
score_history = []
dashboard_clients = set()


class DuprDashboard:
    """Dashboard backend that monitors DUPR scores and broadcasts updates"""
    
    def __init__(self):
        self.dupr_client = DuprClient()
        self.previous_scores = {}
        self.previous_sum = None
        self.uncounted_matches = 1
        self.match_processed = False
        self.running = False
        
        # Setup logging
        logger.add("dupr_dashboard.log", rotation="1 day", retention="7 days")
    
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
    
    def check_match_processing(self, dupr_id: str) -> bool:
        """Check if the tracked match has been processed"""
        try:
            rc, matches = self.dupr_client.get_member_match_history_p(dupr_id)
            if rc == 200 and matches:
                for match in matches:
                    if match.get("matchId") == MATCH_TO_TRACK:
                        match_score_added = match.get("matchScoreAdded", False)
                        if match_score_added and not self.match_processed:
                            logger.info(f"Match {MATCH_TO_TRACK} has been processed!")
                            self.match_processed = True
                            self.uncounted_matches = 0
                            return True
                        break
            return False
        except Exception as e:
            logger.error(f"Error checking match processing: {e}")
            return False
    
    def estimate_rating_changes(self) -> Dict[str, float]:
        """Estimate rating changes from the uncounted match"""
        estimates = {
            "Jon": 0.035,  # Beat higher rated opponents, slight increase
            "Jared": -0.045,  # Lost as expected, moderate decrease
            "Trevor": -0.045,  # Lost as expected, moderate decrease
        }
        return estimates
    
    def get_current_status(self) -> Dict:
        """Get current status for dashboard"""
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
            "uncounted_matches": self.uncounted_matches,
            "match_processed": self.match_processed,
            "estimates": self.estimate_rating_changes() if self.uncounted_matches > 0 else {},
            "timestamp": datetime.now().isoformat()
        }
    
    def monitor_loop(self):
        """Main monitoring loop that broadcasts updates to dashboard clients"""
        logger.info("Starting DUPR dashboard monitoring...")
        
        while self.running:
            try:
                status = self.get_current_status()
                
                # Check for changes
                has_changes = False
                if not self.previous_scores:
                    has_changes = True  # First run
                else:
                    for name, score in status["scores"].items():
                        previous = self.previous_scores.get(name, 0)
                        if abs(score - previous) > 0.001:
                            has_changes = True
                            logger.info(f"{name} rating changed: {previous:.3f} → {score:.3f}")
                
                # Check match processing
                for name, player_info in PLAYERS.items():
                    if self.check_match_processing(player_info["dupr_id"]):
                        has_changes = True
                        break
                
                # Add to history
                score_history.append({
                    "timestamp": status["timestamp"],
                    "scores": status["scores"].copy(),
                    "total_sum": status["total_sum"],
                    "gap": status["gap"]
                })
                
                # Keep only last 100 entries
                if len(score_history) > 100:
                    score_history.pop(0)
                
                # Broadcast update to all connected clients
                if dashboard_clients:
                    socketio.emit('score_update', status, room=None)
                    logger.info(f"Broadcasted update to {len(dashboard_clients)} clients")
                
                # Update stored state
                self.previous_scores = status["scores"].copy()
                self.previous_sum = status["total_sum"]
                
                # Sleep for 30 seconds (faster updates for dashboard)
                time.sleep(30)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(30)
        
        logger.info("Dashboard monitoring stopped")
    
    def start_monitoring(self):
        """Start the monitoring thread"""
        if not self.authenticate():
            return False
        
        self.running = True
        monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        monitor_thread.start()
        logger.info("Dashboard monitoring started")
        return True
    
    def stop_monitoring(self):
        """Stop the monitoring thread"""
        self.running = False
        logger.info("Dashboard monitoring stopped")


# Global dashboard instance
dashboard = DuprDashboard()


# Flask routes
@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('dashboard.html')


@app.route('/api/status')
def api_status():
    """API endpoint for current status"""
    status = dashboard.get_current_status()
    return jsonify(status)


@app.route('/api/history')
def api_history():
    """API endpoint for score history"""
    return jsonify(score_history)


# WebSocket events
@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    dashboard_clients.add(request.sid)
    logger.info(f"Client connected: {request.sid}")
    
    # Send current status immediately
    status = dashboard.get_current_status()
    emit('score_update', status)


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    dashboard_clients.discard(request.sid)
    logger.info(f"Client disconnected: {request.sid}")


@socketio.on('request_update')
def handle_request_update():
    """Handle manual update request"""
    status = dashboard.get_current_status()
    emit('score_update', status)


def main():
    """Main entry point"""
    print("🏓 DUPR Dashboard - Real-time Web Interface")
    print("=" * 50)
    
    # Start monitoring
    if not dashboard.start_monitoring():
        print("❌ Failed to start monitoring!")
        return 1
    
    print("✅ Dashboard monitoring started!")
    print("🌐 Starting web server...")
    print("📱 Open http://localhost:5000 in your browser")
    print("Press Ctrl+C to stop")
    print()
    
    try:
        # Run Flask app with SocketIO
        socketio.run(app, host='0.0.0.0', port=5000, debug=False)
    except KeyboardInterrupt:
        print("\n👋 Dashboard stopped. Goodbye!")
        dashboard.stop_monitoring()
        return 0


if __name__ == "__main__":
    exit(main())
