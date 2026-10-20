"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { centroid } from "@/components/PlanCanvas";
import { ErrorNote, Spinner } from "@/components/ui";
import type { Detection, FloorPlan, Pt, Source } from "@/types/api";
import { MistakeCatcher } from "./MistakeCatcher";

export interface EdRoom { key: string; label: string; room_type: string; polygon: Pt[]; source: Source; confidence: number | null }
export interface EdOpening { key: string; kind: "door" | "window"; position: Pt; is_main_entrance: boolean; source: Source; confidence: number | null }
type Sel = { type: "room" | "opening"; key: string } | null;
type Tool = "select" | "room" | "door" | "window";
type Drag =
  | { kind: "vertex"; key: string; idx: number }
  | { kind: "room"; key: string; start: Pt; orig: Pt[] }
  | { kind: "opening"; key: string }
  | { kind: "new-room"; start: Pt; current: Pt };

const LOW_CONFIDENCE = 0.7;
let seq = 0;
const newKey = (p: string) => `${p}-${Date.now().toString(36)}-${seq++}`;
const edited = (s: Source): Source => (s === "ai" ? "ai_edited" : s);
const pts = (poly: Pt[]) => poly.map((p) => p.join(",")).join(" ");

/** Build the editable model: previously verified data wins; otherwise start from the AI detection. */
export function initialModel(fp: FloorPlan, detection: Detection | null): { rooms: EdRoom[]; openings: EdOpening[]; fromAi: boolean } {
  if (fp.verified && fp.rooms.length) {
    return {
      fromAi: false,
      rooms: fp.rooms.map((r) => ({ key: r.id, label: r.label, room_type: r.room_type, polygon: r.polygon, source: r.source, confidence: r.confidence })),
      openings: fp.openings.map((o) => ({ key: o.id, kind: o.kind, position: o.position, is_main_entrance: o.is_main_entrance, source: o.source, confidence: o.confidence })),
    };
  }
  if (!detection) return { rooms: [], openings: [], fromAi: false };
  return {
    fromAi: true,
    rooms: [
      ...detection.rooms.map((r) => ({ key: r.id, label: r.name, room_type: r.room_type, polygon: r.polygon, source: "ai" as Source, confidence: r.confidence })),
      ...detection.stairs.map((s, i) => ({ key: s.id, label: detection.stairs.length > 1 ? `Staircase ${i + 1}` : "Staircase", room_type: "staircase",
        polygon: s.polygon, source: "ai" as Source, confidence: s.confidence })),
    ],
    openings: [...detection.doors, ...detection.windows].map((o) => ({
      key: o.id, kind: o.kind, position: o.position, is_main_entrance: o.is_main_entrance, source: "ai" as Source, confidence: o.confidence })),
  };
}

