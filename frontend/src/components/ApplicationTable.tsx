import { Fragment, useState } from "react";
import { STATUSES, STATUS_LABELS, type Application, type ApplicationStatus } from "../types";
import HistoryTimeline from "./HistoryTimeline";
import StatusBadge from "./StatusBadge";

interface Props {
  applications: Application[];
  onStatusChange: (id: number, status: ApplicationStatus) => void;
  onDelete: (id: number) => void;
}

const dateFormat = new Intl.DateTimeFormat("tr-TR", { dateStyle: "medium" });

export default function ApplicationTable({ applications, onStatusChange, onDelete }: Props) {
  // Aynı anda tek satırın geçmişi açık olsun.
  const [openId, setOpenId] = useState<number | null>(null);

  if (applications.length === 0) {
    return <p className="empty">Henüz başvuru yok. Yukarıdaki formdan ilkini ekle.</p>;
  }

  return (
    <table>
      <thead>
        <tr>
          <th>Şirket</th>
          <th>Pozisyon</th>
          <th>Konum</th>
          <th>Tarih</th>
          <th>Durum</th>
          <th>Değiştir</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        {applications.map((app) => (
          <Fragment key={app.id}>
            <tr>
              <td>
                {app.link ? (
                  <a href={app.link} target="_blank" rel="noreferrer">
                    {app.company}
                  </a>
                ) : (
                  app.company
                )}
              </td>
              <td>{app.position}</td>
              <td>{app.location ?? "—"}</td>
              <td>{dateFormat.format(new Date(app.applied_at))}</td>
              <td>
                <StatusBadge status={app.status} />
              </td>
              <td>
                <select
                  value={app.status}
                  aria-label={`${app.company} durumu`}
                  onChange={(e) => onStatusChange(app.id, e.target.value as ApplicationStatus)}
                >
                  {STATUSES.map((s) => (
                    <option key={s} value={s}>
                      {STATUS_LABELS[s]}
                    </option>
                  ))}
                </select>
              </td>
              <td className="row-actions">
                <button
                  className="link"
                  aria-expanded={openId === app.id}
                  onClick={() => setOpenId(openId === app.id ? null : app.id)}
                >
                  Geçmiş
                </button>
                <button className="danger" onClick={() => onDelete(app.id)}>
                  Sil
                </button>
              </td>
            </tr>
            {openId === app.id && (
              <tr className="history-row">
                <td colSpan={7}>
                  <HistoryTimeline id={app.id} refreshKey={app.status} />
                </td>
              </tr>
            )}
          </Fragment>
        ))}
      </tbody>
    </table>
  );
}
