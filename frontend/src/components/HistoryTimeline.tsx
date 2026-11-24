import { useEffect, useState } from "react";
import * as api from "../api";
import { STATUS_LABELS, type StatusChange } from "../types";

const SOURCE_LABELS: Record<StatusChange["source"], string> = {
  olusturma: "başvuru kaydedildi",
  manuel: "elle değiştirildi",
  eposta: "e-postadan güncellendi",
};

const dateFormat = new Intl.DateTimeFormat("tr-TR", { dateStyle: "medium" });

// Bir başvurunun durum geçmişi: tablodaki "Geçmiş" düğmesiyle açılır.
// refreshKey değişince (ör. durum değiştirilince) yeniden yüklenir.
export default function HistoryTimeline({ id, refreshKey }: { id: number; refreshKey: string }) {
  const [changes, setChanges] = useState<StatusChange[] | null>(null);

  useEffect(() => {
    api
      .getHistory(id)
      .then(setChanges)
      .catch(() => setChanges([]));
  }, [id, refreshKey]);

  if (changes === null) {
    return <p className="empty">Yükleniyor…</p>;
  }
  if (changes.length === 0) {
    return <p className="empty">Geçmiş kaydı yok.</p>;
  }

  return (
    <ol className="timeline">
      {changes.map((change, i) => (
        <li key={i}>
          <span className="timeline-date">{dateFormat.format(new Date(change.changed_at))}</span>
          <span>
            {change.from_status ? `${STATUS_LABELS[change.from_status]} → ` : ""}
            <strong>{STATUS_LABELS[change.to_status]}</strong>
          </span>
          <span className="timeline-source">{SOURCE_LABELS[change.source]}</span>
        </li>
      ))}
    </ol>
  );
}
