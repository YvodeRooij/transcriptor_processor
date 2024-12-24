import logging
import json
from typing import Dict, Optional, List, Type
from datetime import datetime, timedelta
from pydantic import BaseModel, Field

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel as LCBaseModel
from langchain_core.runnables import RunnablePassthrough
from langchain_core.tools import BaseTool
from langchain_core.prompts import ChatPromptTemplate
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain.agents.agent_types import AgentType
from langchain.agents.format_scratchpad import format_to_openai_functions
from langchain.agents.output_parsers import OpenAIFunctionsAgentOutputParser
from langchain.agents.tools import Tool
from langchain.memory import ConversationBufferMemory
from langchain.schema import AgentAction, AgentFinish

from langgraph.graph import StateGraph, END, START

from core.state import ProcessingState, DDPlan, DDRequirement
from core.types import DecisionType, DDCategory, DDStatus, DDPriority
from agents.base import BaseAgent, AgentProcessingError
from core.config import AppConfig, FundCriteria

# Enhanced logging
logger = logging.getLogger(__name__)

class DDAssessment(LCBaseModel):
    """Assessment of due diligence needs."""
    required: bool = Field(..., description="Whether due diligence is required.")
    priority_areas: List[DDCategory] = Field(default_factory=list, description="Areas where due diligence should focus.")
    rationale: str = Field(..., description="Reasoning for the due diligence assessment.")
    estimated_timeline: Optional[str] = Field(None, description="Estimated timeline for due diligence.")
    skip_reason: Optional[str] = Field(None, description="Reason for skipping due diligence.")

class DecisionOutput(LCBaseModel):
    """Structured output for investment decisions."""
    decision: DecisionType = Field(..., description="The investment decision.")
    confidence: float = Field(..., description="Confidence level in the decision (0 to 1).")
    reasoning: str = Field(..., description="Detailed reasoning behind the decision.")
    dd_assessment: DDAssessment = Field(..., description="Assessment of due diligence needs.")

class CreateDDPlanInput(LCBaseModel):
    """Input for creating a due diligence plan."""
    dd_assessment: DDAssessment = Field(..., description="The due diligence assessment.")

class DecisionAgentState(BaseModel):
    """State for the Decision Agent LangGraph."""
    processing_state: ProcessingState
    decision_output: Optional[DecisionOutput] = None
    dd_plan: Optional[DDPlan] = None  # Include DDPlan in the state

class CreateDDPlanTool(BaseTool):
    """Tool to create a Due Diligence Plan."""
    name: str = Field(default="create_due_diligence_plan", description="The name of the tool")
    description: str = Field(default="Creates a detailed due diligence plan based on the assessment.", description="The description of the tool")
    args_schema: Type[CreateDDPlanInput] = CreateDDPlanInput

    def _run(self, dd_assessment: DDAssessment) -> DDPlan:
        """Creates the DD Plan."""
        try:
            requirements = []
            for area in dd_assessment.priority_areas:
                requirement = DDRequirement(
                    category=area,
                    description=f"Conduct thorough due diligence for {area.value}.",
                    priority=DDPriority.HIGH,
                    status=DDStatus.NOT_STARTED,
                    evidence_required=self._get_evidence_requirements(area),
                    due_date=datetime.now() + timedelta(days=30),
                )
                requirements.append(requirement)

            dd_plan = DDPlan(
                requirements=requirements,
                status=DDStatus.NOT_STARTED,
                start_date=datetime.now(),
                target_completion_date=datetime.now() + timedelta(days=45),
                overall_progress=0.0,
                key_findings=[],
                risk_assessment={},
            )
            return dd_plan
        except Exception as e:
            logger.error(f"Error creating DD plan via tool: {e}", exc_info=True)
            raise ValueError(f"Failed to create DD plan: {e}")

    async def _arun(self, dd_assessment: DDAssessment) -> DDPlan:
        """Asynchronously creates the DD Plan."""
        return self._run(dd_assessment)

    def _get_evidence_requirements(self, category: DDCategory) -> List[str]:
        """Get evidence requirements for a DD category."""
        evidence_map = {
            DDCategory.FINANCIAL: [
                "Review audited financial statements, including balance sheets, income statements, and cash flow statements.",
                "Analyze cash flow projections and underlying assumptions.",
                "Examine revenue model details and historical performance.",
            ],
            DDCategory.MARKET: [
                "Conduct market size and growth analysis.",
                "Assess the competitive landscape and key competitors.",
                "Identify key market trends and growth drivers.",
            ],
            DDCategory.TEAM: [
                "Review management team backgrounds and experience.",
                "Conduct reference checks on key personnel.",
                "Analyze the organizational structure and key roles.",
            ],
            DDCategory.TECHNICAL: [
                "Evaluate the technical architecture and scalability.",
                "Review the development roadmap and key milestones.",
                "Conduct a security assessment and identify potential vulnerabilities.",
            ],
        }
        return evidence_map.get(category, ["Gather relevant documentation and evidence."])

