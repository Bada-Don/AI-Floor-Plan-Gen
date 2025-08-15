# app/routes/layout.py

from fastapi import APIRouter, HTTPException
from app.models.requests import GenerateLayoutRequest
from app.models.responses import LayoutResponse, Feature # No need to import ConflictResponse here
from floorplan.generator import generate_layout_from_constraints, PlacedRoom
from app.services.nlu_processor import parse_freeform_to_constraints
import traceback
import logging

router = APIRouter()

# We only define the success model here. Errors are handled by exceptions.
@router.post("/generate-floorplan", response_model=LayoutResponse)
async def generate_floorplan(req: GenerateLayoutRequest): # Route must be asynchronous
    try:
        constraints = {}
        # === AI INTEGRATION ===
        if req.mode == "freeform" and req.freeform:
            # CORRECTED: Call the async function with 'await'
            constraints = await parse_freeform_to_constraints(req.freeform.text)
            if "error" in constraints:
                # Use HTTPException to return a clean error response
                raise HTTPException(status_code=400, detail=f"AI Processor Error: {constraints.get('details', 'Failed to understand request.')}")

        elif req.mode == "structured" and req.structured:
            constraints = req.structured.constraints
        else:
            raise HTTPException(status_code=400, detail="Invalid request payload. Mode must be 'freeform' or 'structured'.")

        logging.info(f"Received constraints: {constraints}")

        # Call the generator with the determined constraints
        result, placed_rooms = generate_layout_from_constraints(constraints)

        if "error" in result:
            # CORRECTED: Raise an exception for generator errors
            raise HTTPException(status_code=422, detail=result["error"])

        # Convert PlacedRoom objects to the Pydantic Feature model
        cell_ft = 2
        features_list_ft = [
            Feature(
                type=pr.type,
                x=pr.x * cell_ft,
                y=pr.y * cell_ft,
                width=pr.w * cell_ft,
                height=pr.h * cell_ft,
                label=pr.name
            ) for pr in placed_rooms
        ]

        # Return the successful layout response
        return LayoutResponse(
            lot=result["lot"],
            features=features_list_ft,
            image_base64=result["image_base64"]
        )

    except HTTPException as http_exc:
        # Re-raise HTTPException so FastAPI can handle it
        raise http_exc
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        traceback.print_exc()
        # CORRECTED: Raise a generic 500 error for unexpected issues
        raise HTTPException(status_code=500, detail=f"An internal server error occurred: {str(e)}")
