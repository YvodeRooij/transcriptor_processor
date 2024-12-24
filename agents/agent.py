from typing import Dict, Optional, List
import logging
from datetime import datetime
from langchain_core.messages import SystemMessage, HumanMessage
from core.state import ProcessingState
from core.types import DecisionType
from core.config import AppConfig
from .base import BaseAgent, AgentProcessingError
from .workflow import AgentWorkflow
from integrations.slack.client import SlackClient
from integrations.email.client import EmailClient, EmailTemplate

logger = logging.getLogger(__name__)

class MainAgent:
    """Main agent coordinating the processing workflow and handling user interactions."""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.workflow = AgentWorkflow(config)
        self.slack_client = SlackClient(
            bot_token=config.slack.bot_token,
            app_token=config.slack.app_token
        )
        self.email_client = EmailClient(config.email)
        
    async def initialize(self):
        """Initialize connections and resources."""
        await self.workflow.initialize()
        
    async def process_transcript(self, transcript: str) -> ProcessingState:
        """
        Process a transcript and create interactive Slack message.
        
        Args:
            transcript (str): The conversation transcript to process
            
        Returns:
            ProcessingState: The final processing state
        """
        try:
            # Process through main workflow
            state = await self.workflow.process_transcript(transcript)
            
            # Add interactive buttons to Slack message
            await self._add_interaction_buttons(state)
            
            return state
            
        except Exception as e:
            logger.error(f"Failed to process transcript: {str(e)}")
            raise AgentProcessingError(f"Transcript processing failed: {str(e)}")
    
    async def _add_interaction_buttons(self, state: ProcessingState):
        """Add interactive buttons to the Slack message."""
        try:
            # Get the cached message details
            message_info = self.workflow.slack_handler.message_cache.get(state.transcript_id)
            if not message_info:
                logger.error("No cached message found for adding buttons")
                return
            
            # Create button blocks
            button_blocks = [
                {
                    "type": "actions",
                    "block_id": f"decision_buttons_{state.transcript_id}",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "Ja Urgent"
                            },
                            "style": "primary",
                            "value": "urgent",
                            "action_id": "urgent_action"
                        },
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "Ja voor dit fonds maar niet urgent"
                            },
                            "value": "fund_not_urgent",
                            "action_id": "fund_not_urgent_action"
                        },
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "Ja voor later fonds"
                            },
                            "value": "future_fund",
                            "action_id": "future_fund_action"
                        },
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "Nee niet interessant"
                            },
                            "style": "danger",
                            "value": "not_interested",
                            "action_id": "not_interested_action"
                        }
                    ]
                }
            ]
            
            # Update the message with buttons
            await self.slack_client.update_message(
                channel=message_info["channel"],
                timestamp=message_info["ts"],
                blocks=message_info.get("blocks", []) + button_blocks
            )
            
        except Exception as e:
            logger.error(f"Failed to add interaction buttons: {str(e)}")
            raise AgentProcessingError(f"Failed to add interaction buttons: {str(e)}")
    
    async def handle_button_click(self, action: Dict, state: ProcessingState):
        """
        Handle button click actions from Slack.
        
        Args:
            action (Dict): The Slack action payload
            state (ProcessingState): The current processing state
        """
        try:
            action_id = action.get("action_id")
            
            # Map action to workflow
            workflows = {
                "urgent_action": self._handle_urgent_workflow,
                "fund_not_urgent_action": self._handle_fund_not_urgent_workflow,
                "future_fund_action": self._handle_future_fund_workflow,
                "not_interested_action": self._handle_not_interested_workflow
            }
            
            handler = workflows.get(action_id)
            if handler:
                await handler(state)
            else:
                logger.warning(f"Unknown action_id: {action_id}")
                
        except Exception as e:
            logger.error(f"Failed to handle button click: {str(e)}")
            raise AgentProcessingError(f"Button click handling failed: {str(e)}")
    
    async def _handle_urgent_workflow(self, state: ProcessingState):
        """Handle urgent follow-up workflow."""
        try:
            logger.info("🔄 Processing 'Urgent' workflow...")
            
            # Update original message in follow-up channel
            await self._update_message_for_selection(state, "Ja Urgent")
            logger.info("✅ Updated original message with selection")
            
            # Post to fund-x channel
            logger.info(f"📝 Posting to fund-x channel: {self.workflow.slack_handler.fund_x_channel}")
            await self.slack_client.post_message(
                channel=self.workflow.slack_handler.fund_x_channel,
                text=f"URGENT: New opportunity from {state.company_info.name if state.company_info else 'Unknown'}",
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*🚨 URGENT Follow-Up Required*\n\n*Company:* {state.company_info.name if state.company_info else 'N/A'}\n*Summary:* {state.summary}"
                        }
                    }
                ]
            )
            logger.info("✅ Posted to fund-x channel")
            
            # Send email
            logger.info("📧 Sending urgent email...")
            await self._send_urgent_email(state)
            logger.info("✅ Urgent email sent")
            
            # Post confirmation in original thread
            await self._post_workflow_confirmation(
                state,
                "✅ Urgent follow-up initiated:\n• Original message updated\n• Posted to fund-x channel\n• Email sent to conversation owner"
            )
            logger.info("✅ Workflow completed successfully")
            
        except Exception as e:
            logger.error(f"❌ Urgent workflow failed: {str(e)}", exc_info=True)
            await self._post_workflow_confirmation(
                state,
                f"❌ Error processing workflow: {str(e)}"
            )
            raise
    
    async def _handle_fund_not_urgent_workflow(self, state: ProcessingState):
        """Handle non-urgent fund workflow."""
        try:
            logger.info("🔄 Processing 'Fund Not Urgent' workflow...")
            
            # Update original message in follow-up channel
            await self._update_message_for_selection(state, "Ja voor dit fonds maar niet urgent")
            logger.info("✅ Updated original message with selection")
            
            # Post to fund-x channel
            logger.info(f"📝 Posting to fund-x channel: {self.workflow.slack_handler.fund_x_channel}")
            await self.slack_client.post_message(
                channel=self.workflow.slack_handler.fund_x_channel,
                text=f"New opportunity from {state.company_info.name if state.company_info else 'Unknown'}",
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*New Fund Opportunity*\n\n*Company:* {state.company_info.name if state.company_info else 'N/A'}\n*Summary:* {state.summary}"
                        }
                    }
                ]
            )
            logger.info("✅ Posted to fund-x channel")
            
            # Send email
            logger.info("📧 Sending follow-up email...")
            await self._send_fund_not_urgent_email(state)
            logger.info("✅ Follow-up email sent")
            
            # Post confirmation in original thread
            await self._post_workflow_confirmation(
                state,
                "✅ Follow-up initiated:\n• Original message updated\n• Posted to fund-x channel\n• Email sent to conversation owner"
            )
            logger.info("✅ Workflow completed successfully")
            
        except Exception as e:
            logger.error(f"❌ Fund not urgent workflow failed: {str(e)}", exc_info=True)
            await self._post_workflow_confirmation(
                state,
                f"❌ Error processing workflow: {str(e)}"
            )
            raise
    
    async def _handle_future_fund_workflow(self, state: ProcessingState):
        """Handle future fund workflow."""
        try:
            logger.info("🔄 Processing 'Future Fund' workflow...")
            
            # Update original message in follow-up channel
            await self._update_message_for_selection(state, "Ja voor later fonds")
            logger.info("✅ Updated original message with selection")
            
            # Send email
            logger.info("📧 Sending future fund email...")
            await self._send_future_fund_email(state)
            logger.info("✅ Future fund email sent")
            
            # Post confirmation in original thread
            await self._post_workflow_confirmation(
                state,
                "✅ Future fund follow-up initiated:\n• Original message updated\n• Email sent to conversation owner\n• Opportunity noted for future consideration"
            )
            logger.info("✅ Workflow completed successfully")
            
        except Exception as e:
            logger.error(f"❌ Future fund workflow failed: {str(e)}", exc_info=True)
            await self._post_workflow_confirmation(
                state,
                f"❌ Error processing workflow: {str(e)}"
            )
            raise
    
    async def _handle_not_interested_workflow(self, state: ProcessingState):
        """Handle not interested workflow."""
        try:
            logger.info("🔄 Processing 'Not Interested' workflow...")
            
            # Update original message in follow-up channel
            await self._update_message_for_selection(state, "Nee niet interessant")
            logger.info("✅ Updated original message with selection")
            
            # Post to no-action channel
            logger.info(f"📝 Posting to no-action channel: {self.workflow.slack_handler.no_action_channel}")
            await self.slack_client.post_message(
                channel=self.workflow.slack_handler.no_action_channel,
                text=f"Contact not interested: {state.company_info.name if state.company_info else 'Unknown'}",
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Contact Not Interested*\n\n*Company:* {state.company_info.name if state.company_info else 'N/A'}\n*Summary:* {state.summary}"
                        }
                    }
                ]
            )
            logger.info("✅ Posted to no-action channel")
            
            # Post confirmation in original thread
            await self._post_workflow_confirmation(
                state,
                "✅ Not interested workflow completed:\n• Original message updated\n• Notification posted to no-action channel"
            )
            logger.info("✅ Workflow completed successfully")
            
        except Exception as e:
            logger.error(f"❌ Not interested workflow failed: {str(e)}", exc_info=True)
            await self._post_workflow_confirmation(
                state,
                f"❌ Error processing workflow: {str(e)}"
            )
            raise
    
    async def _update_message_for_selection(self, state: ProcessingState, selection: str):
        """Update the Slack message to show the selected option."""
        try:
            message_info = self.workflow.slack_handler.message_cache.get(state.transcript_id)
            if not message_info:
                return
            
            # Add selection to message
            selection_block = {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Selected:* {selection} | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    }
                ]
            }
            
            # Update message
            blocks = message_info.get("blocks", [])
            blocks.append(selection_block)
            
            await self.slack_client.update_message(
                channel=message_info["channel"],
                timestamp=message_info["ts"],
                blocks=blocks
            )
            
        except Exception as e:
            logger.error(f"Failed to update message for selection: {str(e)}")
            raise
    
    async def _post_workflow_confirmation(self, state: ProcessingState, message: str):
        """Post a confirmation message in the thread."""
        try:
            message_info = self.workflow.slack_handler.message_cache.get(state.transcript_id)
            if not message_info:
                return
                
            await self.slack_client.post_message(
                channel=message_info["channel"],
                thread_ts=message_info["ts"],
                text=message
            )
            
        except Exception as e:
            logger.error(f"Failed to post workflow confirmation: {str(e)}")
            raise
    
    async def _send_urgent_email(self, state: ProcessingState):
        """Send urgent follow-up email."""
        try:
            if not state.company_info or not state.company_info.name:
                logger.warning("No company info available for email")
                return
            
            # Generate email content
            body = EmailTemplate.urgent_follow_up(
                company_name=state.company_info.name,
                summary=state.summary,
                key_points=state.key_points,
                next_steps=[step.description for step in state.next_steps]
            )
            
            # Send email
            await self.email_client.send_email(
                to_email=self.config.email.gesprekseigenaar_email,
                subject=f"URGENT Follow-Up Required: {state.company_info.name}",
                body=body,
                html=True
            )
            
        except Exception as e:
            logger.error(f"Failed to send urgent email: {str(e)}")
            raise
    
    async def _send_fund_not_urgent_email(self, state: ProcessingState):
        """Send non-urgent fund follow-up email."""
        try:
            if not state.company_info or not state.company_info.name:
                logger.warning("No company info available for email")
                return
            
            # Generate email content
            body = EmailTemplate.fund_not_urgent(
                company_name=state.company_info.name,
                summary=state.summary,
                key_points=state.key_points,
                next_steps=[step.description for step in state.next_steps]
            )
            
            # Send email
            await self.email_client.send_email(
                to_email=self.config.email.gesprekseigenaar_email,
                subject=f"Fund Follow-Up: {state.company_info.name}",
                body=body,
                html=True
            )
            
        except Exception as e:
            logger.error(f"Failed to send fund not urgent email: {str(e)}")
            raise
    
    async def _send_future_fund_email(self, state: ProcessingState):
        """Send future fund follow-up email."""
        try:
            if not state.company_info or not state.company_info.name:
                logger.warning("No company info available for email")
                return
            
            # Generate email content
            body = EmailTemplate.future_fund(
                company_name=state.company_info.name,
                summary=state.summary,
                key_points=state.key_points,
                next_steps=[step.description for step in state.next_steps]
            )
            
            # Send email
            await self.email_client.send_email(
                to_email=self.config.email.gesprekseigenaar_email,
                subject=f"Future Fund Opportunity: {state.company_info.name}",
                body=body,
                html=True
            )
            
        except Exception as e:
            logger.error(f"Failed to send future fund email: {str(e)}")
            raise
    
    async def shutdown(self):
        """Clean up resources."""
        await self.workflow.shutdown()
        await self.email_client.disconnect()
