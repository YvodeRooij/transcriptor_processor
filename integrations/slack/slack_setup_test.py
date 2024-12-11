import os
from dotenv import load_dotenv
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.socket_mode.aiohttp import SocketModeClient
from slack_sdk.socket_mode.response import SocketModeResponse
from slack_sdk.socket_mode.request import SocketModeRequest
import asyncio
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class SlackTester:
    def __init__(self):
        self.slack_client = AsyncWebClient(token=os.getenv('SLACK_BOT_TOKEN'))
        self.socket_client = SocketModeClient(
            app_token=os.getenv('SLACK_APP_TOKEN'),
            web_client=self.slack_client
        )

    async def test_channels(self):
        """Test posting to all channels"""
        channels = {
            'source': os.getenv('SOURCE_CHANNEL_ID'),
            'follow_up': os.getenv('FOLLOW_UP_CHANNEL_ID'),
            'fund_x': os.getenv('FUND_X_CHANNEL_ID'),
            'no_action': os.getenv('NO_ACTION_CHANNEL_ID')
        }

        for channel_name, channel_id in channels.items():
            if not channel_id:
                logger.warning(f"No channel ID provided for {channel_name}")
                continue

            try:
                # Test posting a message
                response = await self.slack_client.chat_postMessage(
                    channel=channel_id,
                    text=f"Test message for AI Agent {channel_name} channel - morning Jeep!"
                )
                logger.info(f"Successfully posted to {channel_name} channel")

                # Test reading channel info
                channel_info = await self.slack_client.conversations_info(
                    channel=channel_id
                )
                logger.info(f"Successfully read {channel_name} channel info")

            except Exception as e:
                logger.error(f"Error with {channel_name} channel: {str(e)}")

    async def test_socket_mode(self):
        """Test socket mode connection"""
        async def handle_socket_mode_request(client: SocketModeClient, req: SocketModeRequest):
            if req.type == "events_api":
                # Acknowledge the request
                response = SocketModeResponse(envelope_id=req.envelope_id)
                await client.send_socket_mode_response(response)
                logger.info("Successfully handled socket mode request")

        self.socket_client.socket_mode_request_listeners.append(handle_socket_mode_request)
        
        try:
            # Connect to Slack
            await self.socket_client.connect()
            logger.info("Socket Mode client connected")
            
            # Keep the connection alive for a few seconds
            await asyncio.sleep(5)
            
            # Disconnect
            await self.socket_client.disconnect()
            logger.info("Socket Mode client disconnected")
        except Exception as e:
            logger.error(f"Socket Mode error: {str(e)}")

    async def run_tests(self):
        """Run all tests"""
        logger.info("Starting Slack integration tests...")
        
        # Test basic API connection
        try:
            auth_test = await self.slack_client.auth_test()
            logger.info(f"Connected to Slack as: {auth_test['bot_id']}")
        except Exception as e:
            logger.error(f"Failed to connect to Slack: {str(e)}")
            return

        # Run channel tests
        await self.test_channels()

        # Test Socket Mode
        await self.test_socket_mode()

        logger.info("Slack integration tests completed")

async def main():
    tester = SlackTester()
    await tester.run_tests()

if __name__ == "__main__":
    asyncio.run(main())