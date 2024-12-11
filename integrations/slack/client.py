from typing import Dict, List, Optional
import logging
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.socket_mode.aiohttp import SocketModeClient
from slack_sdk.errors import SlackApiError
from core.types import ProcessingError
from core.state import ProcessingState

logger = logging.getLogger(__name__)

class SlackError(ProcessingError):
    """Slack-specific errors"""
    pass

class SlackClient:
    """Wrapper for Slack API interactions."""
    
    def __init__(self, bot_token: str, app_token: str):
        self.web_client = AsyncWebClient(token=bot_token)
        self.socket_client = SocketModeClient(
            app_token=app_token,
            web_client=self.web_client
        )
        self._connected = False
    
    async def connect(self) -> None:
        """Initialize connection to Slack."""
        try:
            auth_test = await self.web_client.auth_test()
            self.bot_id = auth_test["bot_id"]
            self.bot_user_id = auth_test["user_id"]
            
            await self.socket_client.connect()
            self._connected = True
            logger.info(f"Connected to Slack as bot: {self.bot_id}")
            
        except Exception as e:
            self._connected = False
            raise SlackError(f"Failed to connect to Slack: {str(e)}")
    
    async def disconnect(self) -> None:
        """Disconnect from Slack."""
        if self._connected:
            await self.socket_client.disconnect()
            self._connected = False
    
    async def post_message(self, 
                          channel: str, 
                          blocks: List[Dict], 
                          text: str = "",
                          thread_ts: Optional[str] = None) -> Dict:
        """
        Post a message to a Slack channel.
        
        Args:
            channel: Channel ID to post to
            blocks: Slack blocks for message formatting
            text: Fallback text for notifications
            thread_ts: Optional thread timestamp to reply in thread
            
        Returns:
            Dict containing message details including timestamp
        """
        try:
            return await self.web_client.chat_postMessage(
                channel=channel,
                blocks=blocks,
                text=text,
                thread_ts=thread_ts
            )
        except SlackApiError as e:
            raise SlackError(f"Failed to post message: {str(e)}")
    
    async def update_message(self, 
                           channel: str, 
                           timestamp: str, 
                           blocks: List[Dict], 
                           text: str = "") -> Dict:
        """
        Update an existing Slack message.
        
        Args:
            channel: Channel ID containing the message
            timestamp: Timestamp of message to update
            blocks: New Slack blocks for message
            text: New fallback text
            
        Returns:
            Dict containing updated message details
        """
        try:
            return await self.web_client.chat_update(
                channel=channel,
                ts=timestamp,
                blocks=blocks,
                text=text
            )
        except SlackApiError as e:
            raise SlackError(f"Failed to update message: {str(e)}")
    
    async def add_reaction(self, 
                          channel: str, 
                          timestamp: str, 
                          reaction: str) -> Dict:
        """Add a reaction to a message."""
        try:
            return await self.web_client.reactions_add(
                channel=channel,
                timestamp=timestamp,
                name=reaction
            )
        except SlackApiError as e:
            raise SlackError(f"Failed to add reaction: {str(e)}")
    
    def add_socket_handler(self, handler):
        """Add an event handler for socket mode events."""
        self.socket_client.socket_mode_request_listeners.append(handler)