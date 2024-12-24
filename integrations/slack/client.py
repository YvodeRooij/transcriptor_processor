from typing import Dict, List, Optional
import logging
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.socket_mode.aiohttp import SocketModeClient
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse
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
            
            # Connect first
            await self.socket_client.connect()
            
            # Then configure socket mode client to handle all event types
            self.socket_client.socket_mode_request_listeners.append(self._handle_all_events)
            self._connected = True
            logger.info(f"Connected to Slack as bot: {self.bot_id}")
            
        except Exception as e:
            self._connected = False
            raise SlackError(f"Failed to connect to Slack: {str(e)}")
            
    async def _handle_all_events(self, client, req):
        """Log and route all incoming events."""
        try:
            logger.info(f"🔔 Received event: {req.type}")
            logger.debug(f"Event payload: {req.payload}")  # Log payload at debug level since it can be large
            
            # First acknowledge the event
            response = SocketModeResponse(envelope_id=req.envelope_id)
            await client.send_socket_mode_response(response)
            logger.info(f"✅ Acknowledged event: {req.type}")
            
            # Then let registered handlers process the event
            for handler in self.socket_client.socket_mode_request_listeners:
                if handler != self._handle_all_events:  # Avoid recursion
                    try:
                        await handler(client, req)
                        logger.info(f"✅ Handler processed event: {req.type}")
                    except Exception as handler_error:
                        logger.error(f"❌ Handler error: {str(handler_error)}", exc_info=True)
                
        except Exception as e:
            logger.error(f"❌ Error in event handler: {str(e)}", exc_info=True)
            # Ensure we acknowledge even on error
            try:
                response = SocketModeResponse(envelope_id=req.envelope_id)
                await client.send_socket_mode_response(response)
            except Exception as ack_error:
                logger.error(f"❌ Error acknowledging request: {str(ack_error)}", exc_info=True)
    
    async def disconnect(self) -> None:
        """Disconnect from Slack."""
        if self._connected:
            await self.socket_client.disconnect()
            self._connected = False
            logger.info("Disconnected from Slack")
    
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
            logger.info(f"Posting message to channel: {channel}")
            response = await self.web_client.chat_postMessage(
                channel=channel,
                blocks=blocks,
                text=text,
                thread_ts=thread_ts
            )
            logger.info("✅ Message posted successfully")
            return response
        except SlackApiError as e:
            logger.error(f"❌ Failed to post message: {str(e)}")
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
            logger.info(f"Updating message in channel: {channel}")
            response = await self.web_client.chat_update(
                channel=channel,
                ts=timestamp,
                blocks=blocks,
                text=text
            )
            logger.info("✅ Message updated successfully")
            return response
        except SlackApiError as e:
            logger.error(f"❌ Failed to update message: {str(e)}")
            raise SlackError(f"Failed to update message: {str(e)}")
    
    async def add_reaction(self, 
                          channel: str, 
                          timestamp: str, 
                          reaction: str) -> Dict:
        """Add a reaction to a message."""
        try:
            logger.info(f"Adding reaction '{reaction}' to message")
            response = await self.web_client.reactions_add(
                channel=channel,
                timestamp=timestamp,
                name=reaction
            )
            logger.info("✅ Reaction added successfully")
            return response
        except SlackApiError as e:
            logger.error(f"❌ Failed to add reaction: {str(e)}")
            raise SlackError(f"Failed to add reaction: {str(e)}")
    
    def add_socket_handler(self, handler):
        """Add an event handler for socket mode events."""
        logger.info("Adding new socket mode handler")
        self.socket_client.socket_mode_request_listeners.append(handler)
        logger.info("✅ Socket handler added successfully")
