from typing import Dict, Any, List, Tuple
from math import floor
from app.services.validator import validate_constraints, validate_layout_json

# === Defaults for MVP ===
MIN_DIM = {
    "bedroom": (9.0, 10.0),
    "living": (10.0, 12.0),
    "kitchen": (8.0, 10.0),
    "bathroom": (5.0, 7.0),
    "hallway": (3.0, 8.0),
}
DEFAULT_SIZES = {
    "bedroom": (11.0, 12.0),
    "living": (14.0, 16.0),
    "kitchen": (10.0, 12.0),
    "bathroom": (6.0, 8.0),
    "hallway": (4.0, 12.0),
}

def _mk(feature_type: str, x: float, y: float, w: float, h: float, label: str = None, locked: bool=False) -> Dict[str, Any]:
    return {
        "type": feature_type,
        "x": float(x),
        "y": float(y),
        "width": float(w),
        "height": float(h),
        "label": label or feature_type.title(),
        "locked": locked
    }

def _reserve_fixed_features(lot: Dict[str, float], feats: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Handles instructions like:
      park on left (w,h), pool on right (w,h), entrance middle, etc.
    Places them deterministically and flags as locked, guaranteeing entrance space.
    """
    W, H = lot["width"], lot["height"]
    placed: List[Dict[str, Any]] = []

    # Safer defaults and guaranteed entrance space
    DEFAULT_SIDE_WIDTH_RATIO = 0.15
    DEFAULT_SIDE_WIDTH_MAX = 20.0
    MIN_ENTRANCE_WIDTH = 5.0
    MIN_ENTRANCE_HEIGHT = 3.0

    # 1. Separate features by position
    left_feats = [f for f in feats if str(f.get("position","")).lower() == "left"]
    right_feats = [f for f in feats if str(f.get("position","")).lower() == "right"]
    entrance_feats = [f for f in feats if str(f.get("type","")).lower() == "entrance"]
    
    # 2. Reserve space for the entrance and calculate usable width for side features
    usable_width = W - MIN_ENTRANCE_WIDTH

    # 3. Calculate widths of side features with safer defaults
    left_feats_info = []
    total_left_width = 0
    for f in left_feats:
        w = float(f.get("width", min(W * DEFAULT_SIDE_WIDTH_RATIO, DEFAULT_SIDE_WIDTH_MAX)))
        h = float(f.get("height", H))
        left_feats_info.append({'feat': f, 'width': w, 'height': h})
        total_left_width += w

    right_feats_info = []
    total_right_width = 0
    for f in right_feats:
        w = float(f.get("width", min(W * DEFAULT_SIDE_WIDTH_RATIO, DEFAULT_SIDE_WIDTH_MAX)))
        h = float(f.get("height", H))
        right_feats_info.append({'feat': f, 'width': w, 'height': h})
        total_right_width += w

    # 4. Shrink side features proportionally if they occupy too much space
    total_side_width = total_left_width + total_right_width
    if total_side_width > usable_width:
        shrink_ratio = usable_width / total_side_width
        for item in left_feats_info:
            item['width'] *= shrink_ratio
        for item in right_feats_info:
            item['width'] *= shrink_ratio

    # 5. Place left and right features
    cursor_left = 0.0
    for item in left_feats_info:
        f = item['feat']
        w = item['width']
        h = item['height']
        placed.append(_mk(f["type"], cursor_left, 0.0, w, h, f.get("label", f["type"].title()), locked=True))
        cursor_left += w

    cursor_right = W
    for item in right_feats_info:
        f = item['feat']
        w = item['width']
        h = item['height']
        cursor_right -= w
        placed.append(_mk(f["type"], cursor_right, 0.0, w, h, f.get("label", f["type"].title()), locked=True))

    # 6. Place the entrance in the remaining space
    if entrance_feats:
        f = entrance_feats[0] # Assume one entrance
        available_width_for_entrance = cursor_right - cursor_left
        
        # Auto-assign width if not provided
        ew = float(f.get("width", max(MIN_ENTRANCE_WIDTH, available_width_for_entrance * 0.2)))
        ew = min(ew, available_width_for_entrance) # Clamp to available space
        
        eh = float(f.get("height", MIN_ENTRANCE_HEIGHT))

        pos = str(f.get("position","south_center")).lower()
        ex = cursor_left + (available_width_for_entrance - ew) / 2.0
        ey = 0.0
        if "left" in pos:  ex = cursor_left
        if "right" in pos: ex = cursor_right - ew
        if "north" in pos: ey = H - eh
        
        placed.append(_mk("entrance", ex, ey, ew, eh, f.get("label","Entrance"), locked=True))

    # Place other features (e.g., top/bottom strips)
    other_non_side_feats = [f for f in feats if f not in left_feats and f not in right_feats and f not in entrance_feats]
    top_y = H
    bottom_y = 0.0
    for f in other_non_side_feats:
        pos = str(f.get("position","")).lower()
        if pos in ("top", "bottom"):
            w = float(f.get("width", W))
            h = float(f.get("height", H * 0.2))
            x = 0.0
            if pos == "bottom":
                y = bottom_y
                bottom_y += h
            else: # top
                top_y -= h
                y = top_y
            placed.append(_mk(f["type"], x, y, w, h, f.get("label", f["type"].title()), locked=True))


    return placed

def _available_rect(lot: Dict[str, float], occupied: List[Dict[str, Any]]) -> Tuple[float,float,float,float]:
    """Return a single available rectangle after reserving occupied bands.
       MVP: assume left+right bands + bottom/top strips — we allocate the middle."""
    W, H = lot["width"], lot["height"]
    x_left = 0.0
    x_right = W
    y_bottom = 0.0
    y_top = H
    for f in occupied:
        t = f["type"].lower()
        # Deduce which band it is by geometry (locked ones span full height or full width)
        if f["locked"]:
            if f["width"] <= W*0.5 and f["height"] >= H*0.95:
                # treat as vertical band
                if f["x"] == 0.0:
                    x_left = max(x_left, f["x"] + f["width"])
                elif f["x"] + f["width"] >= W - 1e-6:
                    x_right = min(x_right, f["x"])
            if f["height"] <= H*0.5 and f["width"] >= W*0.95:
                # treat as horizontal strip
                if f["y"] == 0.0:
                    y_bottom = max(y_bottom, f["y"] + f["height"])
                elif f["y"] + f["height"] >= H - 1e-6:
                    y_top = min(y_top, f["y"])

    return (x_left, y_bottom, max(0.0, x_right - x_left), max(0.0, y_top - y_bottom))

def _place_core_rooms(lot, core_rect, entrance_rect) -> List[Dict[str, Any]]:
    """Place living, kitchen, hallway in the available middle."""
    x, y, w, h = core_rect
    placed: List[Dict[str, Any]] = []

    if w <= 0 or h <= 0:
        return placed

    # Place Living near entrance horizontally centered
    lw, lh = DEFAULT_SIZES["living"]
    lw = min(lw, w * 0.6); lh = min(lh, h * 0.4)
    living_x = x + (w - lw) / 2.0
    living_y = y + 0.0 + max(entrance_rect["y"] + entrance_rect["height"] - y, 0.0)
    living = _mk("living", living_x, living_y, lw, lh, "Living")

    # Kitchen to the right of Living (if possible)
    kw, kh = DEFAULT_SIZES["kitchen"]
    kw = min(kw, w * 0.35); kh = lh
    kitchen_x = min(x + w - kw, living_x + lw + 2.0)
    kitchen_y = living_y
    kitchen = _mk("kitchen", kitchen_x, kitchen_y, kw, kh, "Kitchen")

    # Hallway above living/kitchen as a horizontal strip
    hw, hh = (w * 0.9, max(DEFAULT_SIZES["hallway"][0], 3.5))
    hallway_x = x + (w - hw) / 2.0
    hallway_y = living_y + lh + 2.0
    hallway = _mk("hallway", hallway_x, hallway_y, hw, hh, "Hallway / Circulation")

    return [living, kitchen, hallway]

def _place_private_rooms(core_rect, hallway, room_counts: Dict[str, int]) -> List[Dict[str, Any]]:
    """Place bedrooms and bathrooms above the hallway band."""
    x, y, w, h = core_rect
    placed: List[Dict[str, Any]] = []

    # Private zone starts above hallway
    priv_y = hallway["y"] + hallway["height"] + 2.0
    available_h = (y + h) - priv_y
    if available_h <= 0:
        return placed

    # Lay out a simple grid: 2 columns of bedrooms if needed
    cols = 2
    col_w = (w - 2.0) / cols
    bx = [x, x + col_w + 2.0]
    by = priv_y

    bsize = DEFAULT_SIZES["bedroom"]
    bathsize = DEFAULT_SIZES["bathroom"]

    # Bedrooms
    bcount = room_counts.get("bedroom", 0)
    for i in range(bcount):
        cx = bx[i % cols]
        cy = by + floor(i / cols) * (bsize[1] + 2.0)
        placed.append(_mk("bedroom", cx, cy, min(bsize[0], col_w), bsize[1], f"Bedroom {i+1}"))

    # Bathrooms (attach near bedrooms but away from entrance – validator checks exact privacy)
    bath_count = room_counts.get("bathroom", 0)
    for i in range(bath_count):
        # Put bathrooms near top-right corner of private area
        bw, bh = bathsize
        bx2 = x + w - bw
        by2 = priv_y + i * (bh + 2.0)
        placed.append(_mk("bathroom", bx2, by2, bw, bh, f"Bathroom {i+1}"))

    return placed

def _count_rooms(constraints: Dict[str, Any]) -> Dict[str, int]:
    counts = {}
    for room in constraints.get("rooms", []):
        room_type = room.get("type")
        count = room.get("count", 0)
        if room_type and count > 0:
            counts[room_type] = counts.get(room_type, 0) + count
    return counts

def _fixed_features_from_constraints(constraints: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    for f in (constraints.get("features") or []):
        entry = {
            "type": f.get("type","").lower(),
            "width": float(f.get("width", 0) or 0),
            "height": float(f.get("height", 0) or 0),
            "position": f.get("position","").lower(),
            "label": f.get("label"),
        }
        out.append(entry)
    # entrance may also come as a separate key
    if constraints.get("entrance"):
        pos = (constraints["entrance"].get("position") or "south_center").lower()
        out.append({"type":"entrance", "position": pos, "width": constraints["entrance"].get("width", None), "height": constraints["entrance"].get("height", None)})
    return out

def generate_layout(constraints: Dict[str, Any]) -> Dict[str, Any]:
    lot = constraints.get("plot") or constraints.get("lot")
    W, H = float(lot["width"]), float(lot["height"])
    layout = {"lot": {"width": W, "height": H}, "features": [], "meta": {"bathroom_privacy_ft": 12.0}}

    # 1) Place fixed features (park left, pool right, entrance middle, etc.)
    fixed = _fixed_features_from_constraints(constraints)
    placed_fixed = _reserve_fixed_features(layout["lot"], fixed)
    layout["features"].extend(placed_fixed)

    # 2) Determine remaining core rectangle
    core_rect = _available_rect(layout["lot"], placed_fixed)

    # 3) Place core public chain (living, kitchen, hallway)
    entrance = next((f for f in placed_fixed if f["type"] == "entrance"), _mk("entrance", W/2 - 5, 0.0, 10.0, 4.0, "Entrance", locked=True))
    core_rooms = _place_core_rooms(layout["lot"], core_rect, entrance)
    layout["features"].extend(core_rooms)

    # 4) Private rooms
    room_counts = _count_rooms(constraints)
    private_rooms = _place_private_rooms(core_rect, core_rooms[-1], room_counts) if core_rooms else []
    layout["features"].extend(private_rooms)

    # 5) Validate; if fails, attempt one simple repair: shrink private rooms by 10% and retry
    ok, errs = validate_layout_json(layout)
    if not ok:
        # Simple repair: shrink bathrooms first, then bedrooms a bit
        repaired = False
        for f in layout["features"]:
            if "bath" in f["type"].lower():
                f["width"] *= 0.9
                f["height"] *= 0.9
                repaired = True
        ok2, errs2 = validate_layout_json(layout)
        if not ok2:
            for f in layout["features"]:
                if "bedroom" in f["type"].lower():
                    f["width"] *= 0.95
                    f["height"] *= 0.95
                    repaired = True
            ok3, errs3 = validate_layout_json(layout)
            if not ok3:
                # Return conflicts with suggestions
                return {
                    "error": "Layout generation failed",
                    "conflicts": errs3,
                    "suggestions": [
                        "Reduce bathroom sizes by 10–20%",
                        "Reduce bedroom sizes slightly",
                        "Relax entrance position or shrink fixed features (park/pool)"
                    ]
                }

    return layout
