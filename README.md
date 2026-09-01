# Quick-ID

Quick-ID, kimlik ve pasaport görüntülerinden otel misafir alanlarını çıkaran bir
OCR servisidir. Syroce PMS entegrasyonunda Quick-ID yalnızca görüntüyü işler ve
yapılandırılmış sonucu döndürür; misafir ve oda kayıtlarının tek sahibi PMS'dir.

## Güvenli PMS entegrasyonu

PMS backend'i `POST /api/scan` çağrısını aşağıdaki sunucu tarafı başlıklarıyla
yapar:

```text
X-Service-Key: <QUICKID_SERVICE_KEY>
X-Acting-User: <pms-user-email>
```

`QUICKID_SERVICE_KEY` iki serviste aynı, rastgele en az 32 karakterlik sır olmalı
ve hiçbir zaman tarayıcıya gönderilmemelidir. OpenAI/Gemini anahtarları tercihen
Quick-ID ortam değişkenlerinde tutulur; PMS'den geçirilecekse yalnız HTTPS veya
aynı makinedeki loopback bağlantısı kullanılmalıdır.

## Yerel çalıştırma

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r backend/requirements.txt
export MONGO_URL=mongodb://localhost:27017
export DB_NAME=quick_id_dev
export JWT_SECRET="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
export QUICKID_SERVICE_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
cd backend && uvicorn server:app --host 127.0.0.1 --port 8099
```

PMS için `QUICKID_URL=http://127.0.0.1:8099` ve aynı
`QUICKID_SERVICE_KEY` ayarlanır. Böylece public deploy olmadan uçtan uca test
yapılabilir.

İlk bağımsız UI kullanıcısını yalnız bir kez oluşturmak gerekirse güçlü bir
parola ile `QUICKID_BOOTSTRAP_ADMIN_EMAIL` ve
`QUICKID_BOOTSTRAP_ADMIN_PASSWORD` birlikte ayarlanır. Kullanıcı oluştuktan sonra
bu iki değişken kaldırılır. Uygulama bilinen varsayılan hesap oluşturmaz.

## OCR sağlayıcıları

- `tesseract`: Yerel ve çağrı başına ücretsiz; sonuçlar kullanıcı doğrulaması ister.
- `gpt-4o-mini` / `gpt-4o`: `OPENAI_API_KEY` gerektirir.
- `gemini-flash`: `GEMINI_API_KEY` gerektirir ve Google Gen AI istemcisini kullanır.

Gerçek kimlik görselleri, veritabanı yedekleri ve `.env` dosyaları repoya
eklenmemelidir.

## Test

```bash
.venv/bin/python -m pytest backend/tests/test_unit.py tests/test_unit.py
npm ci --prefix frontend
npm run build --prefix frontend
```
