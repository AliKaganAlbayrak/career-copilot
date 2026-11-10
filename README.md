# Career Copilot

Yapay zekâ destekli iş başvuru takip platformu. Başvurularını tek yerden yönetir,
süreci istatistiklerle gösterir ve ilan + CV analizinden yola çıkarak sana özel
ön yazı üretir.

Bu projeyi kendi iş aramam için yazdım ve kendim kullanıyorum.

## Teknoloji yığını

| Katman | Teknoloji |
| --- | --- |
| Backend API | Python 3.13, FastAPI, SQLAlchemy 2.0 |
| Veritabanı | SQLite (üretimde PostgreSQL) |
| Frontend | TypeScript, React, Vite |
| Yapay zekâ | LLM API (ön yazı üretimi, ilan analizi) |
| Dağıtım | Docker, GitHub Actions CI |

## Kurulum

### Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
python -m uvicorn app.main:app --reload
```

Arayüz: <http://localhost:8000/docs> (FastAPI otomatik Swagger dokümanı)

### Testler

```powershell
cd backend
python -m pytest -q
```

## API uç noktaları

| Yöntem | Yol | Açıklama |
| --- | --- | --- |
| `GET` | `/health` | Servis durumu |
| `POST` | `/applications` | Yeni başvuru oluşturur (201) |
| `GET` | `/applications?status=&limit=&offset=` | Listeler, en yeniden eskiye |
| `GET` | `/applications/{id}` | Tek kayıt (yoksa 404) |
| `PUT` | `/applications/{id}` | Kısmi günceller |
| `DELETE` | `/applications/{id}` | Siler (204) |
| `GET` | `/stats` | Toplam sayı ve durum kırılımı |

Durum değerleri: `basvuruldu`, `mulakat`, `teklif`, `red`, `kabul`

## Yol haritası

- [x] Backend çekirdeği — CRUD, filtreleme, istatistik, testler
- [ ] Frontend — React + TypeScript, başvuru tablosu ve ekleme formu
- [ ] Kimlik doğrulama — kayıt/giriş, JWT
- [ ] Yapay zekâ — ilan ve CV analizi, ön yazı üretimi
- [ ] Grafikler — süreç hunisi ve zaman serisi
- [ ] Docker, canlıya alma, paylaşılabilir demo

## Katkı düzeni

Commit mesajları [Conventional Commits](https://www.conventionalcommits.org/) biçiminde:

```
feat(api): başvuru listesine durum filtresi ekle
fix(db): applied_at alanı UTC'ye çevrildi
test(api): kısmi güncelleme senaryosu eklendi
docs: README kurulum adımları güncellendi
```

Her özellik kendi dalında geliştirilir (`feat/frontend-setup`), PR ile `main`'e
birleşir ve CI testleri geçmeden birleştirilmez.
