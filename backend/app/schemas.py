from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class InfluencerCreate(BaseModel):
    username: str
    display_name: Optional[str] = None


class AnalysisFields(BaseModel):
    summary: Optional[str] = None
    sentiment: Optional[str] = None
    stocks: List[str] = []
    ipos: List[str] = []
    sectors: List[str] = []
    geopolitical_events: List[str] = []
    economic_events: List[str] = []
    risks: List[str] = []
    opportunities: List[str] = []
    takeaways: List[str] = []
