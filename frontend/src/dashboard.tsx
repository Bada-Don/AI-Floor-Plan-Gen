import React, { useEffect, useMemo, useState } from "react";
import { v4 as uuidv4 } from "uuid";
import {
  Card,
  CardHeader,
  CardContent,
  CardTitle,
  CardDescription,
} from "./components/ui/card";
import { Button } from "./components/ui/button";
import { Textarea } from "./components/ui/textarea";
import { Badge } from "./components/ui/badge";
import {
  Loader2,
  RefreshCw,
  Sparkles,
  XCircle,
  Send,
} from "lucide-react";

// ---------- Types ----------
import {
  LayoutResponse,
  ConflictResponse,
} from "./features/dashboard/types";

// ---------- Helpers ----------
const loadOrCreateSessionId = (): string => {
  const key = "floorplan-ai-session-id";
  const existing = localStorage.getItem(key);
  if (existing) return existing;
  const newSid = uuidv4();
  localStorage.setItem(key, newSid);
  return newSid;
};

const debounce = (fn: Function, delay = 800) => {
  let timer: any;
  return (...args: any[]) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
};

// ---------- Main Component ----------
export default function GenerativeLayoutUI() {
  const [sessionId] = useState<string>(loadOrCreateSessionId());
  const [loading, setLoading] = useState(false);
  const [lastError, setLastError] = useState<string | null>(null);
  const [conflicts, setConflicts] = useState<string[]>([]);

  // User's natural language input
  const [freeform, setFreeform] = useState("");

  // The final layout response from the backend
  const [layout, setLayout] = useState<LayoutResponse | null>(null);

  // ---------- API Call Logic ----------
  const generateLayout = async (text: string) => {
    if (!text.trim()) {
      setLastError("Please enter a description.");
      return;
    }

    setLoading(true);
    setLastError(null);
    setConflicts([]);
    setLayout(null); // Clear previous layout

    try {
      // Make sure this URL matches your backend server address
      const res = await fetch("http://127.0.0.1:8000/generate-floorplan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mode: "freeform",
          freeform: { text: text },
        }),
      });

      const data = await res.json();

      if (!res.ok || data?.error) {
        const err = data as ConflictResponse;
        setLastError(err.error || "Layout generation failed.");
        setConflicts(err.conflicts || []);
        return;
      }

      setLayout(data as LayoutResponse);
    } catch (e: any) {
      setLastError(e?.message || "A network error occurred.");
    } finally {
      setLoading(false);
    }
  };

  // Use a debounced function for auto-generation
  const debouncedGenerate = useMemo(() => debounce(generateLayout), []);


  // ---------- Subcomponents ----------
  const LayoutPreview: React.FC<{ layout: LayoutResponse | null }> = ({ layout }) => {
    return (
      <div className="w-full h-[500px] rounded-lg bg-slate-100 border border-slate-200 relative grid place-items-center overflow-hidden">
        {loading && (
            <div className="absolute inset-0 z-10 grid place-items-center bg-white/50 backdrop-blur-sm">
                 <div className="flex items-center gap-2 text-sm text-slate-500">
                    <Loader2 className="h-4 w-4 animate-spin"/> Thinking...
                </div>
            </div>
        )}

        {layout?.image_base64 ? (
          <img
            src={`data:image/png;base64,${layout.image_base64}`}
            alt="Generated Floor Plan"
            className="object-scale-down"
          />
        ) : (
          !loading && <div className="text-slate-500 text-sm">
            Enter a description to see your floor plan.
          </div>
        )}
      </div>
    );
  };

  // ---------- UI ----------
  return (
    <div className="min-h-screen w-full bg-slate-50">
      <div className="mx-auto max-w-6xl p-4 sm:p-6 lg:p-8">
        {/* Header */}
        <div className="flex items-center justify-between gap-3 mb-6">
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-slate-800">AI Floor Plan Generator</h1>
            <p className="text-sm text-slate-500">
              Turn your ideas into a floor plan with a simple sentence.
            </p>
          </div>
          <Badge variant="outline" className="text-xs shrink-0">Session: {sessionId.slice(0, 8)}</Badge>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left: Inputs */}
          <div className="lg:col-span-1 space-y-4">
            <Card className="shadow-sm">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Sparkles className="h-5 w-5 text-purple-500"/> Describe Your Plan
                </CardTitle>
                <CardDescription>Enter plot size, number of rooms, and any special requests.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <Textarea
                  placeholder='e.g., "A 30x40 plot with 3 bedrooms and 2 bathrooms..."'
                  value={freeform}
                  onChange={(e) => setFreeform(e.target.value)}
                  className="min-h-[150px] text-base"
                />
                <div className="flex items-center justify-end">
                  <Button
                    onClick={() => generateLayout(freeform)}
                    disabled={loading || !freeform.trim()}
                  >
                    {loading ? "Generating..." : "Generate"}
                    <Send className="ml-2 h-4 w-4"/>
                  </Button>
                </div>
              </CardContent>
            </Card>

            {/* Error and Conflict Display */}
            {(lastError || conflicts.length > 0) && (
              <Card className="border-red-200 bg-red-50">
                <CardHeader>
                  <CardTitle className="text-red-700 flex items-center gap-2">
                    <XCircle className="h-5 w-5"/> Error
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {lastError && <p className="text-sm font-medium text-red-800">{lastError}</p>}
                  {conflicts.length > 0 && (
                      <ul className="list-disc pl-5 text-sm text-red-700 space-y-1">
                        {conflicts.map((c, i) => <li key={i}>{c}</li>)}
                      </ul>
                  )}
                </CardContent>
              </Card>
            )}
          </div>

          {/* Right: Preview */}
          <div className="lg:col-span-2">
             <Card className="shadow-sm">
                <CardHeader>
                    <CardTitle>Generated Floor Plan</CardTitle>
                    <CardDescription>This is the layout generated by the AI based on your description.</CardDescription>
                </CardHeader>
                <CardContent>
                    <LayoutPreview layout={layout} />
                </CardContent>
             </Card>
          </div>
        </div>
      </div>
    </div>
  );
}