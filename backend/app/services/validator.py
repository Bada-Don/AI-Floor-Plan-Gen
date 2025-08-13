# Constraint & overlap validation
from typing import Dict, Any, Tuple, List

def validate_constraints(constraints: Dict[str, Any]) -> Tuple[bool, List[str]]:
    errors = []

    # Example: check overlaps
    coords = []
    for f in constraints.get("features", []):
        x, y, w, h = f["x"], f["y"], f["width"], f["height"]
        rect = [(x, y), (x+w, y+h)]
        for ox, oy, ow, oh in coords:
            if not (x+ w <= ox or ox+ow <= x or y+h <= oy or oy+oh <= y):
                errors.append(f"{f['type']} overlaps with another feature")
        coords.append((x, y, w, h))

    return (len(errors) == 0, errors)
