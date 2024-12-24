from typing import Dict, Any
import logging
from langchain_core.messages import HumanMessage, SystemMessage
from core.state import ProcessingState
from core.types import DecisionType
from integrations.slack.client import SlackClient
from integrations.slack.formatters import SlackFormatter
from outputs.base import OutputHandler

logger = logging.getLogger(__name__)

class SlackOutputHandler(OutputHandler):
    """Handle outputting processing results to Slack."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.client = SlackClient(
            bot_token=config["slack"]["bot_token"],
            app_token=config["slack"]["app_token"]
        )
        self.follow_up_channel = config["slack"]["follow_up_channel"]
        self.fund_x_channel = config["slack"]["fund_x_channel"]
        self.no_action_channel = config["slack"]["no_action_channel"]
        self.message_cache: Dict[str, Dict[str, str]] = {}
        self._initialized = False
    
    async def initialize(self):
        """Initialize the Slack connection."""
        if not self._initialized:
            try:
                await self.client.connect()
                self._initialized = True
                logger.info("Slack connection initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Slack connection: {str(e)}")
                raise
    
    async def send(self, state: ProcessingState) -> bool:
        """Send processing results to follow-up channel with decision buttons."""
        if not self._initialized:
            await self.initialize()
            
        try:
            logger.info("📤 Preparing Slack message...")
            
            # Use SlackFormatter to create message blocks with interactive buttons
            blocks = SlackFormatter.format_processing_result(state)
            
            logger.info(f"💬 Posting to follow-up channel: {self.follow_up_channel}")
            
            # Send the message to follow-up channel
            response = await self.client.post_message(
                channel=self.follow_up_channel,
                text=state.summary[:100] + "...",
                blocks=blocks
            )
            
            # Cache the message details for potential updates
            if response and hasattr(state, 'transcript_id'):
                self.message_cache[state.transcript_id] = {
                    "channel": self.follow_up_channel,
                    "ts": response["ts"],
                    "blocks": blocks
                }
                logger.info("✅ Message posted successfully")
                logger.info("⏳ Waiting for user decision via interactive buttons...")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send to Slack: {str(e)}")
            return False
    
    async def update(self, state: ProcessingState) -> bool:
        """Update existing Slack message with new information."""
        if not self._initialized:
            await self.initialize()
            
        try:
            if not hasattr(state, 'transcript_id'):
                logger.warning("No transcript_id in state for update")
                return False
                
            cached = self.message_cache.get(state.transcript_id)
            if not cached:
                logger.warning("No cached message found for update")
                return await self.send(state)
            
            blocks = SlackFormatter.format_processing_result(state)
            
            await self.client.update_message(
                channel=cached["channel"],
                timestamp=cached["ts"],
                blocks=blocks,
                text=f"Updated analysis: {state.summary[:100]}..."
            )
            
            logger.info(f"Updated Slack message in channel: {cached['channel']}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update Slack message: {str(e)}")
            return False
    
    async def delete(self, identifier: str) -> bool:
        """Delete a Slack message."""
        if not self._initialized:
            await self.initialize()
            
        try:
            cached = self.message_cache.get(identifier)
            if not cached:
                logger.warning("No cached message found for deletion")
                return False
            
            await self.client.delete_message(
                channel=cached["channel"],
                timestamp=cached["ts"]
            )
            
            del self.message_cache[identifier]
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete Slack message: {str(e)}")
            return False
    
    async def get_status(self, identifier: str) -> Dict[str, Any]:
        """Get status of a Slack message."""
        if not self._initialized:
            await self.initialize()
            
        cached = self.message_cache.get(identifier)
        if not cached:
            return {"status": "unknown"}
        
        return {
            "status": "posted",
            "channel": cached["channel"],
            "timestamp": cached["ts"]
        }
