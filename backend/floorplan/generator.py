# floorplan/generator.py
import math, random, io, base64
import matplotlib
matplotlib.use("Agg") # Use non-GUI backend for server environment
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from collections import deque, namedtuple
from typing import Dict, Any, List, Tuple

# === Core Definitions ===
Cell = namedtuple("Cell", ["x","y"])
ZONE_ADJACENCY_PREFERENCES = { "public": {"public": 1.0, "service": 0.7, "private": -0.5}, "service": {"service": 1.0, "public": 0.8, "private": 0.3}, "private": {"private": 0.9, "public": -0.3, "service": 0.1} }
DEFAULT_MIN_SIZES = { "bedroom": (10, 10), "master": (12, 13), "bathroom": (5, 8), "kitchen": (10, 10), "living": (12, 15), "entrance": (6, 5) }

class Grid:
    def __init__(self, width_ft, height_ft, cell_ft=1): self.cell, self.cols, self.rows = cell_ft, int(width_ft // cell_ft), int(height_ft // cell_ft)
class RoomSpec:
    def __init__(self, name, room_type, area_ft2=None, prefs=None, priority=5): self.name, self.type, self.area, self.prefs, self.priority = name, room_type, area_ft2, prefs or {}, priority
class PlacedRoom:
    def __init__(self, spec:RoomSpec, x, y, w, h, zone="private"): self.spec, self.name, self.type, self.x, self.y, self.w, self.h, self.zone = spec, spec.name, spec.type, x, y, w, h, zone
    def cells(self):
        for i in range(self.x, self.x+self.w):
            for j in range(self.y, self.y+self.h): yield (i,j)
    @property
    def area_sq_ft(self): return self.w * self.h
    def bbox(self): return (self.x, self.y, self.w, self.h)

def area_to_wh_cells(area_ft2, cell_ft=1, preferred_aspect=1.2):
    cells = max(1, int(round(area_ft2/(cell_ft*cell_ft)))); h = max(1, int(round(math.sqrt(cells/preferred_aspect)))); w = max(1, int(round(cells/h))); return w, h

# === Floor Plan Generator Class ===
class FloorPlanGenerator:
    def __init__(self, plot_w_ft, plot_h_ft, cell_ft=1, verbose=False):
        self.grid = Grid(plot_w_ft, plot_h_ft, cell_ft)
        self.cell_ft, self.placed, self.verbose = cell_ft, [], verbose
        self.occupied = [[None]*self.grid.rows for _ in range(self.grid.cols)]

    # --- Helper Methods ---
    def get_room_by_type(self, rtype): return next((r for r in self.placed if r.type == rtype), None)
    def get_room_by_name(self, name): return next((r for r in self.placed if r.name == name), None)
    def get_room_zone(self, rtype):
        if rtype in ("living", "entrance"): return "public"
        if rtype == "kitchen": return "service"
        return "private"
    def find_adjacent_positions(self, ref, w, h):
        pos = []; y=ref.y-h; [pos.append((x,y)) for x in range(ref.x-w+1, ref.x+ref.w)]; y=ref.y+ref.h; [pos.append((x,y)) for x in range(ref.x-w+1, ref.x+ref.w)]; x=ref.x-w; [pos.append((x,y)) for y in range(ref.y-h+1, ref.y+ref.h)]; x=ref.x+ref.w; [pos.append((x,y)) for y in range(ref.y-h+1, ref.y+ref.h)]; return [(x,y) for x,y in pos if self.check_space_free(x,y,w,h)]
    def calculate_room_distance(self, bbox1, room2):
        x1, y1, w1, h1 = bbox1; x2_c, y2_c = room2.x + room2.w/2, room2.y + room2.h/2
        dist_x = max(0, abs(x1 + w1/2 - x2_c) - (w1/2 + room2.w/2)); dist_y = max(0, abs(y1 + h1/2 - y2_c) - (h1/2 + room2.h/2)); return math.sqrt(dist_x**2 + dist_y**2)
    def calculate_shared_wall_length(self, room1, room2):
        shared = 0; r1_cells, r2_cells = set(room1.cells()), set(room2.cells())
        for x, y in r1_cells:
            if any((x+dx, y+dy) in r2_cells for dx, dy in [(1,0),(-1,0),(0,1),(0,-1)]): shared += 1
        return shared
    def has_exterior_access(self, room): return room.x==0 or room.y==0 or room.x+room.w>=self.grid.cols or room.y+room.h>=self.grid.rows
    def check_space_free(self, x,y,w,h):
        if x<0 or y<0 or x+w>self.grid.cols or y+h>self.grid.rows: return False
        for i in range(x,x+w):
            for j in range(y,y+h):
                if self.occupied[i][j] is not None: return False
        return True
    def mark_occupy(self, room):
        for (x,y) in room.cells(): self.occupied[x][y] = room.name
    def unmark_occupy(self, pr):
        for (x,y) in pr.cells():
            if self.occupied[x][y]==pr.name: self.occupied[x][y] = None
    def place_room(self, spec, x,y,w,h, zone):
        pr = PlacedRoom(spec, x,y,w,h, zone=zone); self.placed.append(pr); self.mark_occupy(pr); return pr
    def remove_room(self, pr):
        if pr in self.placed: self.placed.remove(pr)
        self.unmark_occupy(pr)

    # --- Strategic Placement & Scoring ---
    def score_candidate(self, spec, x, y, w, h, meta):
        score = 0; aspect = max(w,h)/max(1,min(w,h)); score -= 10*(aspect-2.0) if aspect > 2.0 else 0
        ext_len = (h if x==0 else 0)+(w if y==0 else 0)+(h if x+w>=self.grid.cols else 0)+(w if y+h>=self.grid.rows else 0)
        if spec.type in ("living", "bedroom", "master"): score += ext_len*1.5
        if spec.type == "kitchen":
            living = self.get_room_by_type("living"); score += max(0, 15 - self.calculate_room_distance((x,y,w,h), living)) if living else 0
        return score
    def _find_placement_candidates(self, spec, w, h, meta):
        cands = []
        if spec.type == "entrance":
            y = self.grid.rows-h if meta.get("entrance_side")=="south" else 0; [cands.append((x,y)) for x in range(int(self.grid.cols*0.25),int(self.grid.cols*0.75-w))]
        elif spec.type == "living":
            ent = self.get_room_by_type("entrance"); cands.extend(self.find_adjacent_positions(ent, w, h)) if ent else None
        elif spec.type == "kitchen":
            liv = self.get_room_by_type("living"); cands.extend(self.find_adjacent_positions(liv, w, h)) if liv else None
        if not cands:
            for x in range(0, self.grid.cols-w+1, 2):
                for y in range(0, self.grid.rows-h+1, 2):
                    if self.check_space_free(x,y,w,h): cands.append((x,y))
        return cands

    # --- Validation Modules ---
    def validate_room_proportions(self):
        issues = []
        for r in self.placed:
            aspect = max(r.w, r.h) / max(1, min(r.w, r.h))
            max_aspect = {"bathroom": 2.5, "kitchen": 2.5, "bedroom": 2.0, "living": 2.0, "master": 1.8}.get(r.type, 2.0)
            if aspect > max_aspect: issues.append(f"'{r.name}' has poor proportions")
            min_dim = min(r.w, r.h); req_min = {"bathroom": 5, "bedroom": 8, "kitchen": 8, "living": 10, "master": 10}.get(r.type, 4)
            if min_dim < req_min: issues.append(f"'{r.name}' too narrow")
        return issues
    def validate_circulation(self, meta):
        issues = []; entrance = self.get_room_by_type("entrance")
        if not entrance: return ["No entrance placed"]
        starts = [] # FIX: Handle all wall positions
        if entrance.y + entrance.h >= self.grid.rows: starts = [(entrance.x + i, entrance.y) for i in range(entrance.w)]
        elif entrance.y == 0: starts = [(entrance.x + i, entrance.y + entrance.h - 1) for i in range(entrance.w)]
        elif entrance.x == 0: starts = [(entrance.x + entrance.w - 1, entrance.y + i) for i in range(entrance.h)]
        elif entrance.x + entrance.w >= self.grid.cols: starts = [(entrance.x, entrance.y + i) for i in range(entrance.h)]
        if not starts: starts = list(entrance.cells())
        
        q, visited, reachable = deque(starts), set(starts), {entrance.name}
        room_map = {c: r for r in self.placed for c in r.cells()}
        while q:
            x, y = q.popleft()
            for dx,dy in [(1,0),(-1,0),(0,1),(0,-1)]:
                nx,ny = x+dx, y+dy
                if (nx,ny) in visited or not(0<=nx<self.grid.cols and 0<=ny<self.grid.rows): continue
                if (nx,ny) in room_map:
                    neighbor = room_map[(nx,ny)]
                    if neighbor.zone == "private": continue
                    reachable.add(neighbor.name)
                visited.add((nx,ny)); q.append((nx,ny))
        for r in self.placed:
            if r.name not in reachable: issues.append(f"'{r.name}' is isolated")
        return issues
    def validate_comprehensive(self, meta):
        issues, names = [], {r.name: r for r in self.placed}
        for r in self.placed:
            min_dims = DEFAULT_MIN_SIZES.get(r.type)
            if min_dims and r.area_sq_ft < (min_dims[0]*min_dims[1]*0.9): issues.append(f"'{r.name}' is too small")
            if r.type in ("bedroom", "master") and not self.has_exterior_access(r): issues.append(f"'{r.name}' lacks emergency egress")
        if "Kitchen 1" in names and "Living/dining 1" in names:
            k, l = names["Kitchen 1"], names["Living/dining 1"]
            if self.calculate_shared_wall_length(k, l) < 3: issues.append("'Kitchen 1' not strongly adjacent to 'Living/dining 1'")
        issues.extend(self.validate_circulation(meta)); issues.extend(self.validate_room_proportions()); return issues

    # --- Repair Logic ---
    def _fix_adjacency(self, issue_str):
        if "'Kitchen 1'" not in issue_str or "'Living/dining 1'" not in issue_str: return False
        k, l = self.get_room_by_name("Kitchen 1"), self.get_room_by_name("Living/dining 1")
        if not k or not l: return False
        
        orig_k, orig_l = (k.x,k.y,k.w,k.h,k.zone), (l.x,l.y,l.w,l.h,l.zone)
        self.remove_room(k)
        
        for nw,nh in [(k.w,k.h), (k.h,k.w)]: # S1 & S2: Move/Rotate Kitchen
            for x,y in self.find_adjacent_positions(l, nw, nh):
                p = self.place_room(k.spec, x,y, nw, nh, k.zone)
                if self.calculate_shared_wall_length(p,l) >= 3: return True
                self.remove_room(p)
        
        self.place_room(k.spec, *orig_k); self.remove_room(l) # S3: Move Living
        for x,y in self.find_adjacent_positions(k, l.w, l.h):
            p = self.place_room(l.spec, x,y, l.w, l.h, l.zone)
            if self.calculate_shared_wall_length(k,p) >= 3: return True
            self.remove_room(p)
        self.place_room(l.spec, *orig_l) # Restore L

        min_k_area = DEFAULT_MIN_SIZES["kitchen"][0] * DEFAULT_MIN_SIZES["kitchen"][1] # S4: Shrink kitchen
        if k.area_sq_ft > min_k_area:
            self.remove_room(k); nw,nh = area_to_wh_cells(min_k_area)
            for x,y in self.find_adjacent_positions(l,nw,nh):
                p = self.place_room(k.spec,x,y,nw,nh,k.zone)
                if self.calculate_shared_wall_length(p,l) >= 3: return True
                self.remove_room(p)

        if not self.get_room_by_name(k.name): self.place_room(k.spec, *orig_k)
        return False
    def _intelligent_repair(self, issues, meta):
        for issue in issues:
            if "adjacent" in issue:
                if self._fix_adjacency(issue): return True
        return False

    # --- Main Generation Method ---
    def generate(self, specs, entrance_side="south"):
        target_dims = {} # FIX: Safe dictionary creation
        for s in specs:
            default = DEFAULT_MIN_SIZES.get(s.type, (10,10)); area = s.area or (default[0]*default[1]); target_dims[s.name] = area_to_wh_cells(area)
        
        priority = lambda s: ({"entrance":0,"living":1,"kitchen":2,"master":3,"bedroom":4,"bathroom":5}.get(s.type, 10), s.priority)
        specs_sorted, meta = sorted(specs, key=priority), {"entrance_side": entrance_side}

        for spec in specs_sorted:
            w, h = target_dims[spec.name]; zone = self.get_room_zone(spec.type)
            cands = self._find_placement_candidates(spec, w, h, meta)
            if not cands: continue
            
            scored = sorted([(x,y,self.score_candidate(spec,x,y,w,h,meta)) for x,y in cands], key=lambda i: i[2], reverse=True)
            best_cand = scored[0] if scored else None
            if best_cand: self.place_room(spec, best_cand[0], best_cand[1], w, h, zone=zone)

        # OPTIMIZATION: Early success check
        if not self.validate_comprehensive(meta): return True, "Layout valid (early success).", meta

        for _ in range(30): # Repair loop
            issues = self.validate_comprehensive(meta)
            if not issues: break
            if not self._intelligent_repair(issues, meta): # Fallback nudge
                r = random.choice([r for r in self.placed if r.type!='entrance']); self.remove_room(r)
                nx,ny = r.x+random.randint(-2,2), r.y+random.randint(-2,2)
                if self.check_space_free(nx,ny,r.w,r.h): self.place_room(r.spec,nx,ny,r.w,r.h,r.zone)
                else: self.place_room(r.spec,r.x,r.y,r.w,r.h,r.zone)

        final_issues = self.validate_comprehensive(meta); is_valid = not final_issues
        message = "Layout valid." if is_valid else f"Validation failed: {', '.join(list(set(final_issues)))}"
        return is_valid, message, meta

    def render_base64(self, title="Floor Plan"):
        cols, rows = self.grid.cols, self.grid.rows; fig, ax = plt.subplots(figsize=(cols/5, rows/5))
        colors = {"public":"#98FB98","private":"#87CEEB","service":"#FFA07A"}
        for r in self.placed:
            rect = patches.Rectangle((r.x,r.y),r.w,r.h,facecolor=colors.get(r.zone,"#DDD"),edgecolor="black",linewidth=1.1)
            ax.add_patch(rect); ax.text(r.x+r.w/2,r.y+r.h/2,f"{r.name}\n({r.area_sq_ft} sqft)",ha="center",va="center",fontsize=6,wrap=True)
        ent = self.get_room_by_type("entrance")
        if ent: ax.plot(ent.x+ent.w/2, ent.y+ent.h/2, 'o', color="red", markersize=8)
        ax.set_xlim(-1,cols+1); ax.set_ylim(-1,rows+1); ax.set_aspect("equal"); ax.axis("off"); ax.set_title(title,fontsize=12,fontweight="bold"); plt.gca().invert_yaxis()
        buf = io.BytesIO(); plt.savefig(buf, format='png', bbox_inches='tight'); plt.close(fig); buf.seek(0)
        return base64.b64encode(buf.getvalue()).decode('utf-8')

# --- Adapter Function ---
def generate_layout_from_constraints(constraints: Dict[str, Any]) -> Tuple[Dict[str, Any], Any]:
    lot = constraints.get("plot",{}); w,h = lot.get("width",0), lot.get("height",0)
    if not w or not h: return {"error": "Invalid plot dimensions."}, None
    specs, processed, counts = [], set(), {"bedroom":0, "bathroom":0}
    name_map = {"living": "Living/dining 1", "kitchen": "Kitchen 1", "entrance": "Entrance", "master": "Master bedroom"}
    for item in (constraints.get("rooms",[]) or [])+(constraints.get("features",[]) or []):
        rtype = item.get("type","other").lower()
        if "liv" in rtype or "din" in rtype: rtype="living"
        elif "master" in rtype: rtype="master"
        elif "bed" in rtype: rtype="bedroom"
        elif "bath" in rtype: rtype="bathroom"
        elif "kitch" in rtype: rtype="kitchen"
        elif "entran" in rtype: rtype="entrance"
        if rtype in processed and rtype not in counts: continue
        for _ in range(int(item.get("count",1))):
            if rtype in counts: counts[rtype]+=1
            name = name_map.get(rtype) or (f"{rtype.capitalize()} {counts[rtype]}" if rtype in counts else rtype.capitalize())
            area = item.get("area") or (DEFAULT_MIN_SIZES.get(rtype,(10,10))[0]*DEFAULT_MIN_SIZES.get(rtype,(10,10))[1])
            specs.append(RoomSpec(name, rtype, area)); processed.add(rtype)
    if "entrance" not in processed: specs.insert(0, RoomSpec("Entrance","entrance",40,priority=0))
    gen = FloorPlanGenerator(w,h)
    ok,msg,meta = gen.generate(specs, "south")
    return {"lot":lot,"features":gen.placed,"image_base64":gen.render_base64(),"status":"ok" if ok else "failed","message":msg}, gen.placed