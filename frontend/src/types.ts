// Backend'deki ApplicationStatus enum'unun TypeScript karşılığı.
// "as const" sayesinde dizi hem çalışma zamanında (select seçenekleri)
// hem de tip olarak (ApplicationStatus) kullanılabiliyor.
export const STATUSES = ["basvuruldu", "mulakat", "teklif", "red", "kabul"] as const;

export type ApplicationStatus = (typeof STATUSES)[number];

export const STATUS_LABELS: Record<ApplicationStatus, string> = {
  basvuruldu: "Başvuruldu",
  mulakat: "Mülakat",
  teklif: "Teklif",
  red: "Red",
  kabul: "Kabul",
};

// API'nin döndürdüğü kayıt (backend schemas.Application).
export interface Application {
  id: number;
  company: string;
  position: string;
  status: ApplicationStatus;
  location: string | null;
  link: string | null;
  notes: string | null;
  applied_at: string; // ISO 8601 tarih metni
}

// POST /applications gövdesi.
export interface ApplicationCreate {
  company: string;
  position: string;
  status: ApplicationStatus;
  location?: string;
  link?: string;
  notes?: string;
}

// GET /auth/me ve POST /auth/register çıktısı.
export interface User {
  id: number;
  email: string;
  created_at: string;
}

// POST /ai/analyze çıktısı.
export interface AnalysisResult {
  match_score: number; // 0-100
  strengths: string[];
  gaps: string[];
  summary: string;
}

// POST /ai/cover-letter gövdesi.
export interface CoverLetterRequest {
  job_description: string;
  company: string;
  position: string;
  language: "tr" | "en";
}

// GET /stats çıktısı.
export interface FunnelStep {
  key: string;
  label: string;
  count: number;
  rate: number; // yüzde
}

export interface Stats {
  total: number;
  by_status: Record<ApplicationStatus, number>;
  funnel: FunnelStep[];
}

// GET /stats/timeline çıktısı: haftalık başvuru sayısı.
export interface WeekCount {
  week_start: string; // YYYY-MM-DD, pazartesi
  count: number;
}

// GET /inbox kaydı.
export type MailCategory = "mulakat_daveti" | "red" | "teklif" | "bilgi";
export type SuggestionState = "yok" | "bekliyor" | "kabul" | "yoksayildi";

export interface Email {
  id: number;
  sender: string;
  subject: string;
  received_at: string;
  category: MailCategory;
  summary: string;
  company: string | null;
  application_id: number | null;
  suggested_status: ApplicationStatus | null;
  suggestion_state: SuggestionState;
}

export interface SyncResult {
  scanned: number;
  job_related: number;
  new: number;
}
