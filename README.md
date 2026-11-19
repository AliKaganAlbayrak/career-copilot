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
| Yapay zekâ | Ollama ile yerel LLM (ön yazı üretimi, ilan analizi) |
| Dağıtım | Docker, GitHub Actions CI |

## Kurulum

### Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
alembic upgrade head
python -m uvicorn app.main:app --reload
```

Arayüz: <http://localhost:8000/docs> (FastAPI otomatik Swagger dokümanı)

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Arayüz: <http://localhost:5173> (backend'in 8000 portunda çalışıyor olması gerekir)

### Testler

```powershell
cd backend
python -m pytest -q
```

## API uç noktaları

| Yöntem | Yol | Açıklama |
| --- | --- | --- |
| `GET` | `/health` | Servis durumu |
| `POST` | `/auth/register` | Kullanıcı kaydı (201, e-posta kayıtlıysa 409) |
| `POST` | `/auth/login` | Giriş; JWT erişim belirteci döner |
| `GET` | `/auth/me` | Oturum sahibinin bilgileri |
| `POST` | `/applications` | Yeni başvuru oluşturur (201) |
| `GET` | `/applications?status=&limit=&offset=` | Listeler, en yeniden eskiye |
| `GET` | `/applications/{id}` | Tek kayıt (yoksa 404) |
| `PUT` | `/applications/{id}` | Kısmi günceller |
| `DELETE` | `/applications/{id}` | Siler (204) |
| `GET` | `/stats` | Toplam sayı, durum kırılımı ve süreç hunisi |
| `GET` | `/stats/timeline?weeks=12` | Son N haftanın haftalık başvuru sayıları |
| `POST` | `/inbox/sync?days=14` | Postaları tarar, işle ilgili olanları sınıflandırıp kaydeder |
| `GET` | `/inbox` | İş e-postaları ve durum önerileri |
| `POST` | `/inbox/{id}/accept` · `/dismiss` | Öneriyi uygular / yok sayar |
| `GET` / `PUT` | `/ai/cv` | Özgeçmiş metnini okur / kaydeder |
| `POST` | `/ai/analyze` | İlan + özgeçmiş eşleşme analizi (puan, güçlü yönler, eksikler) |
| `POST` | `/ai/cover-letter` | Kişiye özel ön yazı üretir |

`/applications` ve `/stats` uç noktaları `Authorization: Bearer <belirteç>` başlığı ister;
her kullanıcı yalnızca kendi başvurularını görür. Parolalar scrypt ile tuzlanıp özetlenir.

Durum değerleri: `basvuruldu`, `mulakat`, `teklif`, `red`, `kabul`

## Veritabanı göçleri

Şema [Alembic](https://alembic.sqlalchemy.org) ile yönetilir; tablolar uygulama açılırken
değil, göçlerle oluşturulur. Böylece model değiştiğinde mevcut veri silinmeden şema güncellenir.

```powershell
cd backend
alembic upgrade head                         # bekleyen göçleri uygula
alembic revision --autogenerate -m "baslik"  # model değişikliğinden yeni göç üret
alembic downgrade -1                         # son göçü geri al
```

`tests/test_migrations.py`, göçlerin modellerle birebir aynı şemayı ürettiğini ve geri
alınabildiğini doğrular; göç yazmayı unutmak CI'da yakalanır.

## Yapay zekâ

Analiz ve ön yazı, bilgisayarında çalışan [Ollama](https://ollama.com) üzerinden üretilir;
özgeçmişin ve ilan metni dışarıya gönderilmez.

```powershell
ollama pull llama3
```

Model `OLLAMA_MODEL`, adres `OLLAMA_URL` ortam değişkeniyle değiştirilebilir. Kod yalnızca
`LLMClient` arayüzünü tanır; başka bir sağlayıcı eklemek tek bir sınıf yazmaktır.
Testler gerçek model yerine sahte bir istemci kullanır.

## Posta kutusu

Uygulama posta kutusunu tarar, işle ilgili e-postaları bulur ve "Aselsan sana e-posta attı:
25 Kasım'da teknik mülakata davet ediliyorsun" gibi özetler. E-posta bir başvuruyla
eşleşirse durum önerisi çıkar (ör. Başvuruldu → Mülakat); **durum kendiliğinden değişmez**,
kullanıcı onaylar.

1. **Ön eleme (kural tabanlı):** takip edilen bir şirketten gelmeyen ve iş sözcüğü içermeyen
   e-postalar modele hiç gönderilmez.
2. **Sınıflandırma (yerel LLM):** mülakat daveti / olumsuz / teklif / bilgilendirme ve tek
   cümlelik özet.
3. **Eşleştirme:** şirket adı ve gönderen alan adıyla (`ik@aselsan.com.tr` → Aselsan).

Gizlilik: e-postanın gövdesi saklanmaz, yalnızca gönderen, konu, tarih ve özet tutulur;
işle ilgisiz e-postalar hiç kaydedilmez. Sağlayıcı `MailProvider` arayüzünün arkasında;
şu an `MAIL_PROVIDER=demo` örnek e-postalarla çalışır, Gmail sağlayıcısı (OAuth) sıradaki adım.

## Yol haritası

- [x] Backend çekirdeği — CRUD, filtreleme, istatistik, testler
- [x] Frontend — React + TypeScript, başvuru tablosu ve ekleme formu
- [x] Kimlik doğrulama — kayıt/giriş, JWT, kullanıcıya özel veri
- [x] Yapay zekâ — ilan ve CV analizi, ön yazı üretimi (yerel LLM)
- [x] Grafikler — süreç hunisi ve haftalık başvuru grafiği (kütüphanesiz SVG)
- [x] Posta kutusu — iş e-postalarını sınıflandırma ve durum önerisi (demo sağlayıcı)
- [ ] Gmail bağlantısı — OAuth ile gerçek posta kutusu
- [ ] Durum geçmişi — huninin mülakat sonrası redleri de doğru sayması için
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
