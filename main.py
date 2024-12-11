import asyncio
import os
import logging
from dotenv import load_dotenv
from slack_sdk.socket_mode.aiohttp import SocketModeClient
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse

from core.config import AppConfig, SlackConfig, OpenAIConfig, FundCriteria
from core.types import IndustryType, CompanyStage
from agents.workflow import AgentWorkflow

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,  # Changed to DEBUG for more detailed logs
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TranscriptionBot:
    def __init__(self):
        load_dotenv()
        self.config = AppConfig(
            slack=SlackConfig(
                bot_token=os.getenv("SLACK_BOT_TOKEN"),
                app_token=os.getenv("SLACK_APP_TOKEN"),
                source_channel=os.getenv("SOURCE_CHANNEL_ID"),
                follow_up_channel=os.getenv("FOLLOW_UP_CHANNEL_ID"),
                fund_x_channel=os.getenv("FUND_X_CHANNEL_ID"),
                no_action_channel=os.getenv("NO_ACTION_CHANNEL_ID")
            ),
            openai=OpenAIConfig(
                api_key=os.getenv("OPENAI_API_KEY")
            ),
            fund_criteria={
                "fund_x": FundCriteria(
                    min_revenue=1000000,
                    target_industries=[IndustryType.AI, IndustryType.SAAS, IndustryType.FINTECH],
                    stages=[CompanyStage.SERIES_A, CompanyStage.SERIES_B],
                    check_size=(500000, 5000000)
                )
            }
        )
        self.workflow = None

    async def handle_slack_event(self, client: SocketModeClient, req: SocketModeRequest):
        """Handle incoming Slack events."""
        # Acknowledge the request immediately
        response = SocketModeResponse(envelope_id=req.envelope_id)
        await client.send_socket_mode_response(response)
        
        try:
            if req.type == "events_api":
                event = req.payload["event"]
                
                # Check if it's a message in our source channel
                if (event["type"] == "message" and 
                    "channel" in event and 
                    event["channel"] == self.config.slack.source_channel and
                    "text" in event and
                    not event.get("subtype")):  # Ignore message subtypes (edits, deletes, etc.)
                    
                    logger.info(f"Received new transcription in channel {event['channel']}")
                    
                    # Process the transcription
                    try:
                        result = await self.workflow.process_transcript(event["text"])
                        logger.info(f"Processing complete. Decision: {result.decision}")
                    except Exception as e:
                        logger.error(f"Error processing transcript: {str(e)}", exc_info=True)
                        # Send error message to Slack
                        error_blocks = [
                            {
                                "type": "section",
                                "text": {
                                    "type": "mrkdwn",
                                    "text": f"⚠️ Error processing transcription:\n```{str(e)}```"
                                }
                            }
                        ]
                        await self.workflow.slack_handler.client.post_message(
                            channel=self.config.slack.follow_up_channel,
                            text="Error processing transcription",
                            blocks=error_blocks
                        )
                        
        except Exception as e:
            logger.error(f"Error handling Slack event: {str(e)}", exc_info=True)

    async def start(self):
        """Start the bot."""
        try:
            # Initialize workflow
            self.workflow = AgentWorkflow(self.config)
            await self.workflow.initialize()
            
            # Initialize Socket Mode client
            client = SocketModeClient(
                app_token=self.config.slack.app_token,
                web_client=self.workflow.slack_handler.client.web_client
            )
            
            # Add event handler
            client.socket_mode_request_listeners.append(self.handle_slack_event)
            
            # Start listening
            logger.info(f"Starting bot... Listening for transcriptions in channel {self.config.slack.source_channel}")
            await client.connect()
            
            # Keep the connection alive
            while True:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Error in bot: {str(e)}", exc_info=True)
        finally:
            if self.workflow:
                await self.workflow.shutdown()

async def main():
    bot = TranscriptionBot()
    await bot.start()

if __name__ == "__main__":
    asyncio.run(main())