from typing import Dict
import json
from langchain_core.messages import SystemMessage, HumanMessage
from core.state import ProcessingState
from core.types import DecisionType
from core.config import FundCriteria
from .base import BaseAgent, AgentProcessingError

class DecisionAgent(BaseAgent):
    """Agent responsible for making decisions about opportunities."""
    
    def __init__(self, openai_config, fund_criteria: Dict[str, FundCriteria]):
        super().__init__(openai_config)
        self.fund_criteria = fund_criteria
    
    async def process(self, state: ProcessingState) -> ProcessingState:
        """Make a decision based on the analysis."""
        try:
            # Prepare context for decision
            context = {
                "summary": state.summary,
                "company_info": state.company_info.dict() if state.company_info else {},
                "key_points": state.key_points,
                "fund_criteria": {
                    name: criteria.dict() 
                    for name, criteria in self.fund_criteria.items()
                }
            }
            
            # Get decision
            decision_info = await self._make_decision(context)
            
            # Update state
            state.decision = DecisionType(decision_info["decision"])
            state.decision_confidence = decision_info["confidence"]
            state.decision_reasoning = decision_info["reasoning"]
            
            return state
            
        except Exception as e:
            raise AgentProcessingError(f"Decision making failed: {str(e)}")
    
    async def _make_decision(self, context: Dict) -> Dict:
        """Make a decision based on the provided context."""
        prompt = SystemMessage(content=f"""
        Based on the provided information and fund criteria, determine the appropriate decision.
        
        Fund Criteria:
        {json.dumps(context["fund_criteria"], indent=2)}
        
        Company Information:
        {json.dumps(context["company_info"], indent=2)}
        
        Summary:
        {context["summary"]}
        
        Key Points:
        {json.dumps(context["key_points"], indent=2)}
        
        Return a JSON object with:
        {{
            "decision": "fund_x" or "follow_up" or "no_action",
            "confidence": float between 0 and 1,
            "reasoning": "explanation of the decision"
        }}
        """)
        
        response = await self._call_llm([
            prompt,
            HumanMessage(content="Make a decision based on the above information.")
        ])
        
        return json.loads(response)