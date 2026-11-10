import { STATUS_LABELS, type ApplicationStatus } from "../types";

// Her durumun kendi rengi: tabloya bakınca süreç bir bakışta okunur.
const COLORS: Record<ApplicationStatus, { background: string; color: string }> = {
  basvuruldu: { background: "#e0edff", color: "#1d4ed8" },
  mulakat: { background: "#fef3c7", color: "#92400e" },
  teklif: { background: "#ede9fe", color: "#6d28d9" },
  red: { background: "#fee2e2", color: "#b91c1c" },
  kabul: { background: "#dcfce7", color: "#15803d" },
};

export default function StatusBadge({ status }: { status: ApplicationStatus }) {
  return (
    <span className="badge" style={COLORS[status]}>
      {STATUS_LABELS[status]}
    </span>
  );
}
