import random
from typing import Dict, List, Tuple

# ========== MOCK NLU ==========
def parse_freeform(text: str) -> Dict:
    """
    Very simple parser that extracts:
    - Plot size
    - Rooms/features
    - Positions
    """
    constraints = {
        "plot": {"width": 50, "height": 50},  # default in feet
        "features": []
    }

    # Extract plot size
    if "plot size" in text.lower():
        try:
            size_part = text.lower().split("plot size")[1].split(",")[0].strip()
            w, h = [float(x.lower().replace("feet", "").strip()) for x in size_part.split("x")]
            constraints["plot"]["width"] = w
            constraints["plot"]["height"] = h
        except:
            pass

    # Rooms detection
    if "bedroom" in text.lower():
        num_bed = int(text.lower().split("bedroom")[0].split()[-1])
        for _ in range(num_bed):
            constraints["features"].append({"type": "bedroom", "width": 12, "height": 12})
    if "kitchen" in text.lower():
        constraints["features"].append({"type": "kitchen", "width": 10, "height": 10})
    if "hall" in text.lower():
        constraints["features"].append({"type": "hall", "width": 15, "height": 12})
    if "park" in text.lower():
        constraints["features"].append({"type": "park", "width": 15, "height": 20, "zone": "left"})
    if "pool" in text.lower():
        constraints["features"].append({"type": "pool", "width": 12, "height": 20, "zone": "right"})
    if "entrance" in text.lower():
        constraints["features"].append({"type": "entrance", "width": 5, "height": 5, "zone": "middle"})

    return constraints


# ========== GENERATOR ==========
def generate_layout(constraints: Dict) -> Dict:
    plot_w = constraints["plot"]["width"]
    plot_h = constraints["plot"]["height"]

    placed = []
    occupied = set()

    for feat in constraints["features"]:
        # Simple placement: try random positions until it fits without overlap
        for _ in range(100):
            if feat.get("zone") == "left":
                x = random.uniform(0, plot_w / 3)
            elif feat.get("zone") == "right":
                x = random.uniform(plot_w * 2 / 3, plot_w - feat["width"])
            elif feat.get("zone") == "middle":
                x = (plot_w - feat["width"]) / 2
            else:
                x = random.uniform(0, plot_w - feat["width"])

            y = random.uniform(0, plot_h - feat["height"])

            if not overlaps(x, y, feat["width"], feat["height"], occupied):
                mark_occupied(x, y, feat["width"], feat["height"], occupied)
                placed.append({**feat, "x": x, "y": y})
                break

    return {
        "lot": {"width": plot_w, "height": plot_h},
        "features": placed,
        "svg": render_svg(plot_w, plot_h, placed)
    }


# ========== VALIDATION ==========
def overlaps(x: float, y: float, w: float, h: float, occupied: set) -> bool:
    for i in range(int(x), int(x + w)):
        for j in range(int(y), int(y + h)):
            if (i, j) in occupied:
                return True
    return False

def mark_occupied(x: float, y: float, w: float, h: float, occupied: set):
    for i in range(int(x), int(x + w)):
        for j in range(int(y), int(y + h)):
            occupied.add((i, j))


# ========== RENDERER ==========
def render_svg(plot_w: float, plot_h: float, features: List[Dict]) -> str:
    svg_parts = [f'<svg width="{plot_w*10}" height="{plot_h*10}" xmlns="http://www.w3.org/2000/svg">']
    svg_parts.append(f'<rect x="0" y="0" width="{plot_w*10}" height="{plot_h*10}" fill="white" stroke="black"/>')

    colors = {
        "bedroom": "lightblue",
        "kitchen": "lightgreen",
        "hall": "khaki",
        "park": "palegreen",
        "pool": "skyblue",
        "entrance": "gray"
    }

    for feat in features:
        color = colors.get(feat["type"], "lightgray")
        svg_parts.append(
            f'<rect x="{feat["x"]*10}" y="{feat["y"]*10}" width="{feat["width"]*10}" height="{feat["height"]*10}" fill="{color}" stroke="black"/>'
        )
        svg_parts.append(
            f'<text x="{(feat["x"]+1)*10}" y="{(feat["y"]+1)*10}" font-size="10">{feat["type"]}</text>'
        )

    svg_parts.append("</svg>")
    return "".join(svg_parts)


# ========== MAIN FOR TEST ==========
if __name__ == "__main__":
    user_text = "Plot size 50x50 feet, 2 bedrooms, 1 kitchen, park on left, pool on right, entrance in middle"
    constraints = parse_freeform(user_text)
    layout = generate_layout(constraints)
    print(layout["svg"])  # You can write this to an .svg file to see it
