import React, { useEffect, useMemo, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { v4 as uuidv4 } from "uuid";
import {
  Card,
  CardHeader,
  CardContent,
  CardTitle,
  CardDescription,
} from "./components/ui/card";
import { Button } from "./components/ui/button";
import { Input } from "./components/ui/input";
import { Textarea } from "./components/ui/textarea";
import { Badge } from "./components/ui/badge";
import { Switch } from "./components/ui/switch";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "./components/ui/tabs";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "./components/ui/dropdown-menu";
import { Slider } from "./components/ui/slider";
import {
  Plus,
  Loader2,
  Undo2,
  Redo2,
  Trash2,
  Lock,
  Unlock,
  RefreshCw,
  Sparkles,
  XCircle,
  Send,
} from "lucide-react";

// ---------- Types ----------
import {
  Priority,
  ElementConstraint,
  StructuredConstraints,
  ChangeEvent,
  LayoutResponse,
  ConflictResponse,
} from "./features/dashboard/types";

// ---------- Helpers ----------

const loadOrCreateSessionId = (): string => {
  const key = "glui-session-id";
  const existing = localStorage.getItem(key);
  if (existing) return existing;
  const newSid = uuidv4();
  localStorage.setItem(key, newSid);
  return newSid;
};

const debounce = (fn: Function, delay = 600) => {
  let t: any;
  return (...args: any[]) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), delay);
  };
};

const typeHue: Record<string, number> = {
  park: 140,
  pool: 200,
  entrance: 20,
  house: 30,
  garage: 0,
  bbq: 10,
};

const colorForType = (type: string) => {
  const hue = typeHue[type?.toLowerCase()] ?? 260;
  return `hsl(${hue} 70% 45%)`;
};

// scale utility to map model coordinates -> viewBox
function makeScaler(lotW: number, lotH: number, viewW: number, viewH: number) {
  const scale = Math.min(viewW / lotW, viewH / lotH);
  const offsetX = (viewW - lotW * scale) / 2;
  const offsetY = (viewH - lotH * scale) / 2;
  return (x: number) => x * scale;
}

// ---------- Main Component ----------

