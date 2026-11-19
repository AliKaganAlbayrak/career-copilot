import { useCallback, useEffect, useState } from "react";
import * as api from "../api";
import { STATUS_LABELS, type Email, type MailCategory } from "../types";

interface Props {
  onUnauthorized: () => void;
  // Bir öneri kabul edilince başvuru tablosu ve istatistikler yenilensin.
  onApplicationsChanged: () => void;
}

const CATEGORY: Record<MailCategory, { label: string; background: string; color: string }> = {
  mulakat_daveti: { label: "Mülakat daveti", background: "#fef3c7", color: "#92400e" },
  red: { label: "Olumsuz", background: "#fee2e2", color: "#b91c1c" },
  teklif: { label: "Teklif", background: "#ede9fe", color: "#6d28d9" },
  bilgi: { label: "Bilgilendirme", background: "#e0edff", color: "#1d4ed8" },
};

const dateFormat = new Intl.DateTimeFormat("tr-TR", { dateStyle: "medium" });

// "Aselsan İK <ik@aselsan.com.tr>" -> "Aselsan İK"
function senderName(sender: string): string {
  return sender.replace(/<[^>]*>/, "").replace(/"/g, "").trim() || sender;
}

export default function InboxPanel({ onUnauthorized, onApplicationsChanged }: Props) {
  const [emails, setEmails] = useState<Email[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handle = useCallback(
    (err: unknown) => {
      if (err instanceof api.UnauthorizedError) {
        onUnauthorized();
      } else {
        setError(err instanceof Error ? err.message : "Bir şeyler ters gitti.");
      }
    },
    [onUnauthorized],
  );

  useEffect(() => {
    api.listInbox().then(setEmails).catch(handle);
  }, [handle]);

  async function sync() {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const result = await api.syncInbox();
      setEmails(await api.listInbox());
      setMessage(
        result.new > 0
          ? `${result.scanned} e-posta tarandı, ${result.new} yeni iş e-postası bulundu.`
          : `${result.scanned} e-posta tarandı, yeni iş e-postası yok.`,
      );
    } catch (err) {
      handle(err);
    } finally {
      setBusy(false);
    }
  }

  async function decide(email: Email, accept: boolean) {
    setError(null);
    try {
      const updated = accept
        ? await api.acceptSuggestion(email.id)
        : await api.dismissSuggestion(email.id);
      setEmails((list) => list.map((e) => (e.id === updated.id ? updated : e)));
      if (accept) {
        onApplicationsChanged();
      }
    } catch (err) {
      handle(err);
    }
  }

  return (
    <section className="inbox">
      <div className="inbox-head">
        <h2>Posta kutusu</h2>
        <button onClick={sync} disabled={busy}>
          {busy ? "Taranıyor…" : "Postaları tara"}
        </button>
      </div>
      <p className="inbox-note">
        Yalnızca işle ilgili e-postalar kaydedilir; e-postanın kendisi değil, kısa özeti saklanır.
      </p>

      {message && <p className="success">{message}</p>}
      {error && <p className="error">{error}</p>}

      {emails.length === 0 ? (
        <p className="empty">Henüz iş e-postası yok. "Postaları tara" ile başla.</p>
      ) : (
        <ul className="mail-list">
          {emails.map((email) => {
            const category = CATEGORY[email.category];
            const who = email.company ?? senderName(email.sender);
            const pending =
              email.suggestion_state === "bekliyor" &&
              email.suggested_status !== null &&
              email.application_id !== null;
            return (
              <li key={email.id} className="mail">
                <div className="mail-top">
                  <strong>{who} sana e-posta attı</strong>
                  <span
                    className="badge"
                    style={{ background: category.background, color: category.color }}
                  >
                    {category.label}
                  </span>
                  <span className="mail-date">{dateFormat.format(new Date(email.received_at))}</span>
                </div>
                <p className="mail-summary">{email.summary}</p>
                <p className="mail-subject">Konu: {email.subject}</p>

                {pending && email.suggested_status && (
                  <div className="mail-actions">
                    <span>
                      Başvurunun durumu <strong>{STATUS_LABELS[email.suggested_status]}</strong>{" "}
                      olsun mu?
                    </span>
                    <button onClick={() => decide(email, true)}>Evet, güncelle</button>
                    <button className="link" onClick={() => decide(email, false)}>
                      Yoksay
                    </button>
                  </div>
                )}
                {email.suggestion_state === "kabul" && (
                  <p className="mail-done">Başvuru durumu güncellendi.</p>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
