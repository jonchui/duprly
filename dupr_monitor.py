#!/usr/bin/env python3
"""
DUPR Score Monitor & iMessage Notifier

Monitors Trevor, Jared, and Jon's DUPR scores every 60 seconds and sends 
iMessage notifications when scores change, with special focus on tracking 
when the combined score drops below 11.3 for the MILP tournament registration.
"""

import os
import time
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from loguru import logger
from dotenv import load_dotenv

from dupr_client import DuprClient
from imessage_client import iMessageClient

# Load environment variables
load_dotenv()

# Configuration
PLAYERS = {
    "Trevor": {"dupr_id": "6552489258", "short_id": "PKQX0G", "email": "trevor.jin@gmail.com"},
    "Jared": {"dupr_id": "4847895806", "short_id": "W6YQXG", "email": "jaredfuelberth@gmail.com"},
    "Jon": {"dupr_id": "4405492894", "short_id": "0YVNWN", "email": "pbislife@jonchui.com"}
}

TARGET_SUM = 11.3
POLL_INTERVAL = 60  # seconds
MATCH_TO_TRACK = "QPENOLOGN"

# iMessage recipients
IMESSAGE_RECIPIENTS = ["+16504507174", "+14242412484"]


class DuprMonitor:
    """Main DUPR score monitoring class"""
    
    def __init__(self):
        self.dupr_client = DuprClient()
        self.imessage_client = iMessageClient()
        self.previous_scores = {}
        self.previous_sum = None
        self.uncounted_matches = 1  # QPENOLOGN match
        self.match_processed = False
        
        # Setup logging
        logger.add("dupr_monitor.log", rotation="1 day", retention="7 days")
        
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
    
    def check_imessage_server(self) -> bool:
        """Check if iMessage MCP server is running"""
        if self.imessage_client.health_check():
            logger.info("iMessage MCP server is running")
            return True
        else:
            logger.error("iMessage MCP server is not running on localhost:3000")
            return False
    
    def get_player_rating(self, dupr_id: str) -> Optional[float]:
        """Get current doubles rating for a player"""
        try:
            rc, player_data = self.dupr_client.get_player(dupr_id)
            if rc == 200 and player_data:
                # Extract doubles rating
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
        # Based on Jon & Blair beating Jared/Trevor 11-7, 11-6
        estimates = {
            "Jon": 0.035,    # Beat higher rated opponents, slight increase
            "Jared": -0.045, # Lost as expected, moderate decrease  
            "Trevor": -0.045 # Lost as expected, moderate decrease
        }
        return estimates
    
    def format_score_change_message(self, current_scores: Dict[str, float], 
                                  current_sum: float) -> str:
        """Format the iMessage notification for score changes"""
        lines = ["🏓 DUPR Update!"]
        
        # Show individual changes
        for name, dupr_id in PLAYERS.items():
            current = current_scores.get(name, 0)
            previous = self.previous_scores.get(name, current)
            change = current - previous
            
            if change != 0:
                change_str = f"{change:+.3f}" if change != 0 else "0.000"
                lines.append(f"{name}: {previous:.3f} → {current:.3f} ({change_str})")
            else:
                lines.append(f"{name}: {current:.3f} (no change)")
        
        # Show sum and gap
        lines.append(f"Combined: {current_sum:.3f}")
        gap = current_sum - TARGET_SUM
        if gap > 0:
            lines.append(f"Gap to {TARGET_SUM}: +{gap:.3f} (still over)")
        else:
            lines.append(f"Gap to {TARGET_SUM}: {gap:.3f} (UNDER TARGET!)")
        
        # Show uncounted matches
        if self.uncounted_matches > 0:
            lines.append(f"Uncounted matches: {self.uncounted_matches}")
            
            # Add estimates if we have uncounted matches
            estimates = self.estimate_rating_changes()
            lines.append("Estimated changes when processed:")
            for name, est in estimates.items():
                lines.append(f"  {name}: {est:+.3f}")
        
        return "\n".join(lines)
    
    def format_target_reached_message(self, current_sum: float) -> str:
        """Format special message when target is reached"""
        gap = TARGET_SUM - current_sum
        return f"""🎯 TARGET REACHED!
Combined DUPR: {current_sum:.3f}
You're now {gap:.3f} UNDER {TARGET_SUM}!
Register NOW: go.picklr.site/milp

Current scores:
{chr(10).join([f"{name}: {current_scores.get(name, 0):.3f}" for name in PLAYERS.keys()])}"""
    
    def send_notification(self, message: str) -> bool:
        """Send iMessage notification to all recipients"""
        try:
            results = self.imessage_client.send_to_multiple(IMESSAGE_RECIPIENTS, message)
            success_count = len(results["success"])
            total_count = len(IMESSAGE_RECIPIENTS)
            
            if success_count == total_count:
                logger.info(f"Notification sent to all {total_count} recipients")
                return True
            else:
                logger.warning(f"Notification sent to {success_count}/{total_count} recipients")
                return success_count > 0
                
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
            return False
    
    def run_initial_check(self) -> bool:
        """Run initial check to verify current scores"""
        logger.info("Running initial DUPR score check...")
        
        current_scores = {}
        total_sum = 0
        
        for name, player_info in PLAYERS.items():
            dupr_id = player_info["dupr_id"]
            rating = self.get_player_rating(dupr_id)
            
            if rating is not None:
                current_scores[name] = rating
                total_sum += rating
                logger.info(f"{name} ({dupr_id}): {rating:.3f}")
            else:
                logger.error(f"Failed to get rating for {name}")
                return False
        
        logger.info(f"Current combined score: {total_sum:.3f}")
        logger.info(f"Gap to target {TARGET_SUM}: {total_sum - TARGET_SUM:+.3f}")
        
        # Store initial state
        self.previous_scores = current_scores.copy()
        self.previous_sum = total_sum
        
        return True
    
    def monitor_loop(self):
        """Main monitoring loop"""
        logger.info("Starting DUPR score monitoring...")
        logger.info(f"Monitoring players: {list(PLAYERS.keys())}")
        logger.info(f"Target sum: {TARGET_SUM}")
        logger.info(f"Poll interval: {POLL_INTERVAL} seconds")
        
        while True:
            try:
                logger.info("Checking DUPR scores...")
                
                current_scores = {}
                total_sum = 0
                has_changes = False
                
                # Get current scores
                for name, player_info in PLAYERS.items():
                    dupr_id = player_info["dupr_id"]
                    rating = self.get_player_rating(dupr_id)
                    
                    if rating is not None:
                        current_scores[name] = rating
                        total_sum += rating
                        
                        # Check for changes
                        previous = self.previous_scores.get(name, 0)
                        if abs(rating - previous) > 0.001:  # Account for floating point precision
                            has_changes = True
                            logger.info(f"{name} rating changed: {previous:.3f} → {rating:.3f}")
                    else:
                        logger.error(f"Failed to get rating for {name}")
                        continue
                
                # Check if match has been processed
                for name, player_info in PLAYERS.items():
                    if self.check_match_processing(player_info["dupr_id"]):
                        has_changes = True
                        break
                
                # Send notification if there are changes
                if has_changes:
                    logger.info("Score changes detected, sending notification...")
                    
                    # Check if target reached
                    if total_sum <= TARGET_SUM:
                        message = self.format_target_reached_message(total_sum)
                        logger.info("🎯 TARGET REACHED! Sending special notification")
                    else:
                        message = self.format_score_change_message(current_scores, total_sum)
                    
                    self.send_notification(message)
                    
                    # Update stored state
                    self.previous_scores = current_scores.copy()
                    self.previous_sum = total_sum
                
                else:
                    logger.info(f"No changes detected. Current sum: {total_sum:.3f}")
                
                # Sleep until next check
                logger.info(f"Sleeping for {POLL_INTERVAL} seconds...")
                time.sleep(POLL_INTERVAL)
                
            except KeyboardInterrupt:
                logger.info("Monitoring stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                logger.info("Continuing monitoring in 60 seconds...")
                time.sleep(POLL_INTERVAL)


def main():
    """Main entry point"""
    print("🏓 DUPR Score Monitor & iMessage Notifier")
    print("=" * 50)
    
    monitor = DuprMonitor()
    
    # Check prerequisites
    if not monitor.check_imessage_server():
        print("❌ iMessage MCP server is not running!")
        print("Please start the server on localhost:3000")
        return 1
    
    if not monitor.authenticate():
        print("❌ Failed to authenticate with DUPR API!")
        print("Please check your .env file with DUPR_USERNAME and DUPR_PASSWORD")
        return 1
    
    # Run initial check
    if not monitor.run_initial_check():
        print("❌ Initial check failed!")
        return 1
    
    print("✅ All checks passed! Starting monitoring...")
    print("Press Ctrl+C to stop")
    print()
    
    # Start monitoring
    try:
        monitor.monitor_loop()
    except KeyboardInterrupt:
        print("\n👋 Monitoring stopped. Goodbye!")
        return 0


if __name__ == "__main__":
    exit(main())
