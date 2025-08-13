# /generate-layout endpoint
from fastapi import APIRouter
from app.models.requests import GenerateLayoutRequest
from app.models.responses import LayoutResponse, ConflictResponse
from app.services.nlu_processor import parse_freeform_to_constraints
from app.services.generator import generate_layout

router = APIRouter()

@router.post("/generate-layout")
def generate_layout_route(req: GenerateLayoutRequest):
    constraints = None
    if req.mode == "freeform" and req.freeform:
        constraints = parse_freeform_to_constraints(req.freeform.text)
    elif req.mode == "structured" and req.structured:
        constraints = req.structured.constraints
    elif req.changeEvent:
        # TODO: Apply change event logic here
        pass

    result = generate_layout(constraints)

    if "error" in result:
        return ConflictResponse(**result)
    return LayoutResponse(**result)
