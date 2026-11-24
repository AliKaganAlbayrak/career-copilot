import { useCallback, useEffect, useState } from "react";
import * as api from "../api";
import { STATUS_LABELS, type Email, type MailCategory, type MailConnection } from "../types";

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

// Google'dan dönüşte backend'in eklediği ?gmail=... parametresinin anlamı.
const RETURN_MESSAGES: Record<string, { ok: boolean; text: string }> = {
  baglandi: { ok: true, text: "Gmail hesabın bağlandı. Şimdi postaları tarayabilirsin." },
  iptal: { ok: false, text: "Gmail bağlantısı iptal edildi." },
  hata: { ok: false, text: "Gmail bağlanamadı. Tekrar dene." },
};

// "Aselsan İK <ik@aselsan.com.tr>" -> "Aselsan İK"
function senderName(sender: string): string {
  return sender.replace(/<[^>]*>/, "").replace(/"/g, "").trim() || sender;
}

export default function InboxPanel({ onUnauthorized, onApplicationsChanged }: Props) {
  const [emails, setEmails] = useState<Email[]>([]);
  const [connection, setConnection] = useState<MailConnection | null>(null);
  const [confirmDisconnect, setConfirmDisconnect] = useState(false);
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
    api.getMailConnection().then(setConnection).catch(handle);
  }, [handle]);

  // Google'dan dönüldüyse sonucu göster ve parametreyi adres çubuğundan temizle.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const result = params.get("gmail");
    if (result === null) {
      return;
    }
    const info = RETURN_MESSAGES[result] ?? RETURN_MESSAGES.hata;
    if (info.ok) {
      setMessage(info.text);
    } else {
      setError(info.text);
    }
    params.delete("gmail");
    const query = params.toString();
    window.history.replaceState(null, "", window.location.pathname + (query ? `?${query}` : ""));
  }, []);

  async function connect() {
    setError(null);
    try {
      await api.connectGmail();
    } catch (err) {
      handle(err);
    }
  }

  async function disconnect(deleteEmails: boolean) {
    setError(null);
    try {
      await api.disconnectMail(deleteEmails);
      setConfirmDisconnect(false);
      setConnection(await api.getMailConnection());
      if (deleteEmails) {
        setEmails([]);
      }
      setMessage("Gmail bağlantısı kaldırıldı; izin Google tarafında da geri alındı.");
    } catch (err) {
      handle(err);
    }
  }

  async function sync() {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const result = await api.syncInbox();
      setEmails(await api.listInbox());
      setConnection(await api.getMailConnection());
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

  const canSync = connection !== null && (connection.connected || connection.demo_available);

  return (
    <section className="inbox">
      <div className="inbox-head">
        <h2>Posta kutusu</h2>
        <button onClick={sync} disabled={busy || !canSync}>
          {busy ? "Taranıyor…" : "Postaları tara"}
        </button>
      </div>

      {connection && (
        <div className="connection">
          {connection.connected ? (
            <>
              <span>
                Bağlı: <strong>{connection.email_address}</strong>
                {connection.last_synced_at &&
                  ` · son tarama ${dateFormat.format(new Date(connection.last_synced_at))}`}
              </span>
              {confirmDisconnect ? (
                <span className="connection-confirm">
                  Kaydedilen e-posta özetleri de silinsin mi?
                  <button className="danger" onClick={() => disconnect(true)}>
                    Evet, sil
                  </button>
                  <button className="ghost" onClick={() => disconnect(false)}>
                    Hayır, kalsın
                  </button>
                  <button className="link" onClick={() => setConfirmDisconnect(false)}>
                    Vazgeç
                  </button>
                </span>
              ) : (
                <button className="link" onClick={() => setConfirmDisconnect(true)}>
                  Bağlantıyı kaldır
                </button>
              )}
            </>
          ) : connection.gmail_available ? (
            <>
              <span>Gmail hesabını bağla; yalnızca okuma izni istenir.</span>
              <button className="ghost" onClick={connect}>
                Gmail'i bağla
              </button>
            </>
          ) : (
            <span>
              {connection.demo_available
                ? "Gmail bağlantısı sunucuda kurulmadı; tarama örnek e-postalarla çalışıyor."
                : "Posta bağlantısı kurulmadı."}
            </span>
          )}
        </div>
      )}
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
