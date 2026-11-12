import type { Application, ApplicationCreate, ApplicationStatus, User } from "./types";

const BASE_URL: string = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const TOKEN_KEY = "career-copilot-token";

// Belirteç tarayıcıda saklanır ki sayfa yenilenince oturum kapanmasın.
// localStorage bazı ortamlarda (gizli sekme vb.) hata fırlatabilir; o
// durumda sessizce vazgeçiyoruz, oturum yalnızca o sekme boyunca yaşar.
let token: string | null = null;
try {
  token = localStorage.getItem(TOKEN_KEY);
} catch {
  token = null;
}

export function hasToken(): boolean {
  return token !== null;
}

function setToken(value: string | null): void {
  token = value;
  try {
    if (value === null) {
      localStorage.removeItem(TOKEN_KEY);
    } else {
      localStorage.setItem(TOKEN_KEY, value);
    }
  } catch {
    // saklanamadıysa bellekteki kopya yeterli
  }
}

// 401 yanıtlarını diğer hatalardan ayırmak için özel hata sınıfı:
// App bunu yakalayınca kullanıcıyı giriş ekranına döndürür.
export class UnauthorizedError extends Error {}

interface RequestOptions {
  method?: string;
  body?: string;
  headers?: Record<string, string>;
}

// Tüm isteklerin geçtiği tek yer: belirteç ekleme, hata kontrolü, JSON çözme.
async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...options.headers,
  };
  if (token !== null) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${BASE_URL}${path}`, {
    method: options.method,
    body: options.body,
    headers,
  });

  if (response.status === 401) {
    setToken(null);
    throw new UnauthorizedError("Oturum geçersiz.");
  }
  if (!response.ok) {
    throw new Error(await errorMessage(response));
  }

  // 204 No Content (silme) gövde taşımaz; JSON çözmeye çalışma.
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

// Backend hataları {"detail": "..."} biçiminde döner; varsa onu göster.
async function errorMessage(response: Response): Promise<string> {
  try {
    const data: unknown = await response.json();
    if (typeof data === "object" && data !== null && "detail" in data) {
      const detail = (data as { detail: unknown }).detail;
      if (typeof detail === "string") {
        return detail;
      }
    }
  } catch {
    // gövde JSON değilse genel mesaja düş
  }
  return `İstek başarısız oldu (${response.status})`;
}

// --- Kimlik ---

export function register(email: string, password: string): Promise<User> {
  return request<User>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function login(email: string, password: string): Promise<void> {
  // OAuth2 parola akışı JSON değil form verisi bekler; alan adı "username".
  const form = new URLSearchParams({ username: email, password });
  const data = await request<{ access_token: string }>("/auth/login", {
    method: "POST",
    body: form.toString(),
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
  setToken(data.access_token);
}

export function logout(): void {
  setToken(null);
}

export function me(): Promise<User> {
  return request<User>("/auth/me");
}

// --- Başvurular ---

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
