import os
import asyncio
from dotenv import load_dotenv
from integrations.slack.client import SlackClient
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

async def test_workflow():
    client = SlackClient(
        bot_token=os.getenv('SLACK_BOT_TOKEN'),
        app_token=os.getenv('SLACK_APP_TOKEN')
    )
    
    await client.connect()
    
    # Create blocks array
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "🤖 Process This Transcript"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": """*Meeting Details*
Date: December 22, 2024

*Participants*
• John Smith (CEO, AI Software Co.)
• Sarah Johnson (CTO, AI Software Co.)
• Mark Wilson (Investment Analyst)"""
            }
        }
    ]
    
    # Read test transcript
    with open('test_transcript.txt', 'r') as f:
        transcript = f.read()
    
    # Split transcript into chunks of 2000 characters
    chunk_size = 2000
    chunks = [transcript[i:i + chunk_size] for i in range(0, len(transcript), chunk_size)]
    
    # Add each chunk as a separate block
    for chunk in chunks:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": chunk
            }
        })
    
    # Send only to source channel
    source_channel = os.getenv('SOURCE_CHANNEL_ID').split('#')[0].strip()
    logger.info(f"Sending transcript to source channel (ID: {source_channel})")
    
    try:
        response = await client.post_message(
            channel=source_channel,
            blocks=blocks,
            text="Meeting transcript for processing"
        )
        logger.info(f"Successfully sent transcript")
        logger.info(f"Response: {response}")
    except Exception as e:
        logger.error(f"Error sending transcript: {str(e)}")
        if hasattr(e, 'response'):
            logger.error(f"Error response: {e.response}")
    
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(test_workflow())
