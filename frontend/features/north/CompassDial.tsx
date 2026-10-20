"use client";
import { useRef } from "react";

const norm = (a: number) => ((Math.round(a) % 360) + 360) % 360;

/** Drag the brass needle to where true North is, relative to the plan image as shown. */
export function CompassDial({ angle, onChange }: { angle: number; onChange: (a: number) => void }) {
  const ref = useRef<SVGSVGElement>(null);
  const dragging = useRef(false);

  const fromPointer = (e: React.PointerEvent) => {
    const r = ref.current!.getBoundingClientRect();
    const dx = e.clientX - (r.left + r.width / 2), dy = e.clientY - (r.top + r.height / 2);
    let a = (Math.atan2(dx, -dy) * 180) / Math.PI;
    if (e.shiftKey) a = Math.round(a / 15) * 15;
    onChange(norm(a));
  };

  return (
    <div>
    <p className="mb-1 text-center text-xs text-slate">Top of the image</p>
    <svg ref={ref} viewBox="-110 -110 220 220" className="mx-auto block w-full max-w-[240px] touch-none select-none cursor-grab"
      role="slider" aria-label="North direction" aria-valuemin={0} aria-valuemax={359} aria-valuenow={angle}
      aria-valuetext={`${angle} degrees clockwise from the top of the image`} tabIndex={0}
      onKeyDown={(e) => {
        const step = e.shiftKey ? 15 : 1;
        if (e.key === "ArrowRight" || e.key === "ArrowUp") { e.preventDefault(); onChange(norm(angle + step)); }
        if (e.key === "ArrowLeft" || e.key === "ArrowDown") { e.preventDefault(); onChange(norm(angle - step)); }
      }}
      onPointerDown={(e) => { dragging.current = true; ref.current!.setPointerCapture(e.pointerId); fromPointer(e); }}
      onPointerMove={(e) => dragging.current && fromPointer(e)}
      onPointerUp={() => { dragging.current = false; }}>
      <circle r={98} fill="#fff" stroke="#D3DADF" strokeWidth={2} />
      {Array.from({ length: 72 }, (_, i) => i * 5).map((t) => (
        <line key={t} x1={0} y1={-98} x2={0} y2={t % 45 === 0 ? -84 : t % 15 === 0 ? -89 : -93}
          stroke={t % 45 === 0 ? "#16283A" : "#5A6B7B"} strokeWidth={t % 45 === 0 ? 2 : 1} transform={`rotate(${t})`} />
      ))}
      <g transform={`rotate(${angle})`}>
        <path d="M0 -60 L9 0 L0 -7 L-9 0Z" fill="#9C6B1C" />
        <path d="M0 50 L6 0 L-6 0Z" fill="#D3DADF" />
      </g>
      <circle r={5} fill="#16283A" />
      <text x={Math.sin((angle * Math.PI) / 180) * 72} y={-Math.cos((angle * Math.PI) / 180) * 72 + 5.5}
        textAnchor="middle" fontSize={16} fontWeight={600} fill="#9C6B1C" fontFamily="IBM Plex Sans, sans-serif">N</text>
    </svg>
    </div>
  );
}
