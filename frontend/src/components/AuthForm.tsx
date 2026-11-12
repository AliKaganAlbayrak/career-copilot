import { useState, type FormEvent } from "react";
import * as api from "../api";

interface Props {
  onAuthenticated: () => void;
}

// Tek form, iki mod: "giris" ve "kayit". Kayıt başarılı olunca
// kullanıcıyı ayrıca giriş yapmaya zorlamadan doğrudan oturum açıyoruz.
export default function AuthForm({ onAuthenticated }: Props) {
  const [mode, setMode] = useState<"giris" | "kayit">("giris");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === "kayit") {
        await api.register(email.trim(), password);
      }
      await api.login(email.trim(), password);
      onAuthenticated();
    } catch (err) {
      if (err instanceof api.UnauthorizedError) {
        setError("E-posta veya parola hatalı.");
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Bir şeyler ters gitti.");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="auth" onSubmit={handleSubmit}>
      <h2>{mode === "giris" ? "Giriş yap" : "Hesap oluştur"}</h2>
      <input
        type="email"
        placeholder="E-posta"
        autoComplete="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        required
      />
      <input
        type="password"
        placeholder="Parola (en az 8 karakter)"
        autoComplete={mode === "giris" ? "current-password" : "new-password"}
        minLength={8}
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        required
      />
      {error && <p className="error">{error}</p>}
      <button type="submit" disabled={busy}>
        {busy ? "Bekle…" : mode === "giris" ? "Giriş yap" : "Kayıt ol"}
      </button>
      <button
        type="button"
        className="link"
        onClick={() => {
          setMode(mode === "giris" ? "kayit" : "giris");
          setError(null);
        }}
      >
        {mode === "giris" ? "Hesabın yok mu? Kayıt ol" : "Zaten hesabın var mı? Giriş yap"}
      </button>
    </form>
  );
}
