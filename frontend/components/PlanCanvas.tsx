"use client";
import type { Pt, Zone } from "@/types/api";

export interface CanvasRoom {
  id: string;
  label: string;
  polygon: Pt[];
  fill?: string;
  stroke?: string;
  sublabel?: string;
  highlighted?: boolean;
}
export interface CanvasOpening { id: string; kind: string; position: Pt; is_main_entrance: boolean }

export interface PlanLayers { zones: boolean; rooms: boolean; labels: boolean; centre: boolean; openings: boolean }
export const ALL_LAYERS: PlanLayers = { zones: true, rooms: true, labels: true, centre: true, openings: true };

export const centroid = (poly: Pt[]): Pt => {
  let a = 0, cx = 0, cy = 0;
  for (let i = 0; i < poly.length; i++) {
    const [x1, y1] = poly[i];
    const [x2, y2] = poly[(i + 1) % poly.length];
    const f = x1 * y2 - x2 * y1;
    a += f; cx += (x1 + x2) * f; cy += (y1 + y2) * f;
  }
  if (Math.abs(a) < 1e-9) {
    const n = poly.length || 1;
    return [poly.reduce((s, p) => s + p[0], 0) / n, poly.reduce((s, p) => s + p[1], 0) / n];
  }
  return [cx / (3 * a), cy / (3 * a)];
};
const pts = (poly: Pt[]) => poly.map((p) => p.join(",")).join(" ");

/**
 * Read-only plan view. Everything is drawn in the image's own pixel space, so backend
 * geometry (rooms, zones, centre) lines up with the picture without conversion.
 * north_angle is degrees clockwise from the image's top edge to true North.
 */
export function PlanCanvas({
  imageUrl, width, height, rooms = [], openings = [], zones = [], centre, northAngle,
  layers = ALL_LAYERS, northUp = false, onRoomClick, className = "",
}: {
  imageUrl: string; width: number; height: number;
  rooms?: CanvasRoom[]; openings?: CanvasOpening[]; zones?: Zone[];
  centre?: Pt | null; northAngle?: number | null;
  layers?: PlanLayers; northUp?: boolean; onRoomClick?: (id: string) => void; className?: string;
}) {
  const u = Math.max(width, height) / 100;
  const pad = u * 9;
  const cx = width / 2, cy = height / 2;
  // When rotating North-up the view becomes a square around the diagonal so nothing is clipped.
  const diag = Math.hypot(width, height);
  const vb = northUp && northAngle != null
    ? [cx - diag / 2 - pad, cy - diag / 2 - pad, diag + 2 * pad, diag + 2 * pad]
    : [-pad, -pad, width + 2 * pad, height + 2 * pad];
  const rot = northUp && northAngle != null ? -northAngle : 0;

  return (
    <svg viewBox={vb.join(" ")} className={`block h-auto w-full select-none ${className}`} role="img"
      aria-label="Floor plan with Vastu overlay">
      <g transform={`rotate(${rot} ${cx} ${cy})`}>
        <rect x={0} y={0} width={width} height={height} fill="#fff" />
        <image href={imageUrl} x={0} y={0} width={width} height={height} preserveAspectRatio="none" />

        {layers.zones && zones.map((z) => {
          const [zx, zy] = centroid(z.polygon);
          return (
            <g key={z.code}>
              <polygon points={pts(z.polygon)} fill="none" stroke="#9C6B1C" strokeWidth={u * 0.28} strokeDasharray={`${u} ${u * 0.7}`} opacity={0.85} />
              <text x={zx} y={zy} textAnchor="middle" dominantBaseline="middle" fontSize={u * 3.6} fill="#9C6B1C" opacity={0.35}
                fontFamily="IBM Plex Sans, sans-serif" fontWeight={600} transform={`rotate(${-rot} ${zx} ${zy})`}>
                {z.code}
              </text>
            </g>
          );
        })}

        {layers.rooms && rooms.map((r) => (
          <polygon key={r.id} points={pts(r.polygon)} fill={r.fill ?? "rgba(22,40,58,0.04)"}
            stroke={r.stroke ?? "#16283A"} strokeWidth={u * (r.highlighted ? 0.6 : 0.25)}
            className={onRoomClick ? "cursor-pointer" : undefined} onClick={() => onRoomClick?.(r.id)} />
        ))}

        {layers.openings && openings.map((o) => (
          <g key={o.id} transform={`translate(${o.position[0]} ${o.position[1]})`}>
            {o.is_main_entrance ? (
              <>
                <circle r={u * 1.9} fill="#16283A" />
                <text textAnchor="middle" dominantBaseline="central" fontSize={u * 1.8} fill="#fff" fontFamily="IBM Plex Sans, sans-serif"
                  fontWeight={600} transform={`rotate(${-rot})`}>E</text>
              </>
            ) : o.kind === "door"
              ? <rect x={-u * 0.9} y={-u * 0.9} width={u * 1.8} height={u * 1.8} fill="#fff" stroke="#16283A" strokeWidth={u * 0.3} />
              : <circle r={u * 0.8} fill="#fff" stroke="#5A6B7B" strokeWidth={u * 0.3} />}
          </g>
        ))}

        {layers.labels && rooms.map((r) => {
          const [x, y] = centroid(r.polygon);
          return (
            <g key={r.id} transform={`rotate(${-rot} ${x} ${y})`} pointerEvents="none">
              <text x={x} y={y} textAnchor="middle" fontSize={u * 1.9} fill="#16283A" fontFamily="IBM Plex Sans, sans-serif" fontWeight={500}
                paintOrder="stroke" stroke="#fff" strokeWidth={u * 0.5} strokeLinejoin="round">{r.label}</text>
              {r.sublabel && (
                <text x={x} y={y + u * 2.4} textAnchor="middle" fontSize={u * 1.55} fill="#5A6B7B" fontFamily="IBM Plex Sans, sans-serif"
                  paintOrder="stroke" stroke="#fff" strokeWidth={u * 0.5} strokeLinejoin="round">{r.sublabel}</text>
              )}
            </g>
          );
        })}

        {layers.centre && centre && (
          <g transform={`translate(${centre[0]} ${centre[1]})`} pointerEvents="none">
            <circle r={u * 2.6} fill="none" stroke="#9C6B1C" strokeWidth={u * 0.35} />
            <path d={`M${-u * 4} 0H${u * 4}M0 ${-u * 4}V${u * 4}`} stroke="#9C6B1C" strokeWidth={u * 0.35} />
          </g>
        )}
      </g>

      {northAngle != null && <NorthArrow x={vb[0] + vb[2] - pad * 0.55} y={vb[1] + pad * 0.6} size={u * 2.7} angle={northAngle + rot} />}
    </svg>
  );
}

/** North arrow pointing `angle` degrees clockwise from screen-up. */
export function NorthArrow({ x, y, size, angle }: { x: number; y: number; size: number; angle: number }) {
  return (
    <g transform={`translate(${x} ${y})`} aria-label="North">
      <circle r={size * 1.6} fill="#fff" stroke="#D3DADF" strokeWidth={size * 0.08} />
      <g transform={`rotate(${angle})`}>
        <path d={`M0 ${-size * 0.62}L${size * 0.34} ${size * 0.62}L0 ${size * 0.38}L${-size * 0.34} ${size * 0.62}Z`} fill="#9C6B1C" />
        <text y={-size * 0.85} textAnchor="middle" fontSize={size * 0.55} fill="#9C6B1C" fontWeight={600}
          fontFamily="IBM Plex Sans, sans-serif">N</text>
      </g>
    </g>
  );
}
