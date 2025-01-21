from typing import Dict, Optional, Any, List
import logging
import os
from datetime import datetime
from dotenv import load_dotenv
from core.state import ProcessingState
from core.config import AppConfig
from outputs.slack_output import SlackOutputHandler
from integrations.slack.handlers import SlackInteractionHandler
from integrations.email.client import EmailClient, EmailTemplate
from core.types import DecisionType
from .transcription import TranscriptionAgent
from .base import AgentProcessingError
from integrations.dealcloud.client import DealCloudClient

logger = logging.getLogger(__name__)

class AgentWorkflow:
    """Orchestrates the flow of data through various agents."""
    
    def __init__(self, config: AppConfig):
        self.config = config
        
        # Initialize transcription agent
        self.transcription_agent = TranscriptionAgent(config.openai)
        
        # Initialize Slack output handler
        self.slack_handler = SlackOutputHandler(config.dict())
        
        # Email client will be initialized on-demand
        self.email_client = None
        self.config = config

        # Initialize DealCloud client if enabled
        if config.enable_dealcloud:
            try:
                # Load environment variables for DealCloud
                load_dotenv()
                logger.info("🔄 Loading DealCloud environment variables...")
                
                # Initialize DealCloud client
                self.dealcloud_client = DealCloudClient()
                logger.info("✅ DealCloud client initialized successfully")
            except Exception as e:
                logger.error(f"❌ Failed to initialize DealCloud client: {str(e)}", exc_info=True)
                self.dealcloud_client = None
        else:
            self.dealcloud_client = None
            logger.info("⚠️ DealCloud integration is disabled")
    
    async def initialize(self):
        """Initialize connections and handlers."""
        try:
            # Initialize Slack connection first
            await self.slack_handler.initialize()
            
            # Set up interaction handlers
            self.interaction_handler = SlackInteractionHandler(slack_client=self.slack_handler.client.web_client)
            
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
            
            # Add interaction handler to Slack client
            # We only need the interaction handler since it handles all button clicks
            self.slack_handler.client.add_socket_handler(self.interaction_handler.handle_interaction)
            
            logger.info("✅ Socket handlers registered")
            logger.info("✅ Workflow initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize workflow: {str(e)}", exc_info=True)
            raise
        

    async def process_transcript(self, transcript: str) -> ProcessingState:
        """
        Process a transcript through the entire workflow.
        
        Args:
            transcript (str): The conversation transcript to process
            
        Returns:
            ProcessingState: The final processing state
        """
        try:
            # Initialize state
            state = ProcessingState(transcript=transcript)
            start_time = datetime.now()
            
            # Run transcription analysis
            logger.info("Starting transcription analysis...")
            state = await self.transcription_agent.process(state)
            
            # Calculate processing duration
            state.processing_duration = (datetime.now() - start_time).total_seconds()
            
            # Send to Slack
            logger.info("Sending results to Slack...")
            await self.slack_handler.send(state)
            
            return state
            
        except Exception as e:
            logger.error(f"Workflow processing failed: {str(e)}")
            raise
    
    def _extract_state_from_blocks(self, blocks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract state data from Slack message blocks."""
        state_data = {
            "company_name": "",
            "summary": "",
            "key_points": [],
            "next_steps": []
        }
        
        current_section = None
        
        for block in blocks:
            if block["type"] == "section":
                text = block["text"]["text"]
                
                # Handle section headers
                if "*Company:*" in text:
                    current_section = "company"
                    company = text.split("*Company:*")[1].strip()
                    state_data["company_name"] = company.replace('*', '').replace('\n', ' ').strip()
                elif "*Summary:*" in text:
                    current_section = "summary"
                    summary = text.split("*Summary:*")[1].strip()
                    state_data["summary"] = summary.replace('*', '').strip()
                elif "*Key Points:*" in text:
                    current_section = "key_points"
                    points_text = text.split("*Key Points:*")[1].strip()
                    # Split by bullet points and clean
                    # Split by bullet points and clean
                    points = []
                    for line in points_text.split('\n'):
                        line = line.strip()
                        if line and line.startswith('•'):
                            point = line.lstrip('•').strip()
                            if point and not point.startswith('*') and not point.endswith('*'):
                                points.append(point)
                    state_data["key_points"] = points
                elif "*Next Steps:*" in text:
                    current_section = "next_steps"
                    steps_text = text.split("*Next Steps:*")[1].strip()
                    # Split by bullet points and clean
                    # Split by bullet points and clean
                    steps = []
                    for line in steps_text.split('\n'):
                        line = line.strip()
                        if line and line.startswith('•'):
                            step = line.lstrip('•').strip()
                            if step and not step.startswith('*') and not step.endswith('*'):
                                steps.append(step)
                    state_data["next_steps"] = steps
                # Handle content in current section
                elif current_section in ["key_points", "next_steps"]:
                    items = [item.strip().lstrip('•').lstrip('-').strip() 
                            for item in text.split('\n')]
                    valid_items = [item for item in items 
                                 if item and not item.startswith('*') and not item.endswith('*')]
                    state_data[current_section].extend(valid_items)
        
        return state_data

    async def _handle_urgent_action(self, payload: Dict[str, Any]):
        """Handle urgent action button click."""
        try:
            logger.info("🚨 Starting urgent action processing...")
            
            # Extract message details
            channel = payload["channel"]["id"]
            message_ts = payload["message"]["ts"]
            logger.info(f"Processing action in channel: {channel}, message ts: {message_ts}")
            
            # Get state data from message blocks
            state_data = self._extract_state_from_blocks(payload["message"]["blocks"])
            logger.info("Extracted state data:")
            logger.info(f"Company: {state_data['company_name']}")
            logger.info(f"Summary: {state_data['summary']}")
            logger.info(f"Key Points: {state_data['key_points']}")
            logger.info(f"Next Steps: {state_data['next_steps']}")
            
            # Log the raw blocks for debugging
            logger.info("Raw Slack blocks:")
            for block in payload["message"]["blocks"]:
                if block.get("type") == "section":
                    logger.info(f"Block text: {block['text']['text']}")
            
            # Generate email draft
            logger.info("Generating email from template...")
            template = EmailTemplate.get_template_for_decision(DecisionType.FOLLOW_UP)
            email_body = template(
                company_name=state_data["company_name"],
                summary=state_data["summary"],
                key_points=state_data["key_points"],
                next_steps=state_data["next_steps"]
            )
            
            # Initialize email client if needed
            if not self.email_client and self.config.email:
                logger.info("Initializing email client...")
                self.email_client = EmailClient(self.config.email)

            # Send test email if email is configured
            if self.email_client:
                # Clean company name for email subject by removing markdown and newlines
                clean_company_name = state_data['company_name'].replace('*', '').replace('\n', ' ').strip()
                logger.info(f"Sending test email to {EmailTemplate.TEST_EMAIL}...")
                await self.email_client.send_email(
                    to_email=EmailTemplate.TEST_EMAIL,
                    subject=f"[TEST] Urgent Follow-Up: {clean_company_name}",
                    body=email_body
                )
                logger.info("✅ Email sent successfully")
            
            # Update Slack message
            logger.info("Preparing Slack message update...")
            blocks = [b for b in payload["message"]["blocks"] if b.get("type") != "actions" and b.get("type") != "divider"]
            logger.info(f"Filtered {len(blocks)} blocks for update")
            
            # Add the decision text
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"✅ *Decision: Urgent Action*" + (f"\nTest email sent to {EmailTemplate.TEST_EMAIL}" if self.email_client else "")
                }
            })
            
            # Add divider and completion indicator button
            blocks.extend([
                {"type": "divider"},
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "✅ Processed",
                                "emoji": True
                            },
                            "value": "processed",
                            "action_id": "processed_action",
                            "style": "primary",
                            "confirm": {
                                "title": {
                                    "type": "plain_text",
                                    "text": "Action Complete"
                                },
                                "text": {
                                    "type": "plain_text",
                                    "text": "This action has been processed and cannot be undone."
                                }
                            }
                        }
                    ]
                }
            ])
            
            logger.info("Sending message update to Slack...")
            await self.slack_handler.client.update_message(
                channel=channel,
                timestamp=message_ts,
                blocks=blocks,
                text="Decision made: Urgent Action"
            )
            logger.info("✅ Slack message updated successfully")
            logger.info("✅ Urgent action processing complete")

            # Log whether DealCloud is configured
            logger.info("🔍 Checking DealCloud configuration...")
            if self.dealcloud_client:
                logger.info("🔄 DealCloud client is configured, attempting to create deal...")
            else:
                logger.info("⚠️ DealCloud client is not configured, skipping deal creation")
                
            # Create deal in DealCloud if client is configured    
            if self.dealcloud_client:
                logger.info(f"🔄 Attempting to create deal in DealCloud for company: {state_data['company_name']}")
                try:
                    deal_data = {
                        "Subject": f"Urgent Follow-Up: {state_data['company_name']}",
                        "Notes": (
                            f"Decision: Urgent Follow-Up\n\n"
                            f"Summary:\n{state_data['summary']}\n\n"
                            f"Key Points:\n" + "\n".join(f"- {point}" for point in state_data["key_points"]) + "\n\n"
                            f"Next Steps:\n" + "\n".join(f"- {step}" for step in state_data["next_steps"])
                        )
                    }
                    created_deal = await self.dealcloud_client.create_deal(deal_data)
                    logger.info(f"✨ Successfully created urgent deal in DealCloud (ID: {created_deal['EntryId']})")
                except Exception as e:
                    logger.error(f"💥 Failed to create deal in DealCloud: {str(e)}", exc_info=True)
                    raise
            
        except Exception as e:
            logger.error(f"❌ Error handling urgent action: {str(e)}", exc_info=True)
            raise

    async def _handle_fund_not_urgent_action(self, payload: Dict[str, Any]):
        """Handle fund not urgent action button click."""
        try:
            logger.info("💼 Starting fund (not urgent) action processing...")
            channel = payload["channel"]["id"]
            message_ts = payload["message"]["ts"]
            logger.info(f"Processing action in channel: {channel}, message ts: {message_ts}")
            
            # Get state data from message blocks
            state_data = self._extract_state_from_blocks(payload["message"]["blocks"])
            
            # Generate email draft
            template = EmailTemplate.get_template_for_decision(DecisionType.FUND_X)
            email_body = template(
                company_name=state_data["company_name"],
                summary=state_data["summary"],
                key_points=state_data["key_points"],
                next_steps=state_data["next_steps"]
            )
            
            logger.info(f"Extracted data for company: {state_data['company_name']}")
            logger.info("Generating email from template...")
            
            # Initialize email client if needed
            if not self.email_client and self.config.email:
                logger.info("Initializing email client...")
                self.email_client = EmailClient(self.config.email)

            # Send test email if email is configured
            if self.email_client:
                # Clean company name for email subject by removing markdown and newlines
                clean_company_name = state_data['company_name'].replace('*', '').replace('\n', ' ').strip()
                logger.info(f"Sending test email to {EmailTemplate.TEST_EMAIL}...")
                await self.email_client.send_email(
                    to_email=EmailTemplate.TEST_EMAIL,
                    subject=f"[TEST] Fund Follow-Up: {clean_company_name}",
                    body=email_body
                )
                logger.info("✅ Email sent successfully")
            
            # Update Slack message
            logger.info("Preparing Slack message update...")
            blocks = [b for b in payload["message"]["blocks"] if b.get("type") != "actions" and b.get("type") != "divider"]
            logger.info(f"Filtered {len(blocks)} blocks for update")
            
            # Add the decision text
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"✅ *Decision: Fund (Not Urgent)*" + (f"\nTest email sent to {EmailTemplate.TEST_EMAIL}" if self.email_client else "")
                }
            })
            
            # Add divider and completion indicator button
            blocks.extend([
                {"type": "divider"},
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "✅ Processed",
                                "emoji": True
                            },
                            "value": "processed",
                            "action_id": "processed_action"
                        }
                    ]
                }
            ])
            
            await self.slack_handler.client.update_message(
                channel=channel,
                timestamp=message_ts,
                blocks=blocks,
                text="Decision made: Fund (Not Urgent)"
            )
            logger.info("✅ Slack message updated successfully")
            logger.info("✅ Fund (not urgent) action processing complete")

            # Create deal in DealCloud if client is configured
            if self.dealcloud_client:
                logger.info(f"🔄 Attempting to create deal in DealCloud for company: {state_data['company_name']}")
                try:
                    deal_data = {
                        "Date": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "Subject": f"Fund Follow-Up: {state_data['company_name']}",
                        "Notes": (
                            f"Decision: Fund (Not Urgent)\n\n"
                            f"Summary:\n{state_data['summary']}\n\n"
                            f"Key Points:\n" + "\n".join(f"- {point}" for point in state_data["key_points"]) + "\n\n"
                            f"Next Steps:\n" + "\n".join(f"- {step}" for step in state_data["next_steps"])
                        )
                    }
                    created_deal = await self.dealcloud_client.create_deal(deal_data)
                    logger.info(f"✨ Successfully created fund_not_urgent deal in DealCloud (ID: {created_deal.get('EntryId')})")
                except Exception as e:
                    logger.error(f"💥 Failed to create deal in DealCloud: {str(e)}", exc_info=True)
                    raise
            
        except Exception as e:
            logger.error(f"❌ Error handling fund not urgent action: {str(e)}", exc_info=True)
            raise
        
    async def _handle_future_fund_action(self, payload: Dict[str, Any]):
        """Handle future fund action button click."""
        try:
            logger.info("🔄 Starting future fund action processing...")
            channel = payload["channel"]["id"]
            message_ts = payload["message"]["ts"]
            logger.info(f"Processing action in channel: {channel}, message ts: {message_ts}")
            
            # Get state data from message blocks
            state_data = self._extract_state_from_blocks(payload["message"]["blocks"])
            
            # Generate email draft
            template = EmailTemplate.get_template_for_decision(DecisionType.FUTURE_FUND)
            email_body = template(
                company_name=state_data["company_name"],
                summary=state_data["summary"],
                key_points=state_data["key_points"],
                next_steps=state_data["next_steps"]
            )
            
            logger.info(f"Extracted data for company: {state_data['company_name']}")
            logger.info("Generating email from template...")
            
            # Initialize email client if needed
            if not self.email_client and self.config.email:
                logger.info("Initializing email client...")
                self.email_client = EmailClient(self.config.email)

            # Send test email if email is configured
            if self.email_client:
                # Clean company name for email subject by removing markdown and newlines
                clean_company_name = state_data['company_name'].replace('*', '').replace('\n', ' ').strip()
                logger.info(f"Sending test email to {EmailTemplate.TEST_EMAIL}...")
                await self.email_client.send_email(
                    to_email=EmailTemplate.TEST_EMAIL,
                    subject=f"[TEST] Future Fund Opportunity: {clean_company_name}",
                    body=email_body
                )
                logger.info("✅ Email sent successfully")
            
            # Update Slack message
            logger.info("Preparing Slack message update...")
            blocks = [b for b in payload["message"]["blocks"] if b.get("type") != "actions" and b.get("type") != "divider"]
            logger.info(f"Filtered {len(blocks)} blocks for update")
            
            # Add the decision text
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"✅ *Decision: Future Fund*" + (f"\nTest email sent to {EmailTemplate.TEST_EMAIL}" if self.email_client else "")
                }
            })
            
            # Add divider and completion indicator button
            blocks.extend([
                {"type": "divider"},
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "✅ Processed",
                                "emoji": True
                            },
                            "value": "processed",
                            "action_id": "processed_action"
                        }
                    ]
                }
            ])
            
            await self.slack_handler.client.update_message(
                channel=channel,
                timestamp=message_ts,
                blocks=blocks,
                text="Decision made: Future Fund"
            )
            logger.info("✅ Slack message updated successfully")
            logger.info("✅ Future fund action processing complete")

            # Create deal in DealCloud if client is configured
            if self.dealcloud_client:
                try:
                    deal_data = {
                        "Date": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "Subject": f"Future Fund: {state_data['company_name']}",
                        "Notes": (
                            f"Decision: Future Fund\n\n"
                            f"Summary:\n{state_data['summary']}\n\n"
                            f"Key Points:\n" + "\n".join(f"- {point}" for point in state_data["key_points"]) + "\n\n"
                            f"Next Steps:\n" + "\n".join(f"- {step}" for step in state_data["next_steps"])
                        )
                    }
                    created_deal = await self.dealcloud_client.create_deal(deal_data)
                    logger.info(f"✨ Successfully created future fund deal in DealCloud (ID: {created_deal.get('EntryId')})")
                except Exception as e:
                    logger.error(f"💥 Failed to create deal in DealCloud: {str(e)}", exc_info=True)
                    raise
            
        except Exception as e:
            logger.error(f"❌ Error handling future fund action: {str(e)}", exc_info=True)
            raise
        
    async def _handle_not_interested_action(self, payload: Dict[str, Any]):
        """Handle not interested action button click."""
        try:
            logger.info("❌ Starting not interested action processing...")
            channel = payload["channel"]["id"]
            message_ts = payload["message"]["ts"]
            logger.info(f"Processing action in channel: {channel}, message ts: {message_ts}")
            
            # Get state data from message blocks
            state_data = self._extract_state_from_blocks(payload["message"]["blocks"])
            
            # Generate email draft
            template = EmailTemplate.get_template_for_decision(DecisionType.NO_ACTION)
            email_body = template(
                company_name=state_data["company_name"],
                summary=state_data["summary"],
                key_points=state_data["key_points"],
                reasoning="Based on our current investment criteria and strategy, this opportunity does not align with our focus areas at this time."
            )
            
            logger.info(f"Extracted data for company: {state_data['company_name']}")
            logger.info("Generating email from template...")
            
            # Initialize email client if needed
            if not self.email_client and self.config.email:
                logger.info("Initializing email client...")
                self.email_client = EmailClient(self.config.email)

            # Send test email if email is configured
            if self.email_client:
                # Clean company name for email subject by removing markdown and newlines
                clean_company_name = state_data['company_name'].replace('*', '').replace('\n', ' ').strip()
                logger.info(f"Sending test email to {EmailTemplate.TEST_EMAIL}...")
                await self.email_client.send_email(
                    to_email=EmailTemplate.TEST_EMAIL,
                    subject=f"[TEST] Investment Review: {clean_company_name}",
                    body=email_body
                )
                logger.info("✅ Email sent successfully")
            
            # Update Slack message
            logger.info("Preparing Slack message update...")
            blocks = [b for b in payload["message"]["blocks"] if b.get("type") != "actions" and b.get("type") != "divider"]
            logger.info(f"Filtered {len(blocks)} blocks for update")
            
            # Add the decision text
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"✅ *Decision: Not Interested*" + (f"\nTest email sent to {EmailTemplate.TEST_EMAIL}" if self.email_client else "")
                }
            })
            
            # Add divider and completion indicator button
            blocks.extend([
                {"type": "divider"},
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "✅ Processed",
                                "emoji": True
                            },
                            "value": "processed",
                            "action_id": "processed_action"
                        }
                    ]
                }
            ])
            
            await self.slack_handler.client.update_message(
                channel=channel,
                timestamp=message_ts,
                blocks=blocks,
                text="Decision made: Not Interested"
            )
            logger.info("✅ Slack message updated successfully")
            logger.info("✅ Not interested action processing complete")

            # Create deal in DealCloud if client is configured
            if self.dealcloud_client:
                try:
                    deal_data = {
                        "Date": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "Subject": f"Not Interested: {state_data['company_name']}",
                        "Notes": (
                            f"Decision: Not Interested\n\n"
                            f"Summary:\n{state_data['summary']}\n\n"
                            f"Key Points:\n" + "\n".join(f"- {point}" for point in state_data["key_points"]) + "\n\n"
                            "Reason: Based on our current investment criteria and strategy, "
                            "this opportunity does not align with our focus areas at this time."
                        )
                    }
                    created_deal = await self.dealcloud_client.create_deal(deal_data)
                    logger.info(f"✨ Successfully created not interested deal in DealCloud (ID: {created_deal.get('EntryId')})")
                except Exception as e:
                    logger.error(f"💥 Failed to create deal in DealCloud: {str(e)}", exc_info=True)
                    raise
            
        except Exception as e:
            logger.error(f"❌ Error handling not interested action: {str(e)}", exc_info=True)
            raise
        
    async def shutdown(self):
        """Clean up resources."""
        try:
            await self.slack_handler.client.disconnect()
        except Exception as e:
            logger.error(f"Error during shutdown: {str(e)}")
