import type { Application, ApplicationCreate, ApplicationStatus } from "./types";

const BASE_URL: string = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

// Tüm isteklerin geçtiği tek yer: hata kontrolü ve JSON çözme burada.
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });

  if (!response.ok) {
    throw new Error(`İstek başarısız oldu (${response.status})`);
  }

  // 204 No Content (silme) gövde taşımaz; JSON çözmeye çalışma.
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export function listApplications(status?: ApplicationStatus): Promise<Application[]> {
  const query = status ? `?status=${status}` : "";
  return request<Application[]>(`/applications${query}`);
}

export function createApplication(payload: ApplicationCreate): Promise<Application> {
  return request<Application>("/applications", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateStatus(id: number, status: ApplicationStatus): Promise<Application> {
  return request<Application>(`/applications/${id}`, {
    method: "PUT",
    body: JSON.stringify({ status }),
  });
}

export function deleteApplication(id: number): Promise<void> {
  return request<void>(`/applications/${id}`, { method: "DELETE" });
}
