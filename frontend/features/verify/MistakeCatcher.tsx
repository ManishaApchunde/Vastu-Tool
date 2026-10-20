"use client";
import { useEffect, useRef, useState } from "react";
import { CheckList } from "@/features/insights/TrustPassport";
import { api } from "@/services/api";
import type { PlanChecks, PlanCheck } from "@/types/insights";
import type { EdOpening, EdRoom } from "./Editor";

/**
 * AI Mistake Catcher: re-checks the draft on the server as you edit (debounced) and lists likely
 * mistakes: unnamed or mistyped rooms, overlaps, missing kitchen/toilet, a second main entrance,
 * a main entrance away from the outer wall, unreviewed low-confidence AI guesses and more.
 */
export function MistakeCatcher({ fpId, rooms, openings, onSelect }: {
  fpId: string; rooms: EdRoom[]; openings: EdOpening[]; onSelect: (key: string) => void;
}) {
  const [res, setRes] = useState<PlanChecks | null>(null);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const seq = useRef(0);

  useEffect(() => {
    const n = ++seq.current;
    const t = setTimeout(async () => {
      if (!rooms.length) { setRes(null); return; }
      setBusy(true);
      try {
        const r = await api.draftChecks(fpId, {
          boundary: null,
          rooms: rooms.filter((x) => x.label.trim()).map((x) => ({ id: x.key.slice(0, 32), label: x.label.trim(), room_type: x.room_type,
            polygon: x.polygon, source: x.source, confidence: x.confidence })),
          openings: openings.map((o) => ({ id: o.key.slice(0, 32), kind: o.kind, position: o.position, is_main_entrance: o.is_main_entrance,
            source: o.source, confidence: o.confidence })),
        });
        if (n === seq.current) { setRes(r); setFailed(false); }
      } catch {
        if (n === seq.current) setFailed(true);
      } finally {
        if (n === seq.current) setBusy(false);
      }
    }, 700);
    return () => clearTimeout(t);
  }, [fpId, rooms, openings]);

  const keyOf = (id: string) => [...rooms.map((r) => r.key), ...openings.map((o) => o.key)].find((k) => k.slice(0, 32) === id);
  const select = (c: PlanCheck) => { const k = keyOf(c.subject_ids[0]); if (k) onSelect(k); };
  const shown = (res?.checks ?? []).filter((c) => c.code !== "north_not_set");

  return (
    <div className="panel">
      <div className="flex items-center justify-between border-b border-hairline px-4 py-2.5">
        <p className="text-sm font-medium">AI Mistake Catcher</p>
        <span className="text-xs text-slate">{busy ? "Checking…" : res ? `${res.counts.error} errors · ${res.counts.warning} warnings` : ""}</span>
      </div>
      {failed ? <p className="px-4 py-3 text-xs text-slate">Checks are unavailable right now; you can still confirm the plan.</p>
        : !res ? <p className="px-4 py-3 text-xs text-slate">Checks appear once the plan has rooms.</p>
          : <div className="max-h-72 overflow-auto"><CheckList checks={shown} empty="No likely mistakes found." onSelect={select} /></div>}
    </div>
  );
}
