"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { ErrorNote, Spinner } from "@/components/ui";
import { api } from "@/services/api";
import type { ReportLanguage, ReportVideo } from "@/types/api";

const NARRATION = {
  edge: "Narrated voice", gtts: "Narrated voice",
  silent: "Captions only: no voice was available (the voice needs an internet connection). Create it again when online.",
} as const;

function mmss(s: number | null | undefined) {
  if (s == null) return "—";
  const m = Math.floor(s / 60);
  return `${m}:${String(Math.round(s % 60)).padStart(2, "0")}`;
}

/**
 * Video report: a narrated walkthrough of the customer's own report (score, rooms that need care, remedies,
 * personal action plan), in मराठी or English, with captions drawn on screen so it also works muted.
 */
export function VideoReport({ projectId, analysed }: { projectId: string; analysed: boolean }) {
  const [videos, setVideos] = useState<ReportVideo[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [starting, setStarting] = useState<ReportLanguage | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [sharing, setSharing] = useState(false);
  const player = useRef<HTMLVideoElement>(null);

  const load = useCallback(() => api.videos(projectId).then(setVideos).catch(setError), [projectId]);
  useEffect(() => { load(); }, [load]);
  const pending = videos?.some((v) => v.status === "queued" || v.status === "running");
  useEffect(() => {
    if (!pending) return;
    const t = setInterval(load, 2000);
    return () => clearInterval(t);
  }, [pending, load]);

  async function create(language: ReportLanguage) {
    setStarting(language); setError(null);
    try { const v = await api.createVideo(projectId, language); setSelected(v.id); await load(); }
    catch (e) { setError(e); } finally { setStarting(null); }
  }
  async function retry(v: ReportVideo) {
    if (!v.job) return;
    try { await api.retryJob(v.job.id); await load(); } catch (e) { setError(e); }
  }
  async function share(v: ReportVideo) {
    if (!v.download_url) return;
    setSharing(true);
    try {
      const blob = await (await fetch(v.video_url!)).blob();
      const file = new File([blob], `vastu-video-${v.language}.mp4`, { type: "video/mp4" });
      if (navigator.canShare?.({ files: [file] })) {
        await navigator.share({ files: [file], title: "Vastu video report" });
      } else {
        window.location.href = v.download_url;
      }
    } catch { /* user cancelled */ } finally { setSharing(false); }
  }

  const ready = (videos ?? []).filter((v) => v.status === "ready");
  const current = videos?.find((v) => v.id === selected) ?? ready[0] ?? videos?.[0] ?? null;

  return (
    <section className="panel mt-6" aria-labelledby="video-h">
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-hairline px-4 py-3">
        <div>
          <h2 id="video-h" className="font-medium">Video report <span lang="mr" className="font-normal text-slate">· व्हिडिओ अहवाल</span></h2>
          <p className="mt-0.5 max-w-2xl text-sm text-ink-soft">
            A narrated walkthrough of this report, about 5 to 8 minutes: how the plan was read, the score, each room that needs care,
            the remedies step by step and the personal action plan. Captions are on screen, so it works with the sound off.
          </p>
        </div>
        <div className="flex gap-2">
          {(["mr", "en"] as const).map((l) => (
            <button key={l} lang={l} className={l === "mr" ? "btn-primary" : "btn-secondary"} disabled={!analysed || !!starting || !!pending}
              onClick={() => create(l)}>
              {starting === l && <Spinner />} {l === "mr" ? "मराठी व्हिडिओ बनवा" : "Create English video"}
            </button>
          ))}
        </div>
      </div>
      <div className="p-4"><ErrorNote error={error} /></div>

      {!videos ? <p className="px-4 pb-4 text-sm text-slate">Loading…</p> : !videos.length ? (
        <p className="px-4 pb-4 text-sm text-slate">{analysed ? "No videos yet. Choose a language to create one; it takes a minute or two." : "Run the analysis first."}</p>
      ) : current && (
        <div className="grid gap-5 px-4 pb-4 lg:grid-cols-[minmax(0,1fr)_320px]">
          <div>
            {current.status === "ready" && current.video_url ? (
              <video key={current.id} ref={player} controls playsInline preload="metadata" crossOrigin="anonymous"
                poster={current.poster_url ?? undefined} className="aspect-video w-full rounded border border-hairline bg-ink">
                <source src={current.video_url} type="video/mp4" />
                {current.captions_url && <track kind="subtitles" src={current.captions_url} srcLang={current.language}
                  label={current.language === "mr" ? "मराठी" : "English"} />}
              </video>
            ) : current.status === "failed" ? (
              <div className="flex aspect-video w-full flex-col items-center justify-center gap-3 rounded border border-major/30 bg-major-light p-6 text-center text-sm">
                <p className="text-major">{current.error ?? "The video could not be created."}</p>
                {current.job?.can_retry && <button className="btn-secondary" onClick={() => retry(current)}>Retry</button>}
              </div>
            ) : (
              <div className="flex aspect-video w-full flex-col items-center justify-center gap-3 rounded border border-hairline bg-paper p-6 text-sm">
                <p className="flex items-center gap-2 text-ink"><Spinner className="text-brass" /> Creating the {current.language === "mr" ? "मराठी" : "English"} video…</p>
                <div className="h-2 w-64 max-w-full rounded-full bg-white"><div className="h-2 rounded-full bg-brass transition-all" style={{ width: `${current.progress}%` }} /></div>
                <p className="text-xs text-slate">{current.progress}% · drawing slides and recording the narration</p>
              </div>
            )}
            {current.status === "ready" && (
              <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
                <a className="btn-secondary" href={current.download_url!}>Download MP4</a>
                <button className="btn-secondary" onClick={() => share(current)} disabled={sharing}>{sharing && <Spinner />} Share</button>
                {current.subtitles_url && <a className="btn-quiet" href={current.subtitles_url}>Subtitles (.srt)</a>}
                <span className="ml-auto text-xs text-slate">{mmss(current.duration_seconds)} · {current.scenes} scenes{!current.is_current ? " · older analysis" : ""}</span>
              </div>
            )}
            {current.status === "ready" && current.narration && (
              <p className={`mt-2 text-xs ${current.narration === "silent" ? "text-warning" : "text-slate"}`}>{NARRATION[current.narration]}</p>
            )}
          </div>
          <aside className="space-y-4">
            {current.transcript && (
              <div>
                <p className="mb-1 text-sm font-medium">Chapters</p>
                <ol className="max-h-80 divide-y divide-hairline overflow-auto rounded border border-hairline text-sm" lang={current.language}>
                  {current.transcript.map((c, i) => (
                    <li key={i}>
                      <button className="flex w-full gap-3 px-3 py-2 text-left hover:bg-paper"
                        onClick={() => { if (player.current) { player.current.currentTime = c.start; player.current.play(); } }}>
                        <span className="w-10 shrink-0 text-xs text-slate tabular-nums">{mmss(c.start)}</span><span>{c.title}</span>
                      </button>
                    </li>
                  ))}
                </ol>
              </div>
            )}
            <div>
              <p className="mb-1 text-sm font-medium">All videos</p>
              <ul className="divide-y divide-hairline rounded border border-hairline text-sm">
                {videos.map((v) => (
                  <li key={v.id}>
                    <button className={`flex w-full items-center gap-2 px-3 py-2 text-left ${v.id === current.id ? "bg-paper" : "hover:bg-paper/60"}`} onClick={() => setSelected(v.id)}>
                      <span lang={v.language}>{v.language === "mr" ? "मराठी" : "English"}</span>
                      <span className="text-xs text-slate">{new Date(v.created_at).toLocaleString()}</span>
                      <span className="ml-auto text-xs">{v.status === "ready" ? mmss(v.duration_seconds) : v.status === "failed" ? <span className="text-major">failed</span> : <span className="text-brass">{v.progress}%</span>}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          </aside>
        </div>
      )}
    </section>
  );
}
