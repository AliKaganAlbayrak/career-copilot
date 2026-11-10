import { useState, type FormEvent } from "react";
import { STATUSES, STATUS_LABELS, type ApplicationCreate, type ApplicationStatus } from "../types";

interface Props {
  onSubmit: (payload: ApplicationCreate) => Promise<void>;
}

export default function ApplicationForm({ onSubmit }: Props) {
  // Her girdi "kontrollü": değeri React state'inde tutulur.
  const [company, setCompany] = useState("");
  const [position, setPosition] = useState("");
  const [location, setLocation] = useState("");
  const [link, setLink] = useState("");
  const [status, setStatus] = useState<ApplicationStatus>("basvuruldu");
  const [saving, setSaving] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); // sayfanın yenilenmesini engelle
    setSaving(true);
    try {
      await onSubmit({
        company: company.trim(),
        position: position.trim(),
        status,
        // Boş metin yerine alanı hiç gönderme: backend null olarak saklar.
        location: location.trim() || undefined,
        link: link.trim() || undefined,
      });
      setCompany("");
      setPosition("");
      setLocation("");
      setLink("");
      setStatus("basvuruldu");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className="form" onSubmit={handleSubmit}>
      <input
        placeholder="Şirket *"
        value={company}
        onChange={(e) => setCompany(e.target.value)}
        required
      />
      <input
        placeholder="Pozisyon *"
        value={position}
        onChange={(e) => setPosition(e.target.value)}
        required
      />
      <input placeholder="Konum" value={location} onChange={(e) => setLocation(e.target.value)} />
      <input
        placeholder="İlan linki"
        type="url"
        value={link}
        onChange={(e) => setLink(e.target.value)}
      />
      <select value={status} onChange={(e) => setStatus(e.target.value as ApplicationStatus)}>
        {STATUSES.map((s) => (
          <option key={s} value={s}>
            {STATUS_LABELS[s]}
          </option>
        ))}
      </select>
      <button type="submit" disabled={saving}>
        {saving ? "Kaydediliyor…" : "Ekle"}
      </button>
    </form>
  );
}
