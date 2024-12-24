import os
from typing import Dict, Any
from datetime import datetime
from dotenv import load_dotenv
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.socket_mode.aiohttp import SocketModeClient
import asyncio
import logging
import sys

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from integrations.slack.handlers import SlackInteractionHandler

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class SlackTester:
    def __init__(self):
        # Initialize Slack clients
        self.slack_client = AsyncWebClient(token=os.getenv('SLACK_BOT_TOKEN'))
        self.socket_client = SocketModeClient(
            app_token=os.getenv('SLACK_APP_TOKEN'),
            web_client=self.slack_client
        )
        
        # Set up interaction handlers with Slack client
        self.interaction_handler = SlackInteractionHandler(slack_client=self.slack_client)
        
        # Register handlers for each button action
        self.interaction_handler.register_action_handler(
            "urgent_action",
            self._handle_urgent_action
        )
        self.interaction_handler.register_action_handler(
            "fund_not_urgent_action",
            self._handle_fund_not_urgent_action
        )
        self.interaction_handler.register_action_handler(
            "future_fund_action",
            self._handle_future_fund_action
        )
        self.interaction_handler.register_action_handler(
            "not_interested_action",
            self._handle_not_interested_action
        )
    
    async def _handle_urgent_action(self, payload: Dict[str, Any]):
        """Handle urgent action button click."""
        logger.info("🔥 Processing urgent action")
        # Add your urgent action handling logic here
    
    async def _handle_fund_not_urgent_action(self, payload: Dict[str, Any]):
        """Handle fund not urgent action button click."""
        logger.info("📊 Processing fund not urgent action")
        # Add your fund not urgent action handling logic here
    
    async def _handle_future_fund_action(self, payload: Dict[str, Any]):
        """Handle future fund action button click."""
        logger.info("🔮 Processing future fund action")
        # Add your future fund action handling logic here
    
    async def _handle_not_interested_action(self, payload: Dict[str, Any]):
        """Handle not interested action button click."""
        logger.info("❌ Processing not interested action")
        # Add your not interested action handling logic here
    
    async def start(self):
        """Start listening for Slack events."""
        # Connect to Slack
        logger.info("Starting Slack integration...")
        
        # Get bot info
        auth_response = await self.slack_client.auth_test()
        logger.info(f"Connected to Slack as: {auth_response['bot_id']}")
        
        # Set up socket mode handler
        self.socket_client.socket_mode_request_listeners.append(
            self.interaction_handler.handle_interaction
        )
        
        # Start socket mode client
        await self.socket_client.connect()
        logger.info("Socket Mode client connected")
        logger.info("🔄 Waiting for messages in transcriptions channel... (Press Ctrl+C to exit)")
        
        # Keep the connection alive
        while True:
            await asyncio.sleep(1)

async def main():
    tester = SlackTester()
    await tester.start()

if __name__ == "__main__":
    asyncio.run(main())
