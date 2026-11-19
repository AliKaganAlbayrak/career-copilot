import { useState } from "react";
import type { WeekCount } from "../types";

const WIDTH = 640;
const HEIGHT = 180;
const PAD = { top: 16, right: 8, bottom: 24, left: 28 };
const BAR_MAX = 24; // çubuk kalınlığı sınırı: aralığı doldurmasın, hava kalsın

const dayMonth = new Intl.DateTimeFormat("tr-TR", { day: "numeric", month: "short" });

// Haftalık başvuru sayısı: SVG sütun grafiği, üstüne gelince ipucu gösterir.
export default function WeeklyChart({ weeks }: { weeks: WeekCount[] }) {
  const [active, setActive] = useState<number | null>(null);

  const max = Math.max(1, ...weeks.map((w) => w.count));
  const plotW = WIDTH - PAD.left - PAD.right;
  const plotH = HEIGHT - PAD.top - PAD.bottom;
  const slot = plotW / Math.max(1, weeks.length);
  const barW = Math.min(BAR_MAX, slot - 2); // komşu çubuklar arası en az 2px boşluk
  const ticks = [0, Math.ceil(max / 2), max];

  const label = (w: WeekCount) => dayMonth.format(new Date(`${w.week_start}T00:00:00`));
  const current = active !== null ? weeks[active] : null;

  return (
    <div className="weekly">
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-label="Son haftalardaki başvuru sayıları"
        onMouseLeave={() => setActive(null)}
      >
        {ticks.map((t) => {
          const y = PAD.top + plotH - (t / max) * plotH;
          return (
            <g key={t}>
              <line x1={PAD.left} x2={WIDTH - PAD.right} y1={y} y2={y} className="grid" />
              <text x={PAD.left - 6} y={y + 4} textAnchor="end" className="axis">
                {t}
              </text>
            </g>
          );
        })}

        {weeks.map((w, i) => {
          const h = (w.count / max) * plotH;
          const x = PAD.left + i * slot + (slot - barW) / 2;
          const y = PAD.top + plotH - h;
          const r = Math.min(4, h); // üst uç 4px yuvarlak, taban düz
          const path =
            h > 0
              ? `M${x},${y + h} V${y + r} Q${x},${y} ${x + r},${y} H${x + barW - r} Q${x + barW},${y} ${x + barW},${y + r} V${y + h} Z`
              : "";
          return (
            <g key={w.week_start} onMouseEnter={() => setActive(i)}>
              {/* Görünmez geniş alan: fareyle yakalamak çubuktan kolay olsun */}
              <rect x={PAD.left + i * slot} y={PAD.top} width={slot} height={plotH} fill="transparent" />
              {path && <path d={path} className={active === i ? "bar bar-active" : "bar"} />}
              {(i === 0 || i === weeks.length - 1 || i % 4 === 0) && (
                <text x={x + barW / 2} y={HEIGHT - 6} textAnchor="middle" className="axis">
                  {label(w)}
                </text>
              )}
            </g>
          );
        })}
      </svg>

      <p className="weekly-tip" aria-live="polite">
        {current
          ? `${label(current)} haftası: ${current.count} başvuru`
          : "Bir haftanın üstüne gel."}
      </p>

      {/* Ekran okuyucular ve renk görmeyenler için aynı verinin tablo hâli */}
      <table className="sr-only">
        <caption>Haftalık başvuru sayıları</caption>
        <tbody>
          {weeks.map((w) => (
            <tr key={w.week_start}>
              <th scope="row">{label(w)}</th>
              <td>{w.count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
