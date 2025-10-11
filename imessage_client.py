"""
iMessage MCP Server Client & Email Bot
Sends messages via the local iMessage MCP server running on localhost:3000
Also supports email notifications with reply-to-command functionality
"""

import requests
import smtplib
import imaplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from loguru import logger
from typing import List, Optional, Dict
import time
import threading
import os
from dotenv import load_dotenv

load_dotenv()


class iMessageClient:
    """Client for sending iMessages via local MCP server and email bot functionality"""
    
    def __init__(self, base_url: str = "http://localhost:3000", api_key: str = "imessage-mcp-2024-secure-key"):
        self.base_url = base_url
        self.api_key = api_key
        self.headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key
        }
        
        # Email bot configuration
        self.bot_email = os.getenv("DUPR_BOT_EMAIL", "jon.chui@gmail.com")
        self.bot_password = os.getenv("DUPR_BOT_PASSWORD")  # App-specific password
        self.imap_server = "imap.gmail.com"
        self.smtp_server = "smtp.gmail.com"
        self.imap_port = 993
        self.smtp_port = 587
        
        # Command handlers
        self.command_handlers = {
            "status": self._handle_status_command,
            "pause": self._handle_pause_command,
            "resume": self._handle_resume_command,
            "target": self._handle_target_command,
            "help": self._handle_help_command,
            "history": self._handle_history_command,
            "estimate": self._handle_estimate_command,
        }
        
        # Bot state
        self.bot_running = False
        self.monitor_paused = False
        self.current_target = 11.3
        self.last_check_time = None
    
    def health_check(self) -> bool:
        """Check if the iMessage MCP server is running"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            return response.status_code == 200
        except requests.exceptions.RequestException as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    def send_message(self, recipient: str, message: str) -> bool:
        """
        Send an iMessage to a recipient
        
        Args:
            recipient: Phone number (e.g., "+1234567890") or iCloud email
            message: Message text to send
            
        Returns:
            True if message sent successfully, False otherwise
        """
        try:
            payload = {
                "recipient": recipient,
                "message": message
            }
            
            response = requests.post(
                f"{self.base_url}/api/messages/send",
                json=payload,
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"Message sent successfully to {recipient}")
                return True
            else:
                logger.error(f"Failed to send message to {recipient}: {response.status_code} - {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending message to {recipient}: {e}")
            return False
    
    def send_to_multiple(self, recipients: List[str], message: str) -> dict:
        """
        Send the same message to multiple recipients
        
        Args:
            recipients: List of phone numbers or emails
            message: Message text to send
            
        Returns:
            Dict with success/failure counts and details
        """
        results = {
            "success": [],
            "failed": []
        }
        
        for recipient in recipients:
            if self.send_message(recipient, message):
                results["success"].append(recipient)
            else:
                results["failed"].append(recipient)
        
        logger.info(f"Sent to {len(results['success'])}/{len(recipients)} recipients")
        return results
    
    def search_contacts(self, query: str) -> Optional[list]:
        """
        Search contacts by name
        
        Args:
            query: Name or part of name to search for
            
        Returns:
            List of matching contacts or None if error
        """
        try:
            payload = {"query": query}
            
            response = requests.post(
                f"{self.base_url}/api/contacts/search",
                json=payload,
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Contact search failed: {response.status_code}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error searching contacts: {e}")
            return None
    
    # Email Bot Functionality
    
    def send_email(self, to_email: str, subject: str, message: str, reply_to: str = None) -> bool:
        """
        Send email notification
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            message: Email body
            reply_to: Reply-to address (defaults to bot email)
            
        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            if not self.bot_password:
                logger.error("DUPR_BOT_PASSWORD not set in .env file")
                return False
            
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.bot_email
            msg['To'] = to_email
            msg['Subject'] = subject
            msg['Reply-To'] = reply_to or self.bot_email
            
            # Add body
            msg.attach(MIMEText(message, 'plain'))
            
            # Send email
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.bot_email, self.bot_password)
            text = msg.as_string()
            server.sendmail(self.bot_email, to_email, text)
            server.quit()
            
            logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending email to {to_email}: {e}")
            return False
    
    def send_dupr_notification(self, to_email: str, scores: Dict[str, float], 
                             total_sum: float, gap: float, uncounted_matches: int = 0) -> bool:
        """
        Send DUPR score notification email with reply-to-command functionality
        
        Args:
            to_email: Recipient email address
            scores: Current player scores
            total_sum: Combined score total
            gap: Gap to target
            uncounted_matches: Number of uncounted matches
            
        Returns:
            True if email sent successfully, False otherwise
        """
        subject = f"🏓 DUPR Update - {total_sum:.3f} (Gap: {gap:+.3f})"
        
        # Format message with command instructions
        message = f"""🏓 DUPR Score Update

Current Scores:
"""
        for name, score in scores.items():
            message += f"  {name}: {score:.3f}\n"
        
        message += f"""
Combined Score: {total_sum:.3f}
Target: {self.current_target}
Gap: {gap:+.3f} {'(UNDER TARGET!)' if gap <= 0 else '(still over)'}

Uncounted Matches: {uncounted_matches}

---
🤖 DUPR Bot Commands (reply to this email):

• status - Get current status
• pause - Pause monitoring
• resume - Resume monitoring  
• target <number> - Change target (e.g., "target 11.5")
• estimate - Show rating estimates
• history - Show recent changes
• help - Show all commands

Example: Just reply with "status" to get current info.

---
Sent by DUPR Monitor Bot
Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        return self.send_email(to_email, subject, message)
    
    def check_email_commands(self) -> List[Dict]:
        """
        Check for new email commands and process them
        
        Returns:
            List of processed commands
        """
        processed_commands = []
        
        try:
            if not self.bot_password:
                return processed_commands
            
            # Connect to IMAP server
            mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            mail.login(self.bot_email, self.bot_password)
            mail.select('inbox')
            
            # Search for unread emails
            status, messages = mail.search(None, 'UNSEEN')
            email_ids = messages[0].split()
            
            # Process recent emails (last 10)
            for email_id in email_ids[-10:]:
                status, msg_data = mail.fetch(email_id, '(RFC822)')
                email_body = msg_data[0][1]
                email_message = email.message_from_bytes(email_body)
                
                # Check if it's a reply to our bot
                subject = email_message.get('Subject', '')
                if 'DUPR Update' in subject or 'Re:' in subject:
                    # Extract command from email body
                    command = self._extract_command_from_email(email_message)
                    if command:
                        result = self._process_command(command)
                        processed_commands.append({
                            'command': command,
                            'result': result,
                            'timestamp': time.time()
                        })
                        
                        # Mark as read
                        mail.store(email_id, '+FLAGS', '\\Seen')
            
            mail.close()
            mail.logout()
            
        except Exception as e:
            logger.error(f"Error checking email commands: {e}")
        
        return processed_commands
    
    def _extract_command_from_email(self, email_message) -> Optional[str]:
        """Extract command from email body"""
        try:
            # Get email body
            if email_message.is_multipart():
                for part in email_message.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode()
                        break
            else:
                body = email_message.get_payload(decode=True).decode()
            
            # Extract command (look for single word commands)
            lines = body.strip().split('\n')
            for line in lines:
                line = line.strip().lower()
                if line in self.command_handlers:
                    return line
                elif line.startswith('target '):
                    return line
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting command from email: {e}")
            return None
    
    def _process_command(self, command: str) -> str:
        """Process a command and return response"""
        try:
            parts = command.lower().strip().split()
            cmd = parts[0]
            
            if cmd in self.command_handlers:
                return self.command_handlers[cmd](parts[1:] if len(parts) > 1 else [])
            else:
                return f"Unknown command: {cmd}. Type 'help' for available commands."
                
        except Exception as e:
            logger.error(f"Error processing command {command}: {e}")
            return f"Error processing command: {e}"
    
    # Command Handlers
    
    def _handle_status_command(self, args: List[str]) -> str:
        """Handle status command"""
        return f"""🏓 DUPR Bot Status

