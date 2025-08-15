# floorplan/generator.py
import math, random, io, base64
import matplotlib
matplotlib.use("Agg") # Use non-GUI backend for server environment
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from collections import deque, namedtuple
from typing import Dict, Any, List, Tuple

# === Core Definitions from Engine 1 ===
Cell = namedtuple("Cell", ["x","y"])

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
        self.x = x; self.y = y; self.w = w; self.h = h; self.zone = zone
    def cells(self):
        for i in range(self.x, self.x+self.w):
            for j in range(self.y, self.y+self.h):
                yield (i,j)
    def bbox(self):
        return (self.x, self.y, self.x+self.w-1, self.y+self.h-1)

DEFAULT_MIN_SIZES = {
    "bedroom": (10,10),
    "master": (12,12),
    "bathroom": (5,6),
    "kitchen": (8,8),
    "living": (12,12),
    "entrance": (6,4),
    "hallway": (4, 4),
}

def ft_to_cells(dim_ft, cell_ft=2):
    return max(1, int(round(dim_ft / cell_ft)))

def area_to_wh_cells(area_ft2, cell_ft=2, preferred_aspect=1.2):
    cells = max(1, int(round(area_ft2 / (cell_ft*cell_ft))))
    h = max(1, int(round(math.sqrt(cells / preferred_aspect))))
    w = max(1, int(round(cells / h)))
    return w, h

