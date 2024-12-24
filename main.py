import asyncio
import os
import logging
from dotenv import load_dotenv
from langsmith import Client
from slack_sdk.socket_mode.aiohttp import SocketModeClient
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse

from core.config import AppConfig, SlackConfig, OpenAIConfig, EmailConfig, FundCriteria
from core.types import IndustryType, CompanyStage
from agents.workflow import AgentWorkflow
from utils.logging import setup_logging

# Set up logging with colors and better formatting
setup_logging(
    log_level="INFO",
    log_file="transcription_bot.log"  # Optional: log to file as well
)
logger = logging.getLogger(__name__)

class TranscriptionBot:
    def __init__(self):
        load_dotenv()
        
        # Initialize LangSmith client
        if os.getenv("LANGCHAIN_API_KEY"):
            try:
                langsmith_client = Client()
                logger.info("✅ LangSmith initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize LangSmith: {str(e)}")
        # Debug email environment variables
        logger.info(f"Email Provider: {os.getenv('EMAIL_PROVIDER')}")
        logger.info(f"Email Username: {os.getenv('EMAIL_USERNAME')}")
        logger.info(f"From Email: {os.getenv('FROM_EMAIL')}")
        logger.info(f"Gesprekseigenaar Email: {os.getenv('GESPREKSEIGENAAR_EMAIL')}")
        
        # Create email config first to validate it
        email_config = EmailConfig(
            provider=os.getenv("EMAIL_PROVIDER", "gmail"),
            username=os.getenv("EMAIL_USERNAME", "").strip(),
            password=os.getenv("EMAIL_PASSWORD", "").strip(),
            from_email=os.getenv("FROM_EMAIL", "").strip(),
            gesprekseigenaar_email=os.getenv("GESPREKSEIGENAAR_EMAIL", "").strip()
        )
        
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
            email=EmailConfig(
                provider=os.getenv("EMAIL_PROVIDER", "gmail"),
                username=os.getenv("EMAIL_USERNAME", "").strip(),
                password=os.getenv("EMAIL_PASSWORD", "").strip(),
                from_email=os.getenv("FROM_EMAIL", "").strip(),
                gesprekseigenaar_email=os.getenv("GESPREKSEIGENAAR_EMAIL", "").strip()
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
                    (
                        ("text" in event and not event.get("subtype")) or  # Normal messages
                        (event.get("subtype") == "message_deleted" and "previous_message" in event and "text" in event["previous_message"])  # Deleted messages with text
                    )):
                    
                    logger.info(f"📥 Received new transcription in channel {event['channel']}")
                    # Extract text from blocks if present, otherwise fallback to plain text
                    text = None
                    if "blocks" in event:
                        # Combine text from all blocks
                        text = ""
                        for block in event["blocks"]:
                            if block["type"] == "section" and "text" in block:
                                if isinstance(block["text"], dict) and "text" in block["text"]:
                                    text += block["text"]["text"] + "\n"
                            elif block["type"] == "rich_text":
                                for element in block.get("elements", []):
                                    if element["type"] == "rich_text_section":
                                        for text_element in element.get("elements", []):
                                            if text_element["type"] == "text":
                                                text += text_element["text"]
                        text = text.strip()
                    
                    # Fallback to plain text if no blocks or empty text
                    if not text:
                        text = event.get("text") or (event.get("previous_message", {}).get("text") if event.get("subtype") == "message_deleted" else None)
                    
                    if text:
                        logger.info(f"📝 Transcription length: {len(text)} characters")
                        
                        # Process the transcription
                        try:
                            logger.info("🔄 Starting transcript processing workflow...")
                            result = await self.workflow.process_transcript(text)
                            logger.info(f"✅ Processing complete")
                            logger.info(f"📊 Decision: {result.decision}")
                            logger.info(f"💡 Summary: {result.summary[:100]}...")
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
            
            # Add event handler to existing socket client
            self.workflow.slack_handler.client.socket_client.socket_mode_request_listeners.append(self.handle_slack_event)
            
            # Start listening
            logger.info("🤖 Initializing Transcription Bot...")
            logger.info(f"👂 Listening for transcriptions in channel: {self.config.slack.source_channel}")
            logger.info(f"📢 Will post summaries to channel: {self.config.slack.follow_up_channel}")
            logger.info(f"📋 Available channels:")
            logger.info(f"   • Source: {self.config.slack.source_channel}")
            logger.info(f"   • Follow-up: {self.config.slack.follow_up_channel}")
            logger.info(f"   • Fund-X: {self.config.slack.fund_x_channel}")
            logger.info(f"   • No Action: {self.config.slack.no_action_channel}")
            
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
