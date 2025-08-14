from typing import Dict, Any, Tuple, List
from math import fabs

def _rects_overlap(r1, r2) -> bool:
    x1, y1, w1, h1 = r1
    x2, y2, w2, h2 = r2
    # No overlap if one is completely to the left/right or above/below the other
    if x1 + w1 <= x2: return False
    if x2 + w2 <= x1: return False
    if y1 + h1 <= y2: return False
    if y2 + h2 <= y1: return False
    return True

def _in_bounds(lot, rect) -> bool:
    x, y, w, h = rect
    return (x >= 0 and y >= 0 and
            x + w <= lot["width"] and
            y + h <= lot["height"])

def validate_layout_json(layout: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validates a fully generated layout JSON (lot + features)."""
    errors: List[str] = []
    lot = layout.get("lot", {"width": 0, "height": 0})
    feats = layout.get("features", [])

    # 1) In-bounds + non-negative size
    for f in feats:
        rect = (f["x"], f["y"], f["width"], f["height"])
        if f["width"] <= 0 or f["height"] <= 0:
            errors.append(f'{f["type"]} has non-positive size.')
        if not _in_bounds(lot, rect):
            errors.append(f'{f["type"]} is out of lot bounds.')

    # 2) Overlaps
    for i in range(len(feats)):
        r1 = (feats[i]["x"], feats[i]["y"], feats[i]["width"], feats[i]["height"])
        for j in range(i + 1, len(feats)):
            r2 = (feats[j]["x"], feats[j]["y"], feats[j]["width"], feats[j]["height"])
            if _rects_overlap(r1, r2):
                errors.append(f'{feats[i]["type"]} overlaps with {feats[j]["type"]}.')

    # 3) Simple privacy: bathrooms not too close to entrance (Manhattan ≥ threshold)
    # Find entrance(s)
    entrances = [f for f in feats if f["type"].lower() == "entrance"]
    baths = [f for f in feats if "bath" in f["type"].lower()]
    if entrances and baths:
        # Use center points
        def center(f):
            return (f["x"] + f["width"] / 2.0, f["y"] + f["height"] / 2.0)
        for b in baths:
            cbx, cby = center(b)
            min_manhattan = min(
                fabs(cbx - center(e)[0]) + fabs(cby - center(e)[1]) for e in entrances
            )
            threshold = layout.get("meta", {}).get("bathroom_privacy_ft", 12.0)
            if min_manhattan < threshold:
                errors.append(
                    f'Bathroom "{b.get("label", b["type"])}" too close to entrance '
                    f'({min_manhattan:.1f} ft < {threshold:.1f} ft).'
                )

    return (len(errors) == 0, errors)

def validate_constraints(constraints: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Quick feasibility checks on constraints before generation."""
    errors: List[str] = []
    lot = constraints.get("plot") or constraints.get("lot")
    if not lot or lot.get("width", 0) <= 0 or lot.get("height", 0) <= 0:
        errors.append("Plot dimensions missing or invalid.")

    # Optional: sanity checks for fixed features sizes if present
    for feat in (constraints.get("features") or []):
        if feat.get("width", 1) <= 0 or feat.get("height", 1) <= 0:
            errors.append(f'Feature "{feat.get("type","?")}" has invalid size.')

    return (len(errors) == 0, errors)