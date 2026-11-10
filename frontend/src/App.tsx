import { useCallback, useEffect, useState } from "react";
import * as api from "./api";
import ApplicationForm from "./components/ApplicationForm";
import ApplicationTable from "./components/ApplicationTable";
import type { Application, ApplicationCreate, ApplicationStatus } from "./types";

export default function App() {
  const [applications, setApplications] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Listeyi backend'den çeker. Her değişiklikten sonra yeniden çağırıyoruz
  // ki ekrandaki veri daima sunucudakiyle aynı olsun.
  const refresh = useCallback(async () => {
    try {
      setApplications(await api.listApplications());
      setError(null);
    } catch {
      setError("Sunucuya ulaşılamadı. Backend çalışıyor mu? (localhost:8000)");
    } finally {
      setLoading(false);
    }
  }, []);

  // Sayfa ilk açıldığında bir kez listeyi yükle.
  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function handleCreate(payload: ApplicationCreate) {
    try {
      await api.createApplication(payload);
      await refresh();
    } catch {
      setError("Başvuru kaydedilemedi.");
    }
  }

  async function handleStatusChange(id: number, status: ApplicationStatus) {
    try {
      await api.updateStatus(id, status);
      await refresh();
    } catch {
      setError("Durum güncellenemedi.");
    }
  }

  async function handleDelete(id: number) {
    try {
      await api.deleteApplication(id);
      await refresh();
    } catch {
      setError("Başvuru silinemedi.");
    }
  }

  return (
    <main className="container">
      <header>
        <h1>Career Copilot</h1>
        <p className="subtitle">İş başvurularını tek yerden takip et.</p>
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
