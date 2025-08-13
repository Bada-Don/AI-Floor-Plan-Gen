# Pydantic response models
from pydantic import BaseModel
from typing import List, Dict, Any

class Feature(BaseModel):
    type: str
    x: float
    y: float
    width: float
    height: float

class LayoutResponse(BaseModel):
    lot: Dict[str, float]
    features: List[Feature]

class ConflictResponse(BaseModel):
    error: str
    conflicts: List[str]
    suggestions: List[str]
