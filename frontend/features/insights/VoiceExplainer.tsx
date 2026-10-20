"use client";
import { useEffect, useRef, useState } from "react";
import { api } from "@/services/api";
import type { VoiceScript } from "@/types/insights";
import { InsightState, Panel, StaleNote, ToolIntro, useInsight } from "./shared";

type Lang = "en" | "mr";

/** Picks the best installed voice for a BCP-47 tag (mr-IN, en-IN), falling back to the base language. */
function pickVoice(tag: string): SpeechSynthesisVoice | null {
  const voices = typeof window !== "undefined" && "speechSynthesis" in window ? window.speechSynthesis.getVoices() : [];
  const base = tag.split("-")[0];
  return voices.find((v) => v.lang.replace("_", "-") === tag) ?? voices.find((v) => v.lang.toLowerCase().startsWith(base)) ?? null;
}

export function VoiceExplainer({ projectId }: { projectId: string }) {
  const [lang, setLang] = useState<Lang>("mr");
  const { data: d, error, noAnalysis, reload } = useInsight(() => api.voice(projectId, lang), [projectId, lang]);
  const [playing, setPlaying] = useState<number | null>(null);
  const [paused, setPaused] = useState(false);
  const [rate, setRate] = useState(0.95);
  const [voice, setVoice] = useState<SpeechSynthesisVoice | null | undefined>(undefined);
  const queue = useRef<number>(0);
  const supported = typeof window !== "undefined" && "speechSynthesis" in window;

  useEffect(() => {
    if (!supported || !d) return;
    const update = () => setVoice(pickVoice(d.voice_lang));
    update();
    window.speechSynthesis.addEventListener?.("voiceschanged", update);
    return () => window.speechSynthesis.removeEventListener?.("voiceschanged", update);
  }, [d, supported]);
  useEffect(() => () => { if (supported) window.speechSynthesis.cancel(); }, [supported]);
  useEffect(() => { stop(); }, [lang]); // eslint-disable-line react-hooks/exhaustive-deps

  function speakFrom(script: VoiceScript, i: number) {
    if (i >= script.segments.length) { setPlaying(null); return; }
    const u = new SpeechSynthesisUtterance(script.segments[i].speech);
    u.lang = script.voice_lang; u.rate = rate;
    const v = pickVoice(script.voice_lang);
    if (v) u.voice = v;
    const token = queue.current;
    u.onend = () => { if (queue.current === token) speakFrom(script, i + 1); };
    u.onerror = () => { if (queue.current === token) setPlaying(null); };
    setPlaying(i);
    window.speechSynthesis.speak(u);
  }
  function play(from = 0) {
    if (!d || !supported) return;
    queue.current += 1;
    window.speechSynthesis.cancel(); setPaused(false);
    speakFrom(d, from);
  }
  function stop() { if (!supported) return; queue.current += 1; window.speechSynthesis.cancel(); setPlaying(null); setPaused(false); }
  function togglePause() {
    if (!supported) return;
    if (paused) { window.speechSynthesis.resume(); setPaused(false); } else { window.speechSynthesis.pause(); setPaused(true); }
  }
  function download() {
    if (!d) return;
    const blob = new Blob([d.full_text], { type: "text/plain;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = `vastu-summary-${lang}.txt`;
    document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(a.href);
  }

  return (
    <div className="space-y-5">
      <ToolIntro slug="voice">
        <div className="flex rounded border border-hairline bg-white p-0.5 text-sm" role="group" aria-label="Language">
          {([["mr", "मराठी"], ["en", "English"]] as const).map(([v, l]) => (
            <button key={v} lang={v} aria-pressed={lang === v} onClick={() => setLang(v)}
              className={`rounded px-3 py-1 ${lang === v ? "bg-ink text-white" : "text-ink-soft"}`}>{l}</button>
          ))}
        </div>
      </ToolIntro>
      {!d ? <InsightState projectId={projectId} error={error} noAnalysis={noAnalysis} reload={reload} /> : (
        <>
          <StaleNote stale={d.stale} projectId={projectId} />
          <section className="panel flex flex-wrap items-center gap-3 p-4">
            <button className="btn-primary min-w-[120px]" onClick={() => (playing == null ? play(0) : togglePause())} disabled={!supported}>
              {playing == null ? "▶ Play summary" : paused ? "▶ Resume" : "❚❚ Pause"}
            </button>
            <button className="btn-secondary" onClick={stop} disabled={playing == null}>■ Stop</button>
            <label className="flex items-center gap-2 text-sm text-ink-soft">Speed
              <select className="rounded border border-hairline bg-white px-2 py-1" value={rate} onChange={(e) => setRate(Number(e.target.value))}>
                {[0.8, 0.95, 1.1].map((r) => <option key={r} value={r}>{r === 0.8 ? "Slow" : r === 0.95 ? "Normal" : "Fast"}</option>)}
              </select></label>
            <button className="btn-quiet ml-auto" onClick={download}>Download text</button>
            <p className="w-full text-xs text-slate">
              {!supported ? "This browser can't speak text aloud. Read the summary below or download it."
                : voice === null ? `No ${lang === "mr" ? "Marathi" : "English (India)"} voice is installed on this device, so the browser will use its default voice. On Android, install the Marathi voice in Google Text-to-speech settings.`
                : voice ? `Voice: ${voice.name}. Audio is made on this device; nothing is uploaded.` : ""}
            </p>
          </section>
          <Panel title={lang === "mr" ? "सारांश" : "Summary"}>
            <ol className="divide-y divide-hairline">
              {d.segments.map((s, i) => (
                <li key={s.id} className={`grid gap-1 px-4 py-3 sm:grid-cols-[160px_1fr] ${playing === i ? "bg-brass-light/50" : ""}`} lang={lang}>
                  <button className="text-left text-sm font-medium hover:underline" onClick={() => play(i)} disabled={!supported}
                    aria-label={`Play from ${s.title}`}>{playing === i ? "▶ " : ""}{s.title}</button>
                  <p className="text-[15px] leading-relaxed text-ink-soft">{s.text}</p>
                </li>
              ))}
            </ol>
          </Panel>
        </>
      )}
    </div>
  );
}