# === Floor Plan Generator Class ===
class FloorPlanGenerator:
    def __init__(self, plot_w_ft, plot_h_ft, cell_ft=2, verbose=False):
        self.grid = Grid(plot_w_ft, plot_h_ft, cell_ft)
        self.cell_ft = cell_ft
        self.placed = []
        self.occupied = [[None]*self.grid.rows for _ in range(self.grid.cols)]
        self.verbose = verbose

    # (Validation, marking, checking space free, scoring, placing, removing rooms - all from Engine 1)
    # ... (omitted for brevity, assume the full implementation of these methods from Engine 1) ...

    def validate(self, meta):
        # [Engine 1: Full validation logic here]
        rooms = self.placed
        room_map = {}
        private_cells = set()
        for r in rooms:
            for c in r.cells():
                room_map[c] = r
                if r.zone=="private":
                    private_cells.add(c)
        entrance = meta.get("entrance_cell")
        if not entrance:
            # If no entrance spec, find the entrance placed
            ent_room = next((r for r in self.placed if r.type=="entrance"), None)
            if ent_room:
                 entrance = (ent_room.x + ent_room.w//2, ent_room.y + ent_room.h//2)
                 meta["entrance_cell"] = entrance
            else:
                return False, "No entrance provided"

        cols, rows = self.grid.cols, self.grid.rows
        q = deque([entrance]); seen=set([entrance]); reachable=set()
        while q:
            x,y = q.popleft()
            if (x,y) in room_map:
                reachable.add(room_map[(x,y)].name)
            for dx,dy in [(1,0),(-1,0),(0,1),(0,-1)]:
                nx,ny = x+dx, y+dy
                if not (0<=nx<cols and 0<=ny<rows): continue
                if (nx,ny) in seen: continue
                if (nx,ny) in private_cells: continue
                seen.add((nx,ny)); q.append((nx,ny))
        public_rooms = [r.name for r in rooms if r.zone=="public"]
        if not any(p in reachable for p in public_rooms):
            return False, "Entrance cannot reach public areas"
        names = {r.name:r for r in rooms}
        if "Kitchen" in names and "Living/Dining" in names:
            k = names["Kitchen"]; ld = names["Living/Dining"]
            adj=False
            ld_cells = set(ld.cells())
            for (x,y) in k.cells():
                for dx,dy in [(1,0),(-1,0),(0,1),(0,-1)]:
                    if (x+dx,y+dy) in ld_cells:
                        adj=True; break
                if adj: break
            if not adj:
                return False, "Kitchen not adjacent to Living/Dining"
        baths = [r for r in rooms if "Bath" in r.name or "Bathroom" in r.name]
        for b in baths:
            for (x,y) in b.cells():
                if abs(x-entrance[0])+abs(y-entrance[1]) <= 3:
                    return False, "Bathroom too close to entrance"
            if b.zone=="public":
                return False, "Bathroom marked public"
        rooms_by_cell = room_map
        for r in rooms:
            connected=False
            for (x,y) in r.cells():
                for dx,dy in [(1,0),(-1,0),(0,1),(0,-1)]:
                    nx,ny = x+dx, y+dy
                    if not (0<=nx<self.grid.cols and 0<=ny<self.grid.rows): continue
                    if (nx,ny) not in rooms_by_cell:
                        connected=True; break
                    rr = rooms_by_cell[(nx,ny)]
                    if rr.zone!="private" or rr.name==r.name:
                        connected=True; break
                if connected: break
            if not connected:
                return False, f"Room {r.name} isolated (no circulation adjacency)"
        return True, "Layout valid"

    def mark_occupy(self, room):
        for (x,y) in room.cells():
            self.occupied[x][y] = room.name

    def unmark_occupy(self, pr):
        for (x,y) in pr.cells():
            if self.occupied[x][y]==pr.name:
                self.occupied[x][y] = None

    def check_space_free(self, x,y,w,h):
        if x<0 or y<0 or x+w>self.grid.cols or y+h>self.grid.rows: return False
        for i in range(x,x+w):
            for j in range(y,y+h):
                if self.occupied[i][j] is not None: return False
        return True

    def score_candidate(self, spec, x,y,w,h, meta):
        score = 0
        if spec.prefs.get("prefer_corner") and (x==0 or y==0 or x+w==self.grid.cols or y+h==self.grid.rows):
            score += 5
        entrance = meta.get("entrance_cell")
        if spec.type in ("bedroom","master") and entrance:
            min_dist = min(abs(cx-entrance[0])+abs(cy-entrance[1]) for cx in range(x,x+w) for cy in range(y,y+h))
            score += min_dist
        perim = 2*(w+h); area = max(1,w*h)
        score -= 0.2*(perim/area)
        return score

    def place_room(self, spec, x,y,w,h, zone="private"):
        pr = PlacedRoom(spec, x,y,w,h, zone=zone)
        self.placed.append(pr)
        self.mark_occupy(pr)
        return pr

    def remove_room(self, pr):
        if pr in self.placed:
            self.placed.remove(pr)
        self.unmark_occupy(pr)

    def generate(self, specs, entrance_side="south"):
        # [Engine 1: Full generation logic]
        
        target_dims = {}
        for s in specs:
            if s.area:
                w,h = area_to_wh_cells(s.area, self.cell_ft)
            else:
                mn = s.min_area or DEFAULT_MIN_SIZES.get(s.type, (8,8))
                w,h = area_to_wh_cells(mn[0]*mn[1], self.cell_ft)
            minw = ft_to_cells((s.min_area and math.sqrt(s.min_area) or DEFAULT_MIN_SIZES.get(s.type,(8,8))[0]), self.cell_ft)
            minh = minw
            w = max(w, minw); h = max(h, minh)
            target_dims[s.name] = (w,h)

        def priority_key(s):
            order = {"entrance":0,"living":1,"kitchen":2,"hallway":3,"master":4,"bedroom":5,"bathroom":6}
            return order.get(s.type, 10), s.priority
        specs_sorted = sorted(specs, key=priority_key)
        
        cols, rows = self.grid.cols, self.grid.rows
        meta = {}
        
        # Place entrance
        entrance_spec = next((s for s in specs_sorted if s.type=="entrance"), None)
        if entrance_spec:
            ew,eh = target_dims[entrance_spec.name]
            ex = cols//2 - ew//2
            if entrance_side in ("south","north"):
                ey = rows - eh if entrance_side=="south" else 0
            else:
                ey = rows//2 - eh//2
                ex = 0 if entrance_side=="west" else cols-ew
            ent = self.place_room(entrance_spec, ex, ey, ew, eh, zone="public")
            meta["entrance_cell"] = (ex+ew//2, ey+eh//2)
        
        # Place Living/Dining
        living_spec = next((s for s in specs_sorted if s.type=="living"), None)
        if living_spec:
            lw,lh = target_dims[living_spec.name]
            candidates = []
            
            if entrance_spec and entrance_side=="south":
                base_x = ent.x - (lw//2)
                search_x = range(max(0,base_x-2), min(cols-lw+1, base_x+3))
                search_y = range(max(0, ent.y-lh-3), max(0, ent.y-lh+1))
                for x in search_x:
                    for y in search_y:
                        if self.check_space_free(x,y,lw,lh):
                            candidates.append((x,y))

            if not candidates:
                for x in range(0, cols-lw+1):
                    for y in range(0, rows-lh+1):
                        if self.check_space_free(x,y,lw,lh):
                            candidates.append((x,y))

            best=None; bscore=-1e9
            for (x,y) in candidates:
                sc = self.score_candidate(living_spec,x,y,lw,lh,meta)
                if sc>bscore: bscore=sc; best=(x,y)
            if best:
                self.place_room(living_spec,best[0],best[1],lw,lh, zone="public")
        
        # Place Kitchen
        kitchen_spec = next((s for s in specs_sorted if s.type=="kitchen"), None)
        if kitchen_spec and any(r for r in self.placed if r.type=="living"):
            lw_room = next(r for r in self.placed if r.type=="living")
            kw,kh = target_dims[kitchen_spec.name]
            candidates=[]
            for (x,y) in lw_room.cells():
                for dx,dy in [(1,0),(-1,0),(0,1),(0,-1)]:
                    nx,ny = x+dx, y+dy
                    ax = nx; ay = ny - (kh//2)
                    for ox in range(-1,2):
                        for oy in range(-1,2):
                            ax2 = ax+ox; ay2 = ay+oy
                            if self.check_space_free(ax2,ay2,kw,kh):
                                candidates.append((ax2,ay2))
            
            if not candidates:
                for x in range(0, cols-kw+1):
                    for y in range(0, rows-kh+1):
                        if self.check_space_free(x,y,kw,kh):
                            candidates.append((x,y))
            
            best=None; bscore=-1e9
            for (x,y) in candidates:
                sc = self.score_candidate(kitchen_spec,x,y,kw,kh,meta)
                if sc>bscore: bscore=sc; best=(x,y)
            if best:
                self.place_room(kitchen_spec,best[0],best[1],kw,kh, zone="service")

        # Reserve hallway band
        hall_h = max(1, math.ceil(3/self.cell_ft))
        hall_y = max(0, int(self.grid.rows*0.45)-hall_h//2)
        hallway_spec = next((s for s in specs_sorted if s.type=="hallway"), None)
        if hallway_spec:
            hw,hh = self.grid.cols, hall_h
            if self.check_space_free(0,hall_y,hw,hh):
                self.place_room(hallway_spec, 0, hall_y, hw, hh, zone="public")
            else:
                placed_h=False
                for y in range(0, self.grid.rows-hh+1):
                    if self.check_space_free(0,y,hw,hh):
                        self.place_room(hallway_spec,0,y,hw,hh, zone="public"); placed_h=True; break

        # Place private rooms
        private_specs = [s for s in specs_sorted if s.type in ("master","bedroom")]
        for s in private_specs:
            w,h = target_dims[s.name]
            candidates=[]
            hall = next((r for r in self.placed if r.type=="hallway"), None)
            if hall:
                hy = hall.y; hh = hall.h
                search_y = range(max(0, hy - h), max(0, hy+1))
                for x in range(0, self.grid.cols - w +1):
                    for y in search_y:
                        if self.check_space_free(x,y,w,h):
                            candidates.append((x,y))

            if not candidates:
                for x in range(0, self.grid.cols - w +1):
                    for y in range(0, self.grid.rows - h +1):
                        if self.check_space_free(x,y,w,h):
                            candidates.append((x,y))

            best=None; bscore=-1e9
            for (x,y) in candidates:
                sc = self.score_candidate(s,x,y,w,h,meta)
                if sc>bscore: bscore=sc; best=(x,y)
            if best:
                self.place_room(s, best[0], best[1], w, h, zone="private")

        # Place bathrooms
        bath_specs = [s for s in specs_sorted if s.type=="bathroom"]
        for bspec in bath_specs:
            bw,bh = target_dims[bspec.name]
            candidates=[]
            bedrooms = [r for r in self.placed if r.type in ("bedroom","master")]
            for bd in bedrooms:
                for (x,y) in bd.cells():
                    for dx,dy in [(1,0),(-1,0),(0,1),(0,-1)]:
                        nx,ny = x+dx, y+dy
                        ax = nx; ay = ny - (bh//2)
                        if self.check_space_free(ax,ay,bw,bh):
                            candidates.append((ax,ay))

            if not candidates:
                for x in range(0, self.grid.cols-bw+1):
                    for y in range(0, self.grid.rows-bh+1):
                        if self.check_space_free(x,y,bw,bh):
                            candidates.append((x,y))
            
            best=None; bscore=-1e9
            for (x,y) in candidates:
                sc = self.score_candidate(bspec,x,y,bw,bh,meta)
                if sc>bscore: bscore=sc; best=(x,y)
            if best:
                self.place_room(bspec,best[0],best[1],bw,bh, zone="private")
        
        # Final validation and repair attempts (from Engine 1)
        valid, msg = self.validate(meta)
        attempts = 0
        MAX_ATTEMPTS = 300
        while not valid and attempts < MAX_ATTEMPTS:
            # [Engine 1: Repair logic (nudges & swaps)]
            attempts += 1
            # (simplified repair logic for context)
            
            candidates = [r for r in self.placed if r.spec.type not in ("entrance","hallway")]
            if not candidates: break
            r = random.choice(candidates)
            
            self.remove_room(r)
            # Try a random nudge
            dx, dy = random.choice([-2,-1,0,1,2]), random.choice([-2,-1,0,1,2])
            nx, ny = r.x+dx, r.y+dy

            nudged_room = None
            if self.check_space_free(nx,ny,r.w,r.h):
                nudged_room = self.place_room(r.spec, nx, ny, r.w, r.h, zone=r.zone)
                valid, msg = self.validate(meta)
                if valid:
                    break
            
            # Revert if the nudge was unsuccessful
            if nudged_room:
                self.remove_room(nudged_room)

            # Put the original room back and try another repair
            self.place_room(r.spec, r.x, r.y, r.w, r.h, zone=r.zone)

        return valid, msg, meta

    # --- Backend-specific Rendering ---
    def render_base64(self, title="Floor Plan"):
        # [Engine 1: Matplotlib rendering logic]
        cols, rows = self.grid.cols, self.grid.rows
        fig, ax = plt.subplots(figsize=(cols/4, rows/4))
        
        # Draw grid and rooms
        # ... (visualization code from Engine 1) ...
        
        color_map = {"public":"#98FB98","private":"#87CEEB","service":"#FFA07A"}
        for r in self.placed:
            rect = patches.Rectangle((r.x, r.y), r.w, r.h, facecolor=color_map.get(r.zone,"#DDD"), edgecolor="black", linewidth=1.1)
            ax.add_patch(rect)
            ax.text(r.x + r.w/2, r.y + r.h/2, r.name, ha="center", va="center", fontsize=7, wrap=True)
        
        ent = next((r for r in self.placed if r.type=="entrance"), None)
        if ent:
            ex,ey = ent.x + ent.w//2, ent.y + ent.h//2
            ax.plot(ex+0.2, ey+0.2, marker="o", color="red")
            ax.text(ex+0.8, ey+0.8, "Entrance", fontsize=7, color="red")

        ax.set_xlim(0, cols); ax.set_ylim(0, rows); ax.set_aspect("equal"); ax.axis("off")
        ax.set_title(title, fontsize=12, fontweight="bold")
        plt.gca().invert_yaxis()
        
        # Save to buffer and encode to base64
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        
        return base64.b64encode(buf.getvalue()).decode('utf-8')


# --- Adapter Function: Translating Constraints to RoomSpecs ---
def generate_layout_from_constraints(constraints: Dict[str, Any]) -> Tuple[Dict[str, Any], Any]:
    lot = constraints.get("plot", {})
    plot_w = lot.get("width", 0)
    plot_h = lot.get("height", 0)

    if not plot_w or not plot_h:
        return {"error": "Invalid plot dimensions provided by AI. Plot width or height is zero."}, None

    specs = []
    entrance_side = "south"
    
    # Combine rooms and features, and keep track of types we've added to avoid duplicates
    all_items = (constraints.get("rooms", []) or []) + (constraints.get("features", []) or [])
    processed_room_types = set()

    room_id_counter = {"entrance": 0, "living": 0, "kitchen": 0, "hallway": 0, "master": 0, "bedroom": 0, "bathroom": 0, "other": 0}

    for item_data in all_items:
        original_rtype = item_data.get("type", "other").lower()
        
        # Normalize the room type
        normalized_rtype = original_rtype
        if "living" in original_rtype: normalized_rtype = "living"
        elif "master" in original_rtype: normalized_rtype = "master"
        elif "bed" in original_rtype: normalized_rtype = "bedroom"
        elif "bath" in original_rtype: normalized_rtype = "bathroom"
        elif "kitchen" in original_rtype: normalized_rtype = "kitchen"
        elif "entrance" in original_rtype: normalized_rtype = "entrance"
        elif "hall" in original_rtype: normalized_rtype = "hallway"
        
        if normalized_rtype not in room_id_counter:
            continue # Skip unknown types from the 'features' list like zones

        # --- FIX: Prevent adding duplicate rooms (like two kitchens) ---
        if normalized_rtype in processed_room_types and item_data.get("count") is None:
            continue
        
        count = int(item_data.get("count", 1))
        
        for i in range(count):
            room_id_counter[normalized_rtype] += 1
            name = f"{normalized_rtype.capitalize()} {room_id_counter[normalized_rtype]}"
            
            area = item_data.get("area")
            if not area:
                min_dims = DEFAULT_MIN_SIZES.get(normalized_rtype)
                area = min_dims[0] * min_dims[1] if min_dims else 100

            specs.append(RoomSpec(name=name, room_type=normalized_rtype, area_ft2=area))
        
        processed_room_types.add(normalized_rtype)

    # --- FIX: Add a default entrance if the AI forgets ---
    if "entrance" not in processed_room_types:
        print("AI response missing entrance, adding a default one.")
        specs.insert(0, RoomSpec(name="Entrance 1", room_type="entrance", area_ft2=30, priority=0))

    # The rest of the function continues as before
    gen = FloorPlanGenerator(plot_w, plot_h)
    ok, msg, meta = gen.generate(specs, entrance_side=entrance_side)
    
    if not ok:
        return {"error": msg}, gen.placed

    image_base64 = gen.render_base64()
    
    return {
        "lot": lot,
        "features": gen.placed,
        "image_base64": image_base64,
        "status": "ok",
        "message": msg
    }, gen.placed
