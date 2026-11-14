import { useEffect, useState } from "react";
import * as api from "../api";
import type { AnalysisResult } from "../types";

interface Props {
  // 401 gelirse App'e haber ver ki giriş ekranına dönsün.
  onUnauthorized: () => void;
}

type Busy = "cv" | "analiz" | "yazi" | null;

export default function AiPanel({ onUnauthorized }: Props) {
  const [cv, setCv] = useState("");
  const [job, setJob] = useState("");
  const [company, setCompany] = useState("");
  const [position, setPosition] = useState("");
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [letter, setLetter] = useState("");
  const [busy, setBusy] = useState<Busy>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Kayıtlı özgeçmişi bir kez yükle.
  useEffect(() => {
    api
      .getCv()
      .then(setCv)
      .catch((err: unknown) => {
        if (err instanceof api.UnauthorizedError) {
          onUnauthorized();
        }
      });
  }, [onUnauthorized]);

  // Üç düğmenin ortak iskeleti: meşgul durumu, hata yakalama, temizlik.
  async function run(kind: Exclude<Busy, null>, action: () => Promise<void>) {
    setBusy(kind);
    setError(null);
    setMessage(null);
    try {
      await action();
    } catch (err) {
      if (err instanceof api.UnauthorizedError) {
        onUnauthorized();
      } else {
        setError(err instanceof Error ? err.message : "Bir şeyler ters gitti.");
      }
    } finally {
      setBusy(null);
    }
  }

  const jobReady = job.trim().length >= 30;

  return (
    <section className="ai">
      <h2>Yapay zekâ asistanı</h2>

      <label>
        Özgeçmişin (düz metin)
        <textarea
          rows={6}
          value={cv}
          onChange={(e) => setCv(e.target.value)}
          placeholder="Özgeçmişini buraya yapıştır; bir kez kaydetmen yeterli."
        />
      </label>
      <button
        disabled={busy !== null || cv.trim() === ""}
        onClick={() =>
          run("cv", async () => {
            await api.saveCv(cv);
            setMessage("Özgeçmiş kaydedildi.");
          })
        }
      >
        {busy === "cv" ? "Kaydediliyor…" : "Özgeçmişi kaydet"}
      </button>

      <label>
        İş ilanı
        <textarea
          rows={6}
          value={job}
          onChange={(e) => setJob(e.target.value)}
          placeholder="İlan metnini buraya yapıştır (en az 30 karakter)."
        />
      </label>

      <div className="ai-row">
        <input placeholder="Şirket" value={company} onChange={(e) => setCompany(e.target.value)} />
        <input
          placeholder="Pozisyon"
          value={position}
          onChange={(e) => setPosition(e.target.value)}
        />
      </div>

      <div className="ai-row">
        <button
          disabled={busy !== null || !jobReady}
          onClick={() =>
            run("analiz", async () => {
              setAnalysis(await api.analyze(job.trim()));
            })
          }
        >
          {busy === "analiz" ? "Analiz ediliyor…" : "Eşleşmeyi analiz et"}
        </button>
        <button
          disabled={busy !== null || !jobReady || company.trim() === "" || position.trim() === ""}
          onClick={() =>
            run("yazi", async () => {
              setLetter(
                await api.coverLetter({
                  job_description: job.trim(),
                  company: company.trim(),
                  position: position.trim(),
                  language: "tr",
                }),
              );
            })
          }
        >
          {busy === "yazi" ? "Yazılıyor…" : "Ön yazı üret"}
        </button>
      </div>

      {message && <p className="success">{message}</p>}
      {error && <p className="error">{error}</p>}

      {analysis && (
        <div className="ai-result">
          <p className="score">Eşleşme: %{analysis.match_score}</p>
          {analysis.summary && <p>{analysis.summary}</p>}
          <div className="ai-columns">
            <div>
              <h3>Güçlü yönler</h3>
              <ul>
                {analysis.strengths.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
            <div>
              <h3>Eksikler</h3>
              <ul>
                {analysis.gaps.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {letter && (
        <div className="ai-result">
          <h3>Ön yazı</h3>
          <p className="letter">{letter}</p>
        </div>
      )}
    </section>
  );
}
