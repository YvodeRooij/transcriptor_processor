from enum import Enum
from typing import Dict, List, Optional
from datetime import datetime

class DecisionType(str, Enum):
    """Types of decisions that can be made about a transcription."""
    FUND_X = "fund_x"
    FOLLOW_UP = "follow_up"
    NO_ACTION = "no_action"

class IndustryType(str, Enum):
    """Industry categories for classification."""
    AI = "ai"
    SAAS = "saas"
    FINTECH = "fintech"
    HEALTHCARE = "healthcare"
    BIOTECH = "biotech"
    OTHER = "other"

class CompanyStage(str, Enum):
    """Company funding/growth stages."""
    SEED = "seed"
    SERIES_A = "series_a"
    SERIES_B = "series_b"
    SERIES_C = "series_c"
    GROWTH = "growth"

class ProcessingError(Exception):
    """Base exception for processing errors."""
    pass

class ValidationError(ProcessingError):
    """Raised when input validation fails."""
    pass

class IntegrationError(ProcessingError):
    """Raised when an external integration fails."""
    pass