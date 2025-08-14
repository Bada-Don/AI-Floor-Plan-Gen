from fastapi import APIRouter
from app.models.requests import GenerateLayoutRequest
from app.models.responses import LayoutResponse, ConflictResponse
from app.services.nlu_processor import parse_freeform_to_constraints
from app.services.generator import generate_layout
from app.services.renderer import render_svg
import traceback
import json

router = APIRouter()

@router.post("/generate-layout", response_model=None)
def generate_layout_route(req: GenerateLayoutRequest):
    try:
        print("\n=== Incoming Request ===")
        print(json.dumps(req.dict(), indent=2))

        # 1) Build constraints
        constraints = {}
        if req.mode == "freeform" and req.freeform:
            print("[NLU] Parsing freeform input...")
            constraints = parse_freeform_to_constraints(req.freeform.text)
        elif req.mode == "structured" and req.structured:
            print("[NLU] Using structured constraints directly...")
            constraints = req.structured.constraints
        elif req.changeEvent:
            print("[NLU] Processing change event...")
            constraints = req.structured.constraints if req.structured else {}
        else:
            print("[ERROR] Invalid request payload")
            return ConflictResponse(
                error="Invalid request",
                conflicts=["No input provided"],
                suggestions=["Send freeform text or structured constraints"]
            )

        print("\n[Constraints] Built constraints:")
        print(json.dumps(constraints, indent=2))

        # 2) Generate layout
        print("\n[Generator] Generating layout...")
        result = generate_layout(constraints)
        print("[Generator] Raw result:", result)

        if "error" in result:
            print("[Generator] Error in generation, returning conflict response.")
            return ConflictResponse(**result)

        # 3) Render SVG
        print("\n[Renderer] Rendering SVG...")
        svg = render_svg(result)
        result["svg"] = svg
        print("[Renderer] SVG generated successfully.")

        print("\n=== Response Sent ===")
        return LayoutResponse(**result)

    except Exception as e:
        print("\n[Exception] Something went wrong during generation:")
        traceback.print_exc()
        return ConflictResponse(
            error="Internal server error",
            conflicts=[str(e)],
            suggestions=["Check server logs for more details"]
        )