export default function GenerativeLayoutUI() {
  // sessions & network
  const [sessionId, setSessionId] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [lastError, setLastError] = useState<string | null>(null);
  const [conflicts, setConflicts] = useState<string[]>([]);
  const [suggestions, setSuggestions] = useState<string[]>([]);

  // freeform & structured constraints
  const [freeform, setFreeform] = useState("");
  const [constraints, setConstraints] = useState<StructuredConstraints>({
    lot: { width: 100, height: 60 },
    elements: [
      {
        id: uuidv4(),
        type: "park",
        width: 30,
        height: 20,
        position: "left",
        priority: "high",
        locked: false,
      },
      {
        id: uuidv4(),
        type: "pool",
        width: 15,
        height: 10,
        position: "right",
        priority: "medium",
        locked: false,
      },
      {
        id: uuidv4(),
        type: "entrance",
        position: "middle",
        priority: "high",
        locked: false,
      },
    ],
    notes: "Include trees around the park and deck chairs by the pool.",
  });

  // layout preview
  const [layout, setLayout] = useState<LayoutResponse | null>(null);

  // undo/redo
  const [history, setHistory] = useState<StructuredConstraints[]>([]);
  const [future, setFuture] = useState<StructuredConstraints[]>([]);

  // initialize session
  useEffect(() => {
    const sid = loadOrCreateSessionId();
    setSessionId(sid);
  }, []);

  // debounced generator
  const debouncedGenerate = useMemo(
    () =>
      debounce(async (mode: "freeform" | "structured") => {
        await generateLayout(mode);
      }, 600),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [constraints, freeform, sessionId]
  );

  // auto-generate on change
  useEffect(() => {
    if (!sessionId) return;
    // when there is at least some input, generate
    if (freeform.trim().length > 0) debouncedGenerate("freeform");
    else debouncedGenerate("structured");
  }, [constraints, freeform, sessionId]);

  // ---------- Network Calls ----------

  async function generateLayout(mode: "freeform" | "structured") {
    setLoading(true);
    setLastError(null);
    setConflicts([]);
    setSuggestions([]);
    try {
      const res = await fetch("/generate-layout", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Session-ID": sessionId,
        },
        body: JSON.stringify({
          sessionId,
          mode,
          input: mode === "freeform" ? { text: freeform } : constraints,
        }),
      });

      const data = await res.json();
      if (!res.ok || data?.error) {
        const err = (data as ConflictResponse);
        setLastError(err.error || "Layout generation failed");
        setConflicts(err.conflicts || []);
        setSuggestions(err.suggestions || []);
        setLayout(null);
        return;
      }

      setLayout(data as LayoutResponse);
    } catch (e: any) {
      setLastError(e?.message || "Network error");
    } finally {
      setLoading(false);
    }
  }

  async function sendChange(change: ChangeEvent) {
    setLoading(true);
    setLastError(null);
    setConflicts([]);
    setSuggestions([]);
    try {
      const res = await fetch("/generate-layout", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Session-ID": sessionId,
        },
        body: JSON.stringify({
          sessionId,
          mode: "change",
          input: constraints, // include latest constraints so backend can reconcile
          changeEvent: change,
        }),
      });

      const data = await res.json();
      if (!res.ok || data?.error) {
        const err = (data as ConflictResponse);
        setLastError(err.error || "Change application failed");
        setConflicts(err.conflicts || []);
        setSuggestions(err.suggestions || []);
        setLayout(null);
        return;
      }
      setLayout(data as LayoutResponse);
    } catch (e: any) {
      setLastError(e?.message || "Network error");
    } finally {
      setLoading(false);
    }
  }

  // ---------- Local State Editing ----------

  function commit(next: StructuredConstraints) {
    setHistory((h) => [...h, constraints]);
    setFuture([]);
    setConstraints(next);
  }

  function undo() {
    if (history.length === 0) return;
    const prev = history[history.length - 1];
    setHistory((h) => h.slice(0, -1));
    setFuture((f) => [constraints, ...f]);
    setConstraints(prev);
  }

  function redo() {
    if (future.length === 0) return;
    const next = future[0];
    setFuture((f) => f.slice(1));
    setHistory((h) => [...h, constraints]);
    setConstraints(next);
  }

  function addElement() {
    const el: ElementConstraint = {
      id: uuidv4(),
      type: "bbq",
      width: 10,
      height: 8,
      position: "behind pool",
      priority: "low",
      locked: false,
    };
    commit({ ...constraints, elements: [...constraints.elements, el] });
    sendChange({ action: "add", target: el.id, changes: el });
  }

  function deleteElement(el: ElementConstraint) {
    commit({
      ...constraints,
      elements: constraints.elements.filter((e) => e.id !== el.id),
    });
    sendChange({ action: "delete", target: el.id });
  }

  function toggleLock(el: ElementConstraint) {
    const locked = !el.locked;
    commit({
      ...constraints,
      elements: constraints.elements.map((e) =>
        e.id === el.id ? { ...e, locked } : e
      ),
    });
    sendChange({ action: locked ? "lock" : "unlock", target: el.id });
  }

  function modifyElement(el: ElementConstraint, changes: Partial<ElementConstraint>) {
    const updated = { ...el, ...changes } as ElementConstraint;
    commit({
      ...constraints,
      elements: constraints.elements.map((e) => (e.id === el.id ? updated : e)),
    });
    const payload: ChangeEvent = {
      action: "modify",
      target: el.id,
      changes,
    };
    sendChange(payload);
  }

  function acceptSuggestion(s: string) {
    // Let backend decide how to apply; we still push to history for undo
    setHistory((h) => [...h, constraints]);
    setFuture([]);
    sendChange({ action: "accept_suggestion", suggestion: s });
  }

  // ---------- Subcomponents ----------

  const ElementCard: React.FC<{ el: ElementConstraint }> = ({ el }) => {
    return (
      <Card className="mb-3 shadow-sm border-muted/40">
        <CardHeader className="py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span
                className="inline-block h-3 w-3 rounded-full"
                style={{ background: colorForType(el.type) }}
              />
              <CardTitle className="text-base font-semibold capitalize">
                {el.type}
              </CardTitle>
              <Badge variant={el.priority === "high" ? "destructive" : "secondary"}>
                {el.priority}
              </Badge>
              {el.locked ? (
                <Badge variant="outline" className="gap-1">
                  <Lock className="h-3 w-3" /> locked
                </Badge>
              ) : (
                <Badge variant="outline" className="gap-1">
                  <Unlock className="h-3 w-3" /> flexible
                </Badge>
              )}
            </div>
            <div className="flex items-center gap-2">
              <Button size="icon" variant="outline" onClick={() => toggleLock(el)}>
                {el.locked ? <Lock className="h-4 w-4" /> : <Unlock className="h-4 w-4" />}
              </Button>
              <Button size="icon" variant="outline" onClick={() => deleteElement(el)}>
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          </div>
          <CardDescription className="mt-1 text-xs">
            Position: <span className="font-medium">{el.position || "—"}</span>
          </CardDescription>
        </CardHeader>
        <CardContent className="pt-0">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs">Width {el.width ?? "auto"}</label>
              <Slider
                value={[Number(el.width ?? 0)]}
                min={0}
                max={100}
                step={1}
                onValueChange={([v]) => modifyElement(el, { width: v })}
              />
            </div>
            <div>
              <label className="text-xs">Height {el.height ?? "auto"}</label>
              <Slider
                value={[Number(el.height ?? 0)]}
                min={0}
                max={100}
                step={1}
                onValueChange={([v]) => modifyElement(el, { height: v })}
              />
            </div>
            <div className="col-span-2">
              <label className="text-xs">Preferred position</label>
              <Input
                value={el.position || ""}
                onChange={(e) => modifyElement(el, { position: e.target.value })}
                placeholder="left | right | middle | top-left | behind pool"
              />
            </div>
            <div className="col-span-2">
              <label className="text-xs">Priority</label>
              <div className="flex gap-2 mt-1">
                {["low", "medium", "high"].map((p) => (
                  <Button
                    key={p}
                    size="sm"
                    variant={el.priority === p ? "default" : "outline"}
                    onClick={() => modifyElement(el, { priority: p as Priority })}
                  >
                    {p}
                  </Button>
                ))}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  };

  const SVGPreview: React.FC<{ layout: LayoutResponse | null }> = ({ layout }) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const [size, setSize] = useState({ w: 800, h: 480 });

    useEffect(() => {
      const el = containerRef.current;
      if (!el) return;
      const obs = new ResizeObserver(() => {
        setSize({ w: el.clientWidth, h: el.clientHeight });
      });
      obs.observe(el);
      return () => obs.disconnect();
    }, []);

    const lotW = layout?.lot.width ?? 100;
    const lotH = layout?.lot.height ?? 60;
    const scale = Math.min(size.w / lotW, size.h / lotH);
    const offsetX = (size.w - lotW * scale) / 2;
    const offsetY = (size.h - lotH * scale) / 2;

    return (
      <div ref={containerRef} className="w-full h-[480px] rounded-2xl bg-muted/30 relative overflow-hidden">
        <svg width={size.w} height={size.h} className="absolute inset-0">
          {/* Lot background */}
          <g transform={`translate(${offsetX},${offsetY}) scale(${scale})`}>
            <rect x={0} y={0} width={lotW} height={lotH} rx={2} ry={2} fill="#f6f7f9" stroke="#e2e8f0" />
            {/* grid */}
            {Array.from({ length: Math.ceil(lotW / 5) + 1 }, (_, i) => (
              <line key={`vg${i}`} x1={i * 5} y1={0} x2={i * 5} y2={lotH} stroke="#eaecef" strokeWidth={0.3} />
            ))}
            {Array.from({ length: Math.ceil(lotH / 5) + 1 }, (_, i) => (
              <line key={`hg${i}`} x1={0} y1={i * 5} x2={lotW} y2={i * 5} stroke="#eaecef" strokeWidth={0.3} />
            ))}

            {/* Features */}
            <AnimatePresence>
              {layout?.features?.map((f) => (
                <motion.g
                  key={`${f.type}-${f.x}-${f.y}-${f.width}-${f.height}`}
                  initial={{ opacity: 0, scale: 0.98 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.98 }}
                >
                  <rect
                    x={f.x}
                    y={f.y}
                    width={f.width}
                    height={f.height}
                    rx={1.5}
                    ry={1.5}
                    fill={colorForType(f.type)}
                    opacity={0.2}
                    stroke={colorForType(f.type)}
                    strokeWidth={0.8}
                  />
                  <text x={f.x + 2} y={f.y + 6} fontSize={3} fill="#334155">
                    {f.type}
                  </text>
                </motion.g>
              ))}
            </AnimatePresence>
          </g>
        </svg>
        {!layout && (
          <div className="absolute inset-0 grid place-items-center text-muted-foreground text-sm">
            Provide input to generate a preview.
          </div>
        )}
      </div>
    );
  };

  // ---------- UI ----------

  return (
    <div className="min-h-screen w-full bg-gradient-to-b from-white to-slate-50">
      <div className="mx-auto max-w-7xl p-4 sm:p-6 lg:p-8">
        {/* Header */}
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">Generative Layout Studio</h1>
            <p className="text-sm text-muted-foreground">
              Capture requirements, tweak constraints, and preview layouts in real time.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="text-xs">Session: {sessionId.slice(0, 8)}</Badge>
            <Button variant="outline" size="icon" onClick={() => generateLayout(freeform.trim() ? "freeform" : "structured")}>
              <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            </Button>
            <Button variant="outline" size="icon" onClick={undo} disabled={history.length === 0}>
              <Undo2 className="h-4 w-4" />
            </Button>
            <Button variant="outline" size="icon" onClick={redo} disabled={future.length === 0}>
              <Redo2 className="h-4 w-4" />
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 lg:gap-6">
          {/* Left: Inputs */}
          <div className="lg:col-span-1 space-y-4">
            <Card className="shadow-sm border-muted/40">
              <CardHeader>
                <CardTitle className="flex items-center gap-2"><Sparkles className="h-5 w-5"/> Natural Language</CardTitle>
                <CardDescription>Describe your layout in your own words.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <Textarea
                  placeholder='e.g., "I want a park (30x20) on the left, a pool (15x10) on the right, and entrance in the middle"'
                  value={freeform}
                  onChange={(e) => setFreeform(e.target.value)}
                  className="min-h-[110px]"
                />
                <div className="flex items-center justify-between">
                  <div className="text-xs text-muted-foreground">Auto-generates preview as you type</div>
                  <Button size="sm" onClick={() => generateLayout("freeform")}>Send <Send className="ml-1 h-4 w-4"/></Button>
                </div>
              </CardContent>
            </Card>

            <Card className="shadow-sm border-muted/40">
              <CardHeader>
                <CardTitle>Structured Constraints</CardTitle>
                <CardDescription>Power users can set precise lot & element constraints.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs">Lot width (m/ft)</label>
                    <Input
                      type="number"
                      value={constraints.lot.width}
                      onChange={(e) =>
                        commit({ ...constraints, lot: { ...constraints.lot, width: Number(e.target.value) || 0 } })
                      }
                    />
                  </div>
                  <div>
                    <label className="text-xs">Lot height (m/ft)</label>
                    <Input
                      type="number"
                      value={constraints.lot.height}
                      onChange={(e) =>
                        commit({ ...constraints, lot: { ...constraints.lot, height: Number(e.target.value) || 0 } })
                      }
                    />
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="font-medium">Elements</h3>
                    <Button size="sm" variant="secondary" onClick={addElement}><Plus className="h-4 w-4 mr-1"/> Add</Button>
                  </div>
                  <div>
                    {constraints.elements.map((el) => (
                      <ElementCard key={el.id} el={el} />
                    ))}
                  </div>
                </div>

                <div>
                  <label className="text-xs">Notes</label>
                  <Textarea
                    value={constraints.notes || ""}
                    onChange={(e) => commit({ ...constraints, notes: e.target.value })}
                    placeholder="Any extra instructions (trees near park, deck chairs by pool, etc.)"
                  />
                </div>

                <div className="flex items-center justify-end">
                  <Button onClick={() => generateLayout("structured")}>Generate Preview</Button>
                </div>
              </CardContent>
            </Card>

            {(lastError || conflicts.length > 0) && (
              <Card className="border-red-200 bg-red-50/60">
                <CardHeader>
                  <CardTitle className="text-red-700 flex items-center gap-2"><XCircle className="h-5 w-5"/> Conflicts Detected</CardTitle>
                  <CardDescription className="text-red-600">Resolve conflicts or accept suggestions below.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  {lastError && <div className="text-sm text-red-700">{lastError}</div>}
                  {conflicts.length > 0 && (
                    <div>
                      <div className="text-xs font-medium mb-1">Conflicts</div>
                      <ul className="list-disc pl-5 text-sm text-red-700 space-y-1">
                        {conflicts.map((c, i) => (
                          <li key={i}>{c}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {suggestions.length > 0 && (
                    <div>
                      <div className="text-xs font-medium mb-1">Suggestions</div>
                      <div className="flex flex-col gap-2">
                        {suggestions.map((s, i) => (
                          <div key={i} className="flex items-center justify-between gap-2">
                            <div className="text-sm text-slate-700">{s}</div>
                            <Button size="sm" variant="outline" onClick={() => acceptSuggestion(s)}>Apply</Button>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}
          </div>

          {/* Right: Preview */}
          <div className="lg:col-span-2 space-y-4">
            <Card className="shadow-sm border-muted/40">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>Real-time Preview</CardTitle>
                    <CardDescription>Rendering from backend JSON coordinates</CardDescription>
                  </div>
                  {loading && (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <Loader2 className="h-4 w-4 animate-spin"/> Updating…
                    </div>
                  )}
                </div>
              </CardHeader>
              <CardContent>
                <SVGPreview layout={layout} />
              </CardContent>
            </Card>

            <Card className="shadow-sm border-muted/40">
              <CardHeader>
                <CardTitle>Quick Actions</CardTitle>
                <CardDescription>Send incremental edits to the backend.</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-2">
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="outline">Modify Feature</Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent>
                      <DropdownMenuLabel>Select element</DropdownMenuLabel>
                      <DropdownMenuSeparator />
                      {constraints.elements.map((el) => (
                        <DropdownMenuItem
                          key={el.id}
                          onClick={() =>
                            sendChange({ action: "modify", target: el.id, changes: { width: (el.width ?? 10) + 2 } })
                          }
                        >
                          Increase width of {el.type}
                        </DropdownMenuItem>
                      ))}
                    </DropdownMenuContent>
                  </DropdownMenu>

                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="outline">Delete Feature</Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent>
                      <DropdownMenuLabel>Select element</DropdownMenuLabel>
                      <DropdownMenuSeparator />
                      {constraints.elements.map((el) => (
                        <DropdownMenuItem key={el.id} onClick={() => deleteElement(el)}>
                          Remove {el.type}
                        </DropdownMenuItem>
                      ))}
                    </DropdownMenuContent>
                  </DropdownMenu>

                  <Button variant="outline" onClick={addElement}>Add BBQ area</Button>

                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="outline">Lock/Unlock</Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent>
                      <DropdownMenuLabel>Select element</DropdownMenuLabel>
                      <DropdownMenuSeparator />
                      {constraints.elements.map((el) => (
                        <DropdownMenuItem key={el.id} onClick={() => toggleLock(el)}>
                          {el.locked ? "Unlock" : "Lock"} {el.type}
                        </DropdownMenuItem>
                      ))}
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </CardContent>
            </Card>

            <Card className="shadow-sm border-muted/40">
              <CardHeader>
                <CardTitle>Request/Response Debug</CardTitle>
                <CardDescription>What we send & what we render.</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <div className="text-xs font-medium">Constraints (sent)</div>
                    <pre className="text-xs bg-muted/40 rounded-lg p-3 overflow-auto max-h-72">
{JSON.stringify(constraints, null, 2)}
                    </pre>
                  </div>
                  <div className="space-y-2">
                    <div className="text-xs font-medium">Layout (received)</div>
                    <pre className="text-xs bg-muted/40 rounded-lg p-3 overflow-auto max-h-72">
{JSON.stringify(layout || { info: "No layout yet or conflicts present." }, null, 2)}
                    </pre>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>

        <footer className="mt-8 text-center text-xs text-muted-foreground">
          Backend endpoint used: <code>/generate-layout</code> • All requests include <code>sessionId</code>
        </footer>
      </div>
    </div>
  );
}
