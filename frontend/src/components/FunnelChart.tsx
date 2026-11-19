import type { FunnelStep } from "../types";

// Huni: her aşama yatay bir çubuk. Uzunluk ilk aşamaya (toplam başvuru) göre.
// Grafik kütüphanesi yok: düz HTML/CSS, böylece bağımlılık da yok.
export default function FunnelChart({ steps }: { steps: FunnelStep[] }) {
  const max = steps[0]?.count ?? 0;

  return (
    <div className="funnel" role="list" aria-label="Başvuru süreci hunisi">
      {steps.map((step) => {
        const width = max > 0 ? (step.count / max) * 100 : 0;
        return (
          <div
            className="funnel-row"
            role="listitem"
            key={step.key}
            title={`${step.label}: ${step.count} başvuru (%${step.rate})`}
          >
            <span className="funnel-label">{step.label}</span>
            <div className="funnel-track">
              <div className="funnel-bar" style={{ width: `${width}%` }} />
            </div>
            <span className="funnel-value">
              {step.count}
              {step.key !== "basvuru" && <small> %{step.rate}</small>}
            </span>
          </div>
        );
      })}
    </div>
  );
}