export function VerifyEditor({ fp, detection, roomTypes, onConfirm, busy, error }: {
  fp: FloorPlan; detection: Detection | null; roomTypes: { value: string; label: string }[];
  onConfirm: (rooms: EdRoom[], openings: EdOpening[]) => void; busy: boolean; error: unknown;
}) {
  const init = useMemo(() => initialModel(fp, detection), [fp, detection]);
  const [rooms, setRooms] = useState<EdRoom[]>(init.rooms);
  const [openings, setOpenings] = useState<EdOpening[]>(init.openings);
  const [history, setHistory] = useState<{ rooms: EdRoom[]; openings: EdOpening[] }[]>([]);
  const [sel, setSel] = useState<Sel>(null);
  const [tool, setTool] = useState<Tool>("select");
  const [drag, setDrag] = useState<Drag | null>(null);
  const [showImage, setShowImage] = useState(true);
  const [reviewed, setReviewed] = useState<Set<string>>(new Set());
  const svg = useRef<SVGSVGElement>(null);
  const moved = useRef(false);

  const w = fp.width, h = fp.height, u = Math.max(w, h) / 100;
  const typeLabel = (t: string) => roomTypes.find((r) => r.value === t)?.label ?? t;

  const snapshot = () => setHistory((hs) => [...hs.slice(-40), { rooms, openings }]);
  const undo = () => {
    const last = history[history.length - 1];
    if (!last) return;
    setRooms(last.rooms); setOpenings(last.openings); setHistory(history.slice(0, -1)); setSel(null);
  };

  const updateRoom = (key: string, patch: Partial<EdRoom>) =>
    setRooms((rs) => rs.map((r) => (r.key === key ? { ...r, ...patch, source: patch.source ?? edited(r.source) } : r)));
  const updateOpening = (key: string, patch: Partial<EdOpening>) =>
    setOpenings((os) => os.map((o) => (o.key === key ? { ...o, ...patch, source: patch.source ?? edited(o.source) } : o)));

  const deleteSelected = () => {
    if (!sel) return;
    snapshot();
    if (sel.type === "room") setRooms((rs) => rs.filter((r) => r.key !== sel.key));
    else setOpenings((os) => os.filter((o) => o.key !== sel.key));
    setSel(null);
  };
  const setMainEntrance = (key: string) => {
    snapshot();
    setOpenings((os) => os.map((o) => {
      if (o.key === key) return { ...o, kind: "door", is_main_entrance: !o.is_main_entrance, source: edited(o.source) };
      return o.is_main_entrance ? { ...o, is_main_entrance: false, source: edited(o.source) } : o;
    }));
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (t.tagName === "INPUT" || t.tagName === "SELECT" || t.tagName === "TEXTAREA") return;
      if ((e.key === "Delete" || e.key === "Backspace") && sel) { e.preventDefault(); deleteSelected(); }
      if (e.key === "Escape") { setSel(null); setTool("select"); setDrag(null); }
      if ((e.metaKey || e.ctrlKey) && e.key === "z") { e.preventDefault(); undo(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  // --- pointer plumbing: screen → image pixel coordinates ---------------------------------------
  const toPlan = (e: { clientX: number; clientY: number }): Pt => {
    const m = svg.current!.getScreenCTM()!.inverse();
    const p = new DOMPoint(e.clientX, e.clientY).matrixTransform(m);
    return [Math.round(Math.min(w, Math.max(0, p.x))), Math.round(Math.min(h, Math.max(0, p.y)))];
  };
  const capture = (e: React.PointerEvent) => svg.current?.setPointerCapture(e.pointerId);

  function onCanvasDown(e: React.PointerEvent) {
    const p = toPlan(e);
    if (tool === "room") { capture(e); setDrag({ kind: "new-room", start: p, current: p }); return; }
    if (tool === "door" || tool === "window") {
      snapshot();
      const key = newKey(tool);
      setOpenings((os) => [...os, { key, kind: tool, position: p, is_main_entrance: false, source: "user", confidence: null }]);
      setSel({ type: "opening", key }); setTool("select");
      return;
    }
    setSel(null);
  }
  function onMove(e: React.PointerEvent) {
    if (!drag) return;
    const p = toPlan(e);
    if (!moved.current) { moved.current = true; if (drag.kind !== "new-room") snapshot(); }
    if (drag.kind === "new-room") setDrag({ ...drag, current: p });
    else if (drag.kind === "vertex") {
      const r = rooms.find((x) => x.key === drag.key)!;
      updateRoom(drag.key, { polygon: r.polygon.map((q, i) => (i === drag.idx ? p : q)) });
    } else if (drag.kind === "room") {
      const dx = p[0] - drag.start[0], dy = p[1] - drag.start[1];
      updateRoom(drag.key, { polygon: drag.orig.map(([x, y]) => [Math.round(x + dx), Math.round(y + dy)] as Pt) });
    } else if (drag.kind === "opening") updateOpening(drag.key, { position: p });
  }
  function onUp() {
    if (drag?.kind === "new-room") {
      const [x1, y1] = drag.start, [x2, y2] = drag.current;
      if (Math.abs(x2 - x1) > u * 2 && Math.abs(y2 - y1) > u * 2) {
        snapshot();
        const key = newKey("room");
        const [a, b, c, d] = [Math.min(x1, x2), Math.min(y1, y2), Math.max(x1, x2), Math.max(y1, y2)];
        setRooms((rs) => [...rs, { key, label: `Room ${rs.length + 1}`, room_type: "other", polygon: [[a, b], [c, b], [c, d], [a, d]], source: "user", confidence: null }]);
        setSel({ type: "room", key });
      }
      setTool("select");
    }
    setDrag(null);
    moved.current = false;
  }
  // Pointer capture retargets dblclick to the <svg>, so corner removal is resolved by distance here.
  function onDouble(e: React.MouseEvent) {
    if (!selRoom || selRoom.polygon.length <= 3) return;
    const p = toPlan(e);
    const idx = selRoom.polygon.findIndex((q) => Math.hypot(q[0] - p[0], q[1] - p[1]) < u * 1.6);
    if (idx < 0) return;
    snapshot();
    updateRoom(selRoom.key, { polygon: selRoom.polygon.filter((_, j) => j !== idx) });
  }
  const startDrag = (e: React.PointerEvent, d: Drag, s: Sel) => {
    if (tool !== "select") return;
    e.stopPropagation(); capture(e); moved.current = false; setSel(s); setDrag(d);
  };

  // --- derived --------------------------------------------------------------------------------
  const selRoom = sel?.type === "room" ? rooms.find((r) => r.key === sel.key) : undefined;
  const selOpening = sel?.type === "opening" ? openings.find((o) => o.key === sel.key) : undefined;
  const needsCheck = (x: { key: string; source: Source; confidence: number | null }) =>
    x.source === "ai" && (x.confidence ?? 1) < LOW_CONFIDENCE && !reviewed.has(x.key);
  const checks = [...rooms.filter(needsCheck), ...openings.filter(needsCheck)];
  const genericRooms = rooms.filter((r) => r.room_type === "other");
  const mainEntrance = openings.find((o) => o.is_main_entrance);
  const counts = {
    ai: [...rooms, ...openings].filter((x) => x.source === "ai").length,
    edited: [...rooms, ...openings].filter((x) => x.source === "ai_edited").length,
    user: [...rooms, ...openings].filter((x) => x.source === "user").length,
  };

  const roomStyle = (r: EdRoom) => {
    const selected = sel?.type === "room" && sel.key === r.key;
    if (r.source === "ai") return { fill: needsCheck(r) ? "rgba(176,115,26,0.16)" : "rgba(156,107,28,0.08)", stroke: "#B0731A", dash: `${u * 0.9} ${u * 0.6}`, selected };
    return { fill: "rgba(47,115,85,0.10)", stroke: "#2F7355", dash: undefined, selected };
  };

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
      <div className="space-y-3">
        <div className="panel flex flex-wrap items-center gap-1 p-1.5 text-sm" role="toolbar" aria-label="Editing tools">
          {([["select", "Select / move"], ["room", "Draw room"], ["door", "Add door"], ["window", "Add window"]] as const).map(([t, l]) => (
            <button key={t} onClick={() => setTool(t)} aria-pressed={tool === t}
              className={`rounded px-3 py-1.5 ${tool === t ? "bg-ink text-white" : "text-ink-soft hover:bg-paper"}`}>{l}</button>
          ))}
          <span className="mx-1 h-5 w-px bg-hairline" />
          <button className="rounded px-3 py-1.5 text-ink-soft hover:bg-paper disabled:opacity-40" onClick={undo} disabled={!history.length}>Undo</button>
          <button className="rounded px-3 py-1.5 text-ink-soft hover:bg-paper disabled:opacity-40" onClick={deleteSelected} disabled={!sel}>Delete</button>
          <label className="ml-auto flex items-center gap-2 px-2 text-slate">
            <input type="checkbox" checked={showImage} onChange={(e) => setShowImage(e.target.checked)} /> Show plan image
          </label>
        </div>
        <p className="text-xs text-slate">
          {tool === "room" ? "Drag a rectangle over the room. You can reshape it afterwards."
            : tool === "door" || tool === "window" ? `Click where the ${tool} is.`
            : "Drag a room to move it, drag its corners to reshape, drag a hollow midpoint to add a corner, double-click a corner to remove it."}
        </p>
        <div className="panel overflow-hidden p-2">
          <svg ref={svg} viewBox={`${-u * 2} ${-u * 2} ${w + u * 4} ${h + u * 4}`}
            className={`block h-auto w-full touch-none select-none ${tool === "select" ? "" : "cursor-crosshair"}`}
            onPointerDown={onCanvasDown} onPointerMove={onMove} onPointerUp={onUp} onPointerCancel={onUp} onDoubleClick={onDouble}
            role="application" aria-label="Floor plan editor">
            <rect x={0} y={0} width={w} height={h} fill="#fff" />
            {showImage && <image href={fp.image_url} x={0} y={0} width={w} height={h} preserveAspectRatio="none" opacity={0.85} />}

            {rooms.map((r) => {
              const s = roomStyle(r);
              return (
                <polygon key={r.key} points={pts(r.polygon)} fill={s.fill} stroke={s.selected ? "#16283A" : s.stroke}
                  strokeWidth={u * (s.selected ? 0.55 : 0.3)} strokeDasharray={s.selected ? undefined : s.dash}
                  className={tool === "select" ? "cursor-move" : undefined}
                  onPointerDown={(e) => startDrag(e, { kind: "room", key: r.key, start: toPlan(e), orig: r.polygon }, { type: "room", key: r.key })} />
              );
            })}
            {rooms.map((r) => {
              const [x, y] = centroid(r.polygon);
              return (
                <g key={r.key} pointerEvents="none">
                  <text x={x} y={y} textAnchor="middle" fontSize={u * 1.9} fontWeight={500} fill="#16283A" fontFamily="IBM Plex Sans, sans-serif"
                    paintOrder="stroke" stroke="#fff" strokeWidth={u * 0.5} strokeLinejoin="round">{r.label}</text>
                  {needsCheck(r) && (
                    <text x={x} y={y + u * 2.3} textAnchor="middle" fontSize={u * 1.5} fill="#B0731A" fontFamily="IBM Plex Sans, sans-serif"
                      paintOrder="stroke" stroke="#fff" strokeWidth={u * 0.5}>Check this</text>
                  )}
                </g>
              );
            })}

            {selRoom && tool === "select" && (
              <g>
                {selRoom.polygon.map((p, i) => {
                  const q = selRoom.polygon[(i + 1) % selRoom.polygon.length];
                  const mid: Pt = [Math.round((p[0] + q[0]) / 2), Math.round((p[1] + q[1]) / 2)];
                  return (
                    <circle key={`m${i}`} cx={mid[0]} cy={mid[1]} r={u * 0.75} fill="#fff" stroke="#16283A" strokeWidth={u * 0.2} className="cursor-copy"
                      onPointerDown={(e) => {
                        if (tool !== "select") return;
                        e.stopPropagation(); capture(e); snapshot(); moved.current = true;
                        const poly = [...selRoom.polygon.slice(0, i + 1), mid, ...selRoom.polygon.slice(i + 1)];
                        updateRoom(selRoom.key, { polygon: poly });
                        setDrag({ kind: "vertex", key: selRoom.key, idx: i + 1 });
                      }} />
                  );
                })}
                {selRoom.polygon.map((p, i) => (
                  <rect key={`v${i}`} x={p[0] - u * 0.9} y={p[1] - u * 0.9} width={u * 1.8} height={u * 1.8} fill="#16283A" className="cursor-grab"
                    onPointerDown={(e) => startDrag(e, { kind: "vertex", key: selRoom.key, idx: i }, { type: "room", key: selRoom.key })}
/>
                ))}
              </g>
            )}

            {openings.map((o) => {
              const selected = sel?.type === "opening" && sel.key === o.key;
              const ai = o.source === "ai";
              const color = ai ? "#B0731A" : "#2F7355";
              return (
                <g key={o.key} transform={`translate(${o.position[0]} ${o.position[1]})`} className={tool === "select" ? "cursor-move" : undefined}
                  onPointerDown={(e) => startDrag(e, { kind: "opening", key: o.key }, { type: "opening", key: o.key })}>
                  <circle r={u * 2.6} fill="transparent" />
                  {selected && <circle r={u * 2.4} fill="none" stroke="#16283A" strokeWidth={u * 0.3} />}
                  {o.is_main_entrance ? (
                    <>
                      <circle r={u * 1.8} fill="#16283A" />
                      <text textAnchor="middle" dominantBaseline="central" fontSize={u * 1.7} fontWeight={600} fill="#fff" fontFamily="IBM Plex Sans, sans-serif">E</text>
                    </>
                  ) : o.kind === "door" ? (
                    <rect x={-u} y={-u} width={u * 2} height={u * 2} fill="#fff" stroke={color} strokeWidth={u * 0.35} strokeDasharray={ai ? `${u * 0.5} ${u * 0.3}` : undefined} />
                  ) : (
                    <circle r={u * 0.95} fill="#fff" stroke={color} strokeWidth={u * 0.35} strokeDasharray={ai ? `${u * 0.4} ${u * 0.3}` : undefined} />
                  )}
                  {needsCheck(o) && <circle cx={u * 1.6} cy={-u * 1.6} r={u * 0.6} fill="#B0731A" />}
                </g>
              );
            })}

            {drag?.kind === "new-room" && (
              <rect x={Math.min(drag.start[0], drag.current[0])} y={Math.min(drag.start[1], drag.current[1])}
                width={Math.abs(drag.current[0] - drag.start[0])} height={Math.abs(drag.current[1] - drag.start[1])}
                fill="rgba(47,115,85,0.12)" stroke="#2F7355" strokeWidth={u * 0.3} />
            )}
          </svg>
        </div>
        <div className="flex flex-wrap gap-4 text-xs text-slate">
          <Legend swatch="border-2 border-dashed border-warning bg-warning-light" label={`AI detected (${counts.ai})`} />
          <Legend swatch="border-2 border-positive bg-positive-light" label={`Verified by you: ${counts.edited} edited, ${counts.user} added`} />
          <Legend swatch="rounded-full bg-ink" label="Main entrance" />
        </div>
      </div>

      <aside className="space-y-4">
        {selRoom ? (
          <div className="panel space-y-4 p-4">
            <div className="flex items-center justify-between">
              <p className="font-medium">Room</p>
              <SourceChip source={selRoom.source} confidence={selRoom.confidence} />
            </div>
            <div>
              <label className="label" htmlFor="room-label">Name</label>
              <input id="room-label" className="field" value={selRoom.label} maxLength={120}
                onFocus={snapshot} onChange={(e) => updateRoom(selRoom.key, { label: e.target.value })} />
            </div>
            <div>
              <label className="label" htmlFor="room-type">Room type</label>
              <select id="room-type" className="field" value={selRoom.room_type}
                onChange={(e) => { snapshot(); updateRoom(selRoom.key, { room_type: e.target.value }); }}>
                {roomTypes.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
              <p className="mt-1 text-xs text-slate">Vastu rules match on the room type, not the name.</p>
            </div>
            {needsCheck(selRoom) && (
              <div className="rounded bg-warning-light p-3 text-sm">
                <p className="text-ink">The AI was only {Math.round((selRoom.confidence ?? 0) * 100)}% sure about this room.</p>
                <button className="btn-secondary mt-2" onClick={() => setReviewed(new Set(reviewed).add(selRoom.key))}>It's correct</button>
              </div>
            )}
            <button className="btn-danger w-full" onClick={deleteSelected}>Delete room</button>
          </div>
        ) : selOpening ? (
          <div className="panel space-y-4 p-4">
            <div className="flex items-center justify-between">
              <p className="font-medium">{selOpening.is_main_entrance ? "Main entrance" : selOpening.kind === "door" ? "Door" : "Window"}</p>
              <SourceChip source={selOpening.source} confidence={selOpening.confidence} />
            </div>
            <div className="flex gap-2">
              {(["door", "window"] as const).map((k) => (
                <button key={k} aria-pressed={selOpening.kind === k}
                  className={selOpening.kind === k ? "btn-primary flex-1" : "btn-secondary flex-1"}
                  onClick={() => { snapshot(); updateOpening(selOpening.key, { kind: k, is_main_entrance: k === "window" ? false : selOpening.is_main_entrance }); }}>
                  {k === "door" ? "Door" : "Window"}
                </button>
              ))}
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={selOpening.is_main_entrance} onChange={() => setMainEntrance(selOpening.key)} />
              This is the main entrance
            </label>
            {needsCheck(selOpening) && (
              <div className="rounded bg-warning-light p-3 text-sm">
                <p>The AI was only {Math.round((selOpening.confidence ?? 0) * 100)}% sure about this {selOpening.kind}.</p>
                <button className="btn-secondary mt-2" onClick={() => setReviewed(new Set(reviewed).add(selOpening.key))}>It's correct</button>
              </div>
            )}
            <button className="btn-danger w-full" onClick={deleteSelected}>Delete {selOpening.kind}</button>
          </div>
        ) : (
          <div className="panel p-4 text-sm text-slate">
            Select a room, door or window to rename, retype or delete it. Only what you confirm here is used in the Vastu analysis.
          </div>
        )}

        <div className="panel p-4 text-sm">
          <p className="font-medium">Before you confirm</p>
          <ul className="mt-2 space-y-1.5">
            <Check ok={rooms.length > 0} text={rooms.length ? `${rooms.length} rooms` : "Add at least one room"} />
            <Check ok={!!mainEntrance} warn text={mainEntrance ? "Main entrance marked" : "Mark the main entrance (entrance rules are skipped without it)"} />
            <Check ok={checks.length === 0} warn text={checks.length ? `${checks.length} low-confidence item${checks.length > 1 ? "s" : ""} to check` : "Low-confidence items checked"} />
            <Check ok={genericRooms.length === 0} warn text={genericRooms.length ? `${genericRooms.length} room${genericRooms.length > 1 ? "s" : ""} without a type (won't be scored)` : "Every room has a type"} />
          </ul>
          {checks.length > 0 && (
            <button className="btn-quiet mt-2 px-0" onClick={() => {
              const c = checks[0];
              setSel({ type: rooms.some((r) => r.key === c.key) ? "room" : "opening", key: c.key }); setTool("select");
            }}>Show next item to check</button>
          )}
        </div>

        <MistakeCatcher fpId={fp.id} rooms={rooms} openings={openings} onSelect={(key) => {
          setSel({ type: rooms.some((r) => r.key === key) ? "room" : "opening", key }); setTool("select");
        }} />

        <div className="max-h-64 overflow-auto panel">
          <table className="w-full text-sm">
            <tbody className="divide-y divide-hairline">
              {rooms.map((r) => (
                <tr key={r.key} onClick={() => { setSel({ type: "room", key: r.key }); setTool("select"); }}
                  className={`cursor-pointer ${sel?.key === r.key ? "bg-paper" : "hover:bg-paper/60"}`}>
                  <td className="px-3 py-2">{r.label}<span className="block text-xs text-slate">{typeLabel(r.room_type)}</span></td>
                  <td className="px-3 py-2 text-right"><SourceChip source={r.source} confidence={r.confidence} compact /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <ErrorNote error={error} />
        <button className="btn-primary w-full" disabled={busy || rooms.length === 0 || rooms.some((r) => !r.label.trim())}
          onClick={() => onConfirm(rooms, openings)}>
          {busy && <Spinner />} Confirm plan and set North
        </button>
        <p className="text-xs text-slate">Confirming marks everything shown as verified by you.</p>
      </aside>
    </div>
  );
}

function SourceChip({ source, confidence, compact }: { source: Source; confidence: number | null; compact?: boolean }) {
  if (source === "ai")
    return <span className="rounded-sm border border-dashed border-warning px-1.5 py-0.5 text-xs text-warning">
      AI detected{confidence != null && !compact ? ` · ${Math.round(confidence * 100)}%` : ""}</span>;
  return <span className="rounded-sm border border-positive/40 bg-positive-light px-1.5 py-0.5 text-xs text-positive">
    {source === "ai_edited" ? "Edited by you" : "Added by you"}</span>;
}
function Legend({ swatch, label }: { swatch: string; label: string }) {
  return <span className="flex items-center gap-1.5"><span className={`inline-block h-3 w-3 ${swatch}`} />{label}</span>;
}
function Check({ ok, warn, text }: { ok: boolean; warn?: boolean; text: string }) {
  return (
    <li className="flex gap-2">
      <span aria-hidden className={ok ? "text-positive" : warn ? "text-warning" : "text-major"}>{ok ? "✓" : "!"}</span>
      <span className={ok ? "text-ink-soft" : "text-ink"}>{text}</span>
    </li>
  );
}
