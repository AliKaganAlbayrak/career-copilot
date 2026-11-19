import { useEffect, useState } from "react";
import * as api from "../api";
import type { Stats, WeekCount } from "../types";
import FunnelChart from "./FunnelChart";
import WeeklyChart from "./WeeklyChart";

interface Props {
  // Başvuru listesi değiştikçe istatistikleri yeniden çekmek için.
  refreshKey: unknown;
  onUnauthorized: () => void;
}

export default function StatsPanel({ refreshKey, onUnauthorized }: Props) {
  const [stats, setStats] = useState<Stats | null>(null);
  const [weeks, setWeeks] = useState<WeekCount[]>([]);

  useEffect(() => {
    // İki isteği paralel gönder, ikisi de gelince ekranı güncelle.
    Promise.all([api.getStats(), api.getTimeline(12)])
      .then(([s, w]) => {
        setStats(s);
        setWeeks(w);
      })
      .catch((err: unknown) => {
        if (err instanceof api.UnauthorizedError) {
          onUnauthorized();
        }
      });
  }, [refreshKey, onUnauthorized]);

  if (!stats || stats.total === 0) {
    return null; // veri yokken boş grafik göstermenin anlamı yok
  }

  const step = (key: string) => stats.funnel.find((s) => s.key === key);

  return (
    <section className="stats">
      <h2>İstatistikler</h2>

      <div className="tiles">
        <div className="tile">
          <span className="tile-value">{stats.total}</span>
          <span className="tile-label">Toplam başvuru</span>
        </div>
        <div className="tile">
          <span className="tile-value">%{step("donus")?.rate ?? 0}</span>
          <span className="tile-label">Geri dönüş oranı</span>
        </div>
        <div className="tile">
          <span className="tile-value">%{step("mulakat")?.rate ?? 0}</span>
          <span className="tile-label">Mülakata kalma</span>
        </div>
      </div>

      <div className="stats-grid">
        <div>
          <h3>Süreç hunisi</h3>
          <FunnelChart steps={stats.funnel} />
        </div>
        <div>
          <h3>Son 12 hafta</h3>
          <WeeklyChart weeks={weeks} />
        </div>
      </div>
    </section>
  );
}
