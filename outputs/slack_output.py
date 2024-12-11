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
        self.channel_map = {
            DecisionType.FUND_X: config["slack"]["fund_x_channel"],
            DecisionType.FOLLOW_UP: config["slack"]["follow_up_channel"],
            DecisionType.NO_ACTION: config["slack"]["no_action_channel"]
        }
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
        """Send processing results to appropriate Slack channel."""
        if not self._initialized:
            await self.initialize()
            
        try:
            # Create blocks for the message
            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "📝 Meeting Summary"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Summary:*\n{state.summary}"
                    }
                }
            ]
            
            # Add key points if available
            if state.key_points:
                key_points_text = "\n".join([f"• {point}" for point in state.key_points])
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Key Points:*\n{key_points_text}"
                    }
                })
            
            # Add company info if available
            if state.company_info:
                company_text = f"*Company:* {state.company_info.name}\n"
                if state.company_info.industry:
                    company_text += f"*Industry:* {state.company_info.industry}\n"
                if state.company_info.stage:
                    company_text += f"*Stage:* {state.company_info.stage}\n"
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": company_text
                    }
                })
            
            # Add participants if available
            if state.participants:
                participants_text = "\n".join([f"• {p.name}" + (f" ({p.role})" if p.role else "") for p in state.participants])
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Participants:*\n{participants_text}"
                    }
                })
            
            # Determine target channel
            channel = self.channel_map.get(state.decision, self.channel_map[DecisionType.FOLLOW_UP])
            
            # Send the message
            response = await self.client.post_message(
                channel=channel,
                text=state.summary[:100] + "...",
                blocks=blocks
            )
            
            # Cache the message details for potential updates
            if response and hasattr(state, 'transcript_id'):
                self.message_cache[state.transcript_id] = {
                    "channel": channel,
                    "ts": response["ts"]
                }
            
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