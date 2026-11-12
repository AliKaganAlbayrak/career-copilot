import { useCallback, useEffect, useState } from "react";
import * as api from "./api";
import ApplicationForm from "./components/ApplicationForm";
import ApplicationTable from "./components/ApplicationTable";
import AuthForm from "./components/AuthForm";
import type { Application, ApplicationCreate, ApplicationStatus } from "./types";

export default function App() {
  // Saklı bir belirteç varsa oturum açık varsayılır; geçersizse ilk
  // istekte 401 gelir ve giriş ekranına döneriz.
  const [authenticated, setAuthenticated] = useState(api.hasToken());
  const [email, setEmail] = useState<string | null>(null);
  const [applications, setApplications] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Hataları tek yerde yorumla: 401 ise oturumu kapat, değilse mesaj göster.
  const handleError = useCallback((err: unknown, fallback: string) => {
    if (err instanceof api.UnauthorizedError) {
      setAuthenticated(false);
      setError(null);
    } else {
      setError(fallback);
    }
  }, []);

  // Listeyi backend'den çeker. Her değişiklikten sonra yeniden çağırıyoruz
  // ki ekrandaki veri daima sunucudakiyle aynı olsun.
  const refresh = useCallback(async () => {
    try {
      setApplications(await api.listApplications());
      setError(null);
    } catch (err) {
      handleError(err, "Sunucuya ulaşılamadı. Backend çalışıyor mu? (localhost:8000)");
    } finally {
      setLoading(false);
    }
  }, [handleError]);

  // Oturum açılınca kullanıcı bilgisini ve listeyi yükle.
  useEffect(() => {
    if (!authenticated) {
      return;
    }
    setLoading(true);
    api
      .me()
      .then((user) => setEmail(user.email))
      .catch((err: unknown) => handleError(err, "Kullanıcı bilgisi alınamadı."));
    void refresh();
  }, [authenticated, refresh, handleError]);

  function handleLogout() {
    api.logout();
    setAuthenticated(false);
    setApplications([]);
    setEmail(null);
  }

  async function handleCreate(payload: ApplicationCreate) {
    try {
      await api.createApplication(payload);
      await refresh();
    } catch (err) {
      handleError(err, "Başvuru kaydedilemedi.");
    }
  }

  async function handleStatusChange(id: number, status: ApplicationStatus) {
    try {
      await api.updateStatus(id, status);
      await refresh();
    } catch (err) {
      handleError(err, "Durum güncellenemedi.");
    }
  }

  async function handleDelete(id: number) {
    try {
      await api.deleteApplication(id);
      await refresh();
    } catch (err) {
      handleError(err, "Başvuru silinemedi.");
    }
  }

  if (!authenticated) {
    return (
      <main className="container">
        <header>
          <h1>Career Copilot</h1>
          <p className="subtitle">İş başvurularını tek yerden takip et.</p>
        </header>
        <AuthForm onAuthenticated={() => setAuthenticated(true)} />
      </main>
    );
  }

  return (
    <main className="container">
      <header className="topbar">
        <div>
          <h1>Career Copilot</h1>
          <p className="subtitle">İş başvurularını tek yerden takip et.</p>
        </div>
        <div className="session">
          {email && <span>{email}</span>}
          <button className="link" onClick={handleLogout}>
            Çıkış
          </button>
        </div>
      </header>

      <ApplicationForm onSubmit={handleCreate} />

      {error && <p className="error">{error}</p>}

      {loading ? (
        <p className="empty">Yükleniyor…</p>
      ) : (
        <ApplicationTable
          applications={applications}
          onStatusChange={handleStatusChange}
          onDelete={handleDelete}
        />
      )}
    </main>
  );
}