Monitoring: {'Paused' if self.monitor_paused else 'Active'}
Target: {self.current_target}
Last Check: {self.last_check_time or 'Never'}

Bot Commands:
• status - This message
• pause/resume - Control monitoring
• target <number> - Change target
• estimate - Rating estimates
• help - All commands
"""
    
    def _handle_pause_command(self, args: List[str]) -> str:
        """Handle pause command"""
        self.monitor_paused = True
        return "⏸️ Monitoring paused. Use 'resume' to restart."
    
    def _handle_resume_command(self, args: List[str]) -> str:
        """Handle resume command"""
        self.monitor_paused = False
        return "▶️ Monitoring resumed."
    
    def _handle_target_command(self, args: List[str]) -> str:
        """Handle target command"""
        if not args:
            return f"Current target: {self.current_target}"
        
        try:
            new_target = float(args[0])
            old_target = self.current_target
            self.current_target = new_target
            return f"🎯 Target changed from {old_target} to {new_target}"
        except ValueError:
            return "Invalid target. Use: target <number> (e.g., target 11.5)"
    
    def _handle_help_command(self, args: List[str]) -> str:
        """Handle help command"""
        return """🤖 DUPR Bot Commands

• status - Get current status
• pause - Pause monitoring
• resume - Resume monitoring
• target <number> - Change target score
• estimate - Show rating estimates
• history - Show recent changes
• help - Show this help

Examples:
• target 11.5
• status
• pause
"""
    
    def _handle_history_command(self, args: List[str]) -> str:
        """Handle history command"""
        return "📊 History feature coming soon!"
    
    def _handle_estimate_command(self, args: List[str]) -> str:
        """Handle estimate command"""
        return """📈 Rating Estimates (from QPENOLOGN match):

Jon: +0.035 (beat higher rated opponents)
Jared: -0.045 (lost as expected)
Trevor: -0.045 (lost as expected)

Estimated new total: ~11.63-11.66
"""
    
    def start_email_bot(self):
        """Start the email bot monitoring thread"""
        if not self.bot_password:
            logger.error("Cannot start email bot: DUPR_BOT_PASSWORD not set")
            return False
        
        self.bot_running = True
        bot_thread = threading.Thread(target=self._email_bot_loop, daemon=True)
        bot_thread.start()
        logger.info("Email bot started")
        return True
    
    def stop_email_bot(self):
        """Stop the email bot"""
        self.bot_running = False
        logger.info("Email bot stopped")
    
    def _email_bot_loop(self):
        """Email bot monitoring loop"""
        logger.info("Email bot monitoring started")
        
        while self.bot_running:
            try:
                commands = self.check_email_commands()
                for cmd_info in commands:
                    logger.info(f"Processed command: {cmd_info['command']}")
                    # Could send response email here if needed
                
                time.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in email bot loop: {e}")
                time.sleep(60)
        
        logger.info("Email bot monitoring stopped")