class DecisionAgent(BaseAgent):
    """Agent for making investment decisions and determining DD requirements using LangGraph."""

    def __init__(self, openai_config: dict, fund_criteria: Dict[str, FundCriteria]):
        super().__init__(openai_config)
        self.fund_criteria = fund_criteria
        self.tools = [CreateDDPlanTool()]

        prompt_template = """You are a world-class investment analyst making critical decisions about potential investments. Your analysis must be thorough and your decisions well-justified.

Your task is to evaluate the provided information and make a structured investment decision, including an assessment of due diligence needs. If due diligence is required, you can use the 'create_due_diligence_plan' tool.

The decision should include:
- A clear decision to proceed (FUND_X), gather more information (FOLLOW_UP), or decline (NO_ACTION).
- A confidence level in your decision (between 0.0 and 1.0).
- Detailed reasoning supporting your decision.
- A thorough assessment of due diligence requirements, specifying if it's needed, the priority areas, and your rationale. If no DD is needed, explain why.

Here is the information for your analysis:
{context}

{agent_scratchpad}"""

        self.make_decision_prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content=prompt_template)
        ])
        self.output_parser = JsonOutputParser(pydantic_object=DecisionOutput)

    def format_context(self, state: DecisionAgentState):
        """Formats the context from the state."""
        context = {
            "summary": state.processing_state.summary,
            "key_points": state.processing_state.key_points,
            "company": state.processing_state.company_info.dict() if state.processing_state.company_info else {},
            "investment_criteria": {k: v.dict() for k, v in self.fund_criteria.items()},
            "participants": [p.dict() for p in state.processing_state.participants],
            "next_steps": [step.dict() for step in state.processing_state.next_steps],
        }
        return json.dumps(context, indent=2)

    def make_decision(self, state: DecisionAgentState):
        """Makes a decision using the LLM, potentially calling tools."""
        try:
            formatted_context = self.format_context(state)
            prompt = self.make_decision_prompt.partial(context=formatted_context)
            agent = create_openai_functions_agent(
                llm=self.llm,
                tools=self.tools,
                prompt=prompt
            )
            agent_executor = AgentExecutor(agent=agent, tools=self.tools, verbose=True, handle_parsing_errors=True)
            response = agent_executor.invoke({"agent_scratchpad": format_to_openai_functions([])})
            # Assuming the agent's final answer contains the JSON
            json_output = response['output']
            decision_output = self.output_parser.parse(json_output)
            return {"decision_output": decision_output}
        except Exception as e:
            logger.error(f"Error making decision: {e}", exc_info=True)
            raise AgentProcessingError(f"Decision making failed: {e}")

    def create_dd_plan(self, state: DecisionAgentState):
        """Creates a DD plan if the decision requires it."""
        if state.decision_output and state.decision_output.dd_assessment.required:
            tool = CreateDDPlanTool()
            dd_plan = tool.run(state.decision_output.dd_assessment)
            return {"dd_plan": dd_plan}
        return {"dd_plan": None}

    def should_create_dd_plan(self, state: DecisionAgentState):
        """Determines if a DD plan should be created."""
        if state.decision_output and state.decision_output.dd_assessment.required:
            return "create_plan"
        return "end"

    async def process(self, state: ProcessingState) -> ProcessingState:
        """Processes the state and makes an investment decision using LangGraph."""
        try:
            graph_state = DecisionAgentState(processing_state=state)

            builder = StateGraph(DecisionAgentState)

            # Add nodes
            builder.add_node("make_decision", self.make_decision)
            builder.add_node("create_dd_plan", self.create_dd_plan)

            # Define edges
            builder.add_edge("make_decision", "create_dd_plan")
            builder.add_edge("create_dd_plan", END)

            # Set entry point
            builder.set_entry_point("make_decision")

            graph = builder.compile()
            final_state = await graph.ainvoke(graph_state)

            # Update the original processing state with the outputs
            state.decision = final_state.decision_output.decision if final_state.decision_output else None
            state.decision_confidence = final_state.decision_output.confidence if final_state.decision_output else None
            state.decision_reasoning = final_state.decision_output.reasoning if final_state.decision_output else None
            state.dd_plan = final_state.dd_plan

            return state

        except Exception as e:
            logger.error(f"Error processing decision with LangGraph: {e}", exc_info=True)
            raise AgentProcessingError(f"Decision making process failed: {e}")
