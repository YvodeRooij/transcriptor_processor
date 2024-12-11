# agents/summary.py
from typing import List
import logging
from langchain_core.messages import SystemMessage, HumanMessage
from core.state import ProcessingState
from .base import BaseAgent, AgentProcessingError

logger = logging.getLogger(__name__)

class SummaryAgent(BaseAgent):
    """Agent responsible for generating concise summaries of processed information."""
    
    async def process(self, state: ProcessingState) -> ProcessingState:
        """
        Generate a final summary of the processed information.
        
        Args:
            state (ProcessingState): Current processing state
            
        Returns:
            ProcessingState: Updated state with final summary
        """
        try:
            prompt = SystemMessage(content="""You are an AI assistant tasked with creating a final summary.
            Create a concise summary that includes:
            1. Key meeting outcomes
            2. Next steps or action items
            3. Important company details if available
            4. Notable participant contributions
            
            Keep the summary focused and business-oriented.""")
            
            summary = await self._call_llm([
                prompt,
                HumanMessage(content=self._format_state_for_summary(state))
            ])
            
            state.final_summary = summary
            return state
            
        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            raise AgentProcessingError(f"Summary generation failed: {str(e)}")
    
    def _format_state_for_summary(self, state: ProcessingState) -> str:
        """Format the current state into a string for summarization."""
        sections: List[str] = []
        
        # Add transcript summary
        sections.append(f"Meeting Summary:\n{state.summary}")
        
        # Add key points
        if state.key_points:
            points = "\n".join(f"- {point}" for point in state.key_points)
            sections.append(f"Key Points:\n{points}")
        
        # Add company info if available
        if state.company_info:
            company = state.company_info
            company_str = f"Company: {company.name}"
            if company.industry:
                company_str += f"\nIndustry: {company.industry}"
            if company.stage:
                company_str += f"\nStage: {company.stage}"
            sections.append(company_str)
        
        # Add participants if available
        if state.participants:
            participants = "\n".join(
                f"- {p.name}" + (f" ({p.role})" if p.role else "")
                for p in state.participants
            )
            sections.append(f"Participants:\n{participants}")
        
        return "\n\n".join(sections)