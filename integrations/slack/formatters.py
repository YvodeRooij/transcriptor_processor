
from typing import Dict, List
from datetime import datetime
from core.state import ProcessingState, Participant, NextStep
from core.types import DecisionType

class SlackFormatter:
    """Format processing results for Slack messages."""
    
    @staticmethod
    def format_header(state: ProcessingState) -> Dict:
        """Format header block."""
        decision_emoji = {
            DecisionType.FUND_X: "🎯",
            DecisionType.FOLLOW_UP: "👀",
            DecisionType.NO_ACTION: "⏩",
        }
        
        emoji = decision_emoji.get(state.decision, "ℹ️")
        return {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{emoji} Conversation Analysis Results"
            }
        }
    
    @staticmethod
    def format_summary(state: ProcessingState) -> Dict:
        """Format summary block."""
        return {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Executive Summary*\n{state.summary}"
            }
        }
    
    @staticmethod
    def format_participants(participants: List[Participant]) -> Dict:
        """Format participants block."""
        participant_text = ""
        for p in participants:
            role_info = f" ({p.role})" if p.role else ""
            company_info = f" from {p.company}" if p.company else ""
            participant_text += f"• {p.name}{role_info}{company_info}\n"
        
        return {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Participants*\n{participant_text}"
            }
        }
    
    @staticmethod
    def format_next_steps(next_steps: List[NextStep]) -> Dict:
        """Format next steps block."""
        steps_text = ""
        for step in next_steps:
            owner = f" - Owner: {step.owner}" if step.owner else ""
            deadline = f" - Due: {step.deadline.strftime('%Y-%m-%d')}" if step.deadline else ""
            steps_text += f"• {step.description}{owner}{deadline}\n"
        
        return {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Next Steps*\n{steps_text}"
            }
        }
    
    @staticmethod
    def format_company_info(state: ProcessingState) -> Dict:
        """Format company information block."""
        if not state.company_info:
            return None
            
        info = state.company_info
        company_text = f"*Company:* {info.name}\n"
        if info.industry:
            company_text += f"*Industry:* {info.industry.value}\n"
        if info.stage:
            company_text += f"*Stage:* {info.stage.value}\n"
        if info.revenue:
            company_text += f"*Revenue:* ${info.revenue:,.2f}\n"
        if info.growth_rate:
            company_text += f"*Growth Rate:* {info.growth_rate}%\n"
        
        return {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": company_text
            }
        }
    
    @staticmethod
    def format_footer(state: ProcessingState) -> Dict:
        """Format footer with metadata."""
        return {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": (
                        f"Decision: {state.decision.value if state.decision else 'Pending'} | "
                        f"Confidence: {state.decision_confidence:.1%} | "
                        f"Processed: {state.processed_at.strftime('%Y-%m-%d %H:%M:%S')}"
                    )
                }
            ]
        }
    
    @staticmethod
    def format_disabled_button(action_type: str, text: str, style: str = None) -> Dict:
        """Format a single disabled button."""
        button = {
            "type": "button",
            "text": {
                "type": "plain_text",
                "text": text,
                "emoji": True
            },
            "value": action_type,
            "action_id": f"{action_type}_action",
            "disabled": True
        }
        if style:
            button["style"] = style
        return button

    @classmethod
    def format_processing_result(cls, state: ProcessingState, selected_action: str = None) -> List[Dict]:
        """Format complete processing result into Slack blocks."""
        blocks = [
            cls.format_header(state),
            cls.format_summary(state),
            {"type": "divider"},
        ]
        
        if state.participants:
            blocks.extend([
                cls.format_participants(state.participants),
                {"type": "divider"},
            ])
        
        company_info = cls.format_company_info(state)
        if company_info:
            blocks.extend([
                company_info,
                {"type": "divider"},
            ])
        
        if state.next_steps:
            blocks.extend([
                cls.format_next_steps(state.next_steps),
                {"type": "divider"},
            ])
        
        blocks.append(cls.format_footer(state))
        
        # Add action buttons based on whether an action was selected
        blocks.extend([
            {"type": "divider"},
            {
                "type": "actions",
                "elements": [
                    # If an action was selected, show only that button disabled
                    cls.format_disabled_button(
                        selected_action,
                        {
                            "urgent": "Ja Urgent ✅",
                            "fund_not_urgent": "Ja voor dit fonds maar niet urgent ✅",
                            "future_fund": "Ja voor later fonds ✅",
                            "not_interested": "Nee niet interessant ✅"
                        }.get(selected_action, "Unknown Action"),
                        {
                            "urgent": "primary",
                            "not_interested": "danger"
                        }.get(selected_action)
                    )
                ] if selected_action else [
                    # Otherwise show all active buttons
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
        
        return blocks
