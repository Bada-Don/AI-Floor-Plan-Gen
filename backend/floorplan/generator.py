import math, random, io
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from collections import deque, namedtuple

Cell = namedtuple("Cell", ["x", "y"])

# === Grid and Room Definitions ===
class Grid:
    def __init__(self, width_ft, height_ft, cell_ft=2):
        self.cell = cell_ft
        self.cols = int(width_ft // cell_ft)
        self.rows = int(height_ft // cell_ft)

class RoomSpec:
    def __init__(self, name, room_type, area_ft2=None, min_area_ft2=None, prefs=None, priority=5):
        self.name = name
        self.type = room_type
        self.area = area_ft2
        self.min_area = min_area_ft2
        self.prefs = prefs or {}
        self.priority = priority

class PlacedRoom:
    def __init__(self, spec:RoomSpec, x, y, w, h, zone="private"):
        self.spec = spec
        self.name = spec.name
        self.type = spec.type
        self.x, self.y, self.w, self.h, self.zone = x, y, w, h, zone

    def cells(self):
        for i in range(self.x, self.x+self.w):
            for j in range(self.y, self.y+self.h):
                yield (i, j)

DEFAULT_MIN_SIZES = {
    "bedroom": (10, 10),
    "master": (12, 12),
    "bathroom": (5, 6),
    "kitchen": (8, 8),
    "living": (12, 12),
    "entrance": (6, 4),
    "park": (10, 10),
    "pool": (10, 10)
}

# === Utility ===
def ft_to_cells(dim_ft, cell_ft=2):
    return max(1, int(round(dim_ft / cell_ft)))

def area_to_wh_cells(area_ft2, cell_ft=2, preferred_aspect=1.2):
    cells = max(1, int(round(area_ft2 / (cell_ft * cell_ft))))
    h = max(1, int(round(math.sqrt(cells / preferred_aspect))))
    w = max(1, int(round(cells / h)))
    return w, h

# === Main Generator ===
class FloorPlanGenerator:
    def __init__(self, plot_w_ft, plot_h_ft, cell_ft=2):
        self.grid = Grid(plot_w_ft, plot_h_ft, cell_ft)
        self.cell_ft = cell_ft
        self.placed = []
        self.occupied = [[None] * self.grid.rows for _ in range(self.grid.cols)]

    def mark_occupy(self, room):
        for (x, y) in room.cells():
            if 0 <= x < self.grid.cols and 0 <= y < self.grid.rows:
                self.occupied[x][y] = room.name

    def check_space_free(self, x, y, w, h):
        if x < 0 or y < 0 or x + w > self.grid.cols or y + h > self.grid.rows:
            return False
        for i in range(x, x + w):
            for j in range(y, y + h):
                if self.occupied[i][j] is not None:
                    return False
        return True

    def place_room(self, spec, x, y, w, h, zone="private"):
        room = PlacedRoom(spec, x, y, w, h, zone)
        self.placed.append(room)
        self.mark_occupy(room)

    def generate(self, constraints):
        # Step 1 — Reserve fixed features
        for feature in constraints.get("features", []):
            ftype = feature["type"]
            w_ft, h_ft = DEFAULT_MIN_SIZES.get(ftype, (10, 10))
            if "width" in feature: w_ft = feature["width"]
            if "height" in feature: h_ft = feature["height"]
            w, h = ft_to_cells(w_ft, self.cell_ft), ft_to_cells(h_ft, self.cell_ft)
            if feature["zone"] == "left":
                x, y = 0, 0
            elif feature["zone"] == "right":
                x, y = self.grid.cols - w, 0
            elif feature["zone"] == "middle":
                x, y = (self.grid.cols // 2 - w // 2), (self.grid.rows // 2 - h // 2)
            else:
                x, y = 0, 0
            spec = RoomSpec(ftype.capitalize(), ftype, area_ft2=w_ft*h_ft)
            self.place_room(spec, x, y, w, h, zone="public")

        # Step 2 — Place other rooms (very simplified here)
        for room in constraints.get("rooms", []):
            rtype = room["type"]
            count = room.get("count", 1)
            min_w, min_h = DEFAULT_MIN_SIZES.get(rtype, (8, 8))
            w, h = ft_to_cells(min_w, self.cell_ft), ft_to_cells(min_h, self.cell_ft)
            for i in range(count):
                for x in range(self.grid.cols):
                    for y in range(self.grid.rows):
                        if self.check_space_free(x, y, w, h):
                            spec = RoomSpec(f"{rtype.capitalize()} {i+1}", rtype, area_ft2=min_w*min_h)
                            self.place_room(spec, x, y, w, h, zone="private")
                            break
                    else:
                        continue
                    break

    def render_svg(self, title="Floor Plan"):
        cols, rows = self.grid.cols, self.grid.rows
        fig, ax = plt.subplots(figsize=(cols/4, rows/4))
        ax.set_xlim(0, cols)
        ax.set_ylim(0, rows)
        ax.set_aspect("equal")
        ax.axis("off")

        color_map = {"public": "#98FB98", "private": "#87CEEB", "service": "#FFA07A"}

        for r in self.placed:
            rect = patches.Rectangle((r.x, r.y), r.w, r.h,
                                     facecolor=color_map.get(r.zone, "#DDD"),
                                     edgecolor="black", linewidth=1.1)
            ax.add_patch(rect)
            ax.text(r.x + r.w/2, r.y + r.h/2, r.name, ha="center", va="center", fontsize=7, wrap=True)

        plt.gca().invert_yaxis()
        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format="svg")
        plt.close(fig)
        buf.seek(0)
        return buf.getvalue().decode("utf-8")
