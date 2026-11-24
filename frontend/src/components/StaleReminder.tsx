import { useEffect, useState } from "react";
import * as api from "../api";
import { STATUS_LABELS, type StaleApplication } from "../types";

interface Props {
  refreshKey: unknown;
  onUnauthorized: () => void;
}

const QUIET_DAYS = 14;

// "Haber var mı?": 14 gündür durumu değişmemiş, sonucu beklenen başvurular.
// Hiç yoksa hiçbir şey göstermez; dikkat dağıtmasın.
export default function StaleReminder({ refreshKey, onUnauthorized }: Props) {
  const [items, setItems] = useState<StaleApplication[]>([]);

  useEffect(() => {
    api
      .getStale(QUIET_DAYS)
      .then(setItems)
      .catch((err: unknown) => {
        if (err instanceof api.UnauthorizedError) {
          onUnauthorized();
        }
      });
  }, [refreshKey, onUnauthorized]);

  if (items.length === 0) {
    return null;
  }

  return (
    <section className="reminder" aria-label="Hatırlatma">
      <h2>Haber var mı?</h2>
      <p>
        Bu başvurulardan {QUIET_DAYS} gündür ses çıkmadı. Bir dönüş aldıysan durumu güncelle;
        almadıysan kısa bir takip e-postası göndermenin zamanı olabilir.
      </p>
      <ul>
        {items.map((item) => (
          <li key={item.id}>
            <strong>{item.company}</strong> · {item.position} ·{" "}
            {STATUS_LABELS[item.status]} · <span>{item.days_quiet} gündür değişmedi</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
