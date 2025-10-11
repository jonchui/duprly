"""
iMessage MCP Server Client
Sends messages via the local iMessage MCP server running on localhost:3000
"""

import requests
from loguru import logger
from typing import List, Optional


class iMessageClient:
    """Client for sending iMessages via local MCP server"""
    
    def __init__(self, base_url: str = "http://localhost:3000", api_key: str = "imessage-mcp-2024-secure-key"):
        self.base_url = base_url
        self.api_key = api_key
        self.headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key
        }
    
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

