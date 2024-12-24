import os
import logging
import re
import html
from datetime import datetime
from typing import Dict, Any, Callable, Awaitable, Optional
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse
from integrations.krisp.client import KrispClient

logger = logging.getLogger(__name__)

class SlackInteractionHandler:
    """Handler for Slack interactions."""
    
    def __init__(self, slack_client: AsyncWebClient = None):
        self.action_handlers: Dict[str, Callable[[Dict[str, Any]], Awaitable[None]]] = {}
        self.slack_client = slack_client
        self.krisp_client = KrispClient()  # Use cookies from .env for authentication
        self.processed_messages = set()  # Keep track of processed messages
    
    async def cleanup(self):
        """Cleanup resources when shutting down."""
        if self.krisp_client:
            await self.krisp_client.cleanup()
    
    def register_action_handler(
        self,
        action_id: str,
        handler: Callable[[Dict[str, Any]], Awaitable[None]]
    ):
        """Register a handler for a specific action."""
        logger.info(f"🔗 Registering handler for action: {action_id}")
        self.action_handlers[action_id] = handler
        logger.info(f"✅ Handler registered for {action_id}")
    
    def extract_meeting_info(self, text: str, attachments: list = None) -> Dict[str, Any]:
        """Extract meeting information from Krisp message."""
        info = {}
        
        # Try to extract company name from attachments first
        if attachments:
            for attachment in attachments:
                blocks = attachment.get('blocks', [])
                for block in blocks:
                    if block.get('type') == 'section':
                        text_content = block.get('text', {}).get('text', '')
                        if 'Marktlink x' in text_content:
                            company_match = re.search(r'Marktlink x ([^|>]+)', text_content)
                            if company_match:
                                info['company'] = company_match.group(1).strip()
                                break
                    elif block.get('type') == 'context':
                        for element in block.get('elements', []):
                            if element.get('type') == 'mrkdwn' and 'Participants:' in element.get('text', ''):
                                info['participants'] = re.sub(r'<[^>]+\|([^>]+)>', r'\1', element.get('text', '')).replace('*Participants:*', '').strip()
        
        # If no company found in attachments, try the message text
        if not info.get('company'):
            company_match = re.search(r'Marktlink x ([^\n]+)', text)
            info['company'] = company_match.group(1).strip() if company_match else "Unknown Company"
        
        # Extract date and time
        date_match = re.search(r'(\d{1,2} [A-Za-z]+, \d{1,2}:\d{2} [AP]M)', text)
        info['date'] = date_match.group(1) if date_match else datetime.now().strftime("%d %b, %I:%M %p")
        
        # Extract duration
        duration_match = re.search(r'●\s*(\d+)m', text)
        info['duration'] = duration_match.group(1) if duration_match else "Unknown"
        
        # Extract participants if not found in attachments
        if not info.get('participants'):
            participants_match = re.search(r'Participants: ([^\n]+)', text)
            info['participants'] = participants_match.group(1).strip() if participants_match else ""
        
        # Extract meeting notes link from text or attachments
        links = []
        
        # Try to find link in text
        # Handle Slack's link format: <url|text>
        text_links = re.findall(r'<(https://app\.krisp\.ai/t/[^|>]+)[^>]*>', html.unescape(text))
        links.extend(text_links)
        
        # Try to find link in attachments
        if attachments:
            for attachment in attachments:
                if 'app_unfurl_url' in attachment:
                    links.append(html.unescape(attachment['app_unfurl_url']))
                blocks = attachment.get('blocks', [])
                for block in blocks:
                    if block.get('type') == 'section':
                        text_content = block.get('text', {}).get('text', '')
                        block_links = re.findall(r'<(https://app\.krisp\.ai/t/[^|>]+)[^>]*>', html.unescape(text_content))
                        links.extend(block_links)
        
        info['notes_link'] = links[0] if links else None
        
        logger.info(f"Extracted meeting info: {info}")
        return info
    
    async def handle_interaction(self, client: AsyncWebClient, req: SocketModeRequest) -> SocketModeResponse:
        """Handle incoming Slack interactions."""
        logger.info("=" * 40)
        logger.info(f"🎯 Received event type: {req.type}")
        logger.info(f"📦 Payload type: {req.payload.get('type')}")
        
        # Acknowledge the request immediately
        response = SocketModeResponse(envelope_id=req.envelope_id)
        logger.info("✅ Acknowledged interaction")
        
        try:
            # Handle message events from transcriptions channel
            if (req.payload.get('type') == 'event_callback' and 
                req.payload.get('event', {}).get('type') == 'message' and
                req.payload.get('event', {}).get('channel') == os.getenv('SOURCE_CHANNEL_ID')):
                
                event = req.payload['event']
                
                # Handle message_changed events
                if event.get('subtype') == 'message_changed':
                    message = event.get('message', {})
                    text = message.get('text', '')
                    ts = message.get('ts')
                    bot_profile = message.get('bot_profile', {})
                    attachments = message.get('attachments', [])
                else:
                    text = event.get('text', '')
                    ts = event.get('ts')
                    bot_profile = event.get('bot_profile', {})
                    attachments = event.get('attachments', [])
                
                # Skip if we've already processed this message
                if ts in self.processed_messages:
                    return response
                
                # Only process messages from Krisp bot that contain "View meeting notes"
                if bot_profile.get('name') == 'Krisp' and 'View meeting notes' in text:
                    logger.info("📝 Processing new Krisp message")
                    logger.info(f"Message text: {text}")
                    logger.info(f"Message attachments: {attachments}")
                    
                    # Extract meeting information
                    meeting_info = self.extract_meeting_info(text, attachments)
                    
                    if meeting_info.get('notes_link'):
                        logger.info(f"🔗 Found Krisp.ai link: {meeting_info['notes_link']}")
                        
                        try:
                            # Get meeting notes using headless browser
                            meeting_notes = await self.krisp_client.get_meeting_notes(meeting_info['notes_link'])
                            
                            if meeting_notes:
                                # Create analysis blocks
                                followup_blocks = [
                                    {
                                        "type": "header",
                                        "text": {
                                            "type": "plain_text",
                                            "text": ":information_source: Meeting Analysis Required",
                                            "emoji": True
                                        }
                                    },
                                    {
                                        "type": "section",
                                        "text": {
                                            "type": "mrkdwn",
                                            "text": f"*Executive Summary*\n{meeting_notes['summary']}"
                                        }
                                    },
                                    {
                                        "type": "section",
                                        "text": {
                                            "type": "mrkdwn",
                                            "text": (
                                                f"*Company Details*\n"
                                                f"• Company: {meeting_info['company']}\n"
                                                f"• Participants: {meeting_info['participants']}"
                                            )
                                        }
                                    }
                                ]
                                
                                # Add next steps if any were found
                                if meeting_notes['action_items']:
                                    followup_blocks.append({
                                        "type": "section",
                                        "text": {
                                            "type": "mrkdwn",
                                            "text": "*Proposed Next Steps*\n" + "\n".join(f"• {item}" for item in meeting_notes['action_items'])
                                        }
                                    })
                                
                                # Add transcript link and decision buttons
                                followup_blocks.extend([
                                    {
                                        "type": "section",
                                        "text": {
                                            "type": "mrkdwn",
                                            "text": f"<{meeting_info['notes_link']}|View Full Transcript>"
                                        }
                                    },
                                    {
                                        "type": "divider"
                                    },
                                    {
                                        "type": "context",
                                        "elements": [
                                            {
                                                "type": "mrkdwn",
                                                "text": f"Decision: Pending | Processed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                                            }
                                        ]
                                    },
                                    {
                                        "type": "divider"
                                    },
                                    {
                                        "type": "actions",
                                        "elements": [
                                            {
                                                "type": "button",
                                                "text": {
                                                    "type": "plain_text",
                                                    "text": "Ja Urgent",
                                                    "emoji": True
                                                },
                                                "style": "primary",
                                                "value": "urgent",
                                                "action_id": "urgent_action",
                                                "confirm": {
                                                    "title": {
                                                        "type": "plain_text",
                                                        "text": "Confirm Action"
                                                    },
                                                    "text": {
                                                        "type": "mrkdwn",
                                                        "text": "Are you sure you want to mark this as urgent?"
                                                    },
                                                    "confirm": {
                                                        "type": "plain_text",
                                                        "text": "Yes"
                                                    },
                                                    "deny": {
                                                        "type": "plain_text",
                                                        "text": "No"
                                                    }
                                                }
                                            },
                                            {
                                                "type": "button",
                                                "text": {
                                                    "type": "plain_text",
                                                    "text": "Ja voor dit fonds maar niet urgent",
                                                    "emoji": True
                                                },
                                                "value": "fund_not_urgent",
                                                "action_id": "fund_not_urgent_action"
                                            },
                                            {
                                                "type": "button",
                                                "text": {
                                                    "type": "plain_text",
                                                    "text": "Ja voor later fonds",
                                                    "emoji": True
                                                },
                                                "value": "future_fund",
                                                "action_id": "future_fund_action"
                                            },
                                            {
                                                "type": "button",
                                                "text": {
                                                    "type": "plain_text",
                                                    "text": "Nee niet interessant",
                                                    "emoji": True
                                                },
                                                "style": "danger",
                                                "value": "not_interested",
                                                "action_id": "not_interested_action",
                                                "confirm": {
                                                    "title": {
                                                        "type": "plain_text",
                                                        "text": "Confirm Action"
                                                    },
                                                    "text": {
                                                        "type": "mrkdwn",
                                                        "text": "Are you sure you want to mark this as not interested?"
                                                    },
                                                    "confirm": {
                                                        "type": "plain_text",
                                                        "text": "Yes"
                                                    },
                                                    "deny": {
                                                        "type": "plain_text",
                                                        "text": "No"
                                                    }
                                                }
                                            }
                                        ]
                                    }
                                ])
                                
                                # Post analysis to follow-up channel
                                await self.slack_client.chat_postMessage(
                                    channel=os.getenv('FOLLOW_UP_CHANNEL_ID'),
                                    text="New meeting analysis required",
                                    blocks=followup_blocks
                                )
                                logger.info("✅ Posted analysis to follow-up channel")
                                
                                # Mark message as processed
                                self.processed_messages.add(ts)
                            else:
                                logger.error("❌ Failed to fetch meeting notes")
                        except Exception as e:
                            logger.error(f"❌ Error processing meeting notes: {str(e)}")
                    else:
                        logger.info("❌ No Krisp.ai link found in message")
            
            # Handle button clicks
            elif req.payload.get('type') == 'block_actions':
                actions = req.payload.get('actions', [])
                if actions:
                    action = actions[0]
                    action_id = action.get('action_id')
                    logger.info(f"📎 Found action in actions array: {action_id}")
                    
                    if action_id in self.action_handlers:
                        logger.info(f"🔍 Processing action: {action_id}")
                        handler = self.action_handlers[action_id]
                        logger.info(f"⚡ Executing handler for: {action_id}")
                        await handler(req.payload)
                        logger.info(f"✅ Handler completed for: {action_id}")
                    else:
                        logger.warning(f"⚠️ No handler found for action: {action_id}")
                else:
                    logger.warning("⚠️ No actions found in payload")
            
        except Exception as e:
            logger.error(f"❌ Error handling interaction: {str(e)}")
        
        return response
