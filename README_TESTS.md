# Test scaffold — o'rnatish qo'llanmasi

## 1. Fayllarni joylashtirish

Repo tuzilishiga mos qilib quyidagicha ko'chiring (root — `manage.py` turgan joy):

```
Inventra/
├── conftest.py                                  ← shu yerga
├── pytest.ini                                   ← shu yerga
├── tests/
│   ├── __init__.py                               ← bo'sh fayl, o'zingiz yarating
│   └── factories.py                              ← shu yerga
├── apps/
│   ├── accounts/
│   │   ├── tests.py                              ← O'CHIRING (eski stub)
│   │   └── tests/
│   │       ├── __init__.py                       ← bo'sh fayl, o'zingiz yarating
│   │       ├── test_employee_service.py          ← shu yerga
│   │       └── test_otp_services.py              ← shu yerga
│   └── tenants/
│       ├── tests.py                              ← O'CHIRING (eski stub)
│       └── tests/
│           ├── __init__.py                       ← bo'sh fayl, o'zingiz yarating
│           └── test_tenant_service.py            ← shu yerga
```

`apps/accounts/tests.py` va `apps/tenants/tests.py` bir vaqtning o'zida
`tests/` papka bilan bir xil nomda tura olmaydi — albatta o'chirib, keyin
papka yarating.

## 2. Kerakli paketlarni o'rnatish

```powershell
uv add --dev pytest pytest-django factory-boy pytest-cov
```

## 3. Test infratuzilmasi — alohida Postgres va Redis

Endi testlar **dev/production bazangizga umuman tegmaydi** — `docker-compose.test.yml`
orqali ko'tariladigan alohida Postgres (port `5433`) va Redis (port `6380`)
konteynerlarida ishlaydi.

**Bir martalik sozlash:**

```powershell
copy .env.test.example .env.test
```

`.env.test` faylini o'zgartirish shart emas — standart qiymatlar
`docker-compose.test.yml`dagi portlarga mos keladi. `.env` kabi buni ham
`.gitignore`ga qo'shing.

**Har safar test yozishdan/ishga tushirishdan oldin:**

```powershell
docker compose -f docker-compose.test.yml up -d
uv run pytest
```

**Ishlab bo'lgach (ixtiyoriy — konteynerlarni butunlay o'chirish uchun):**

```powershell
docker compose -f docker-compose.test.yml down -v
```

`tmpfs` ishlatilgani uchun har safar `down -v` qilinganda ma'lumotlar
butunlay tozalanadi — bu ataylab shunday, testlar har doim toza holatdan
boshlanishi kerak. Kunlik ishlashda konteynerlarni ochiq qoldirib,
`--reuse-db` (pytest.ini'da allaqachon yoqilgan) tufayli test bazasi
qayta yaratilmay, tezroq ishlaydi.

`config/settings_test.py` — `config/settings.py`dan hamma narsani meros
oladi (`INSTALLED_APPS`, `REST_FRAMEWORK` va h.k.), faqat `DATABASES` va
`REDIS_URL`ni `.env.test`dagi qiymatlarga almashtiradi. Production
`settings.py`ga hech qanday o'zgartirish kiritilmaydi.

`pytest.ini`da `DJANGO_SETTINGS_MODULE = config.settings_test` allaqachon
ko'rsatilgan — qo'shimcha flag kerak emas, oddiy `pytest` buyrug'i yetarli.

**Tasdiqlandi**: shu sozlash bilan barcha 36 test (Redis'ga bog'liqlari
ham) haqiqiy alohida Postgres/Redis instance'lariga qarshi muvaffaqiyatli
o'tdi.

## 5. Ishga tushirish

```powershell
uv run pytest
uv run pytest --cov=apps --cov-report=term-missing   # coverage bilan
uv run pytest apps/accounts/tests/test_employee_service.py -v   # bitta fayl
```

## 6. Bu yerda yo'q narsalar (keyingi qadamlar)

- `TenantService`/`EmployeeService` uchun **concurrency** (race-condition)
  testlari — `select_for_update()` ikkita parallel so'rovda ham bitta
  faol `Employee` qolishini kafolatlashi kerak. Buni to'g'ri yozish uchun
  `threading`/`transaction.on_commit` bilan ishlash kerak — alohida
  muhokama qilib, keyin qo'shamiz.
- API/permission integratsion testlari (`APIClient` + JWT) — bularni
  yozish uchun `api/v1/tenants/views.py` va `api/v1/accounts/views/` fayllarini
  ko'rib chiqishim kerak (hali ko'rmadim). Shu fayllarni ko'rsatsangiz,
  keyingi bosqichda yozib beraman.
- `test_employee_service.py`dagi `test_owner_cannot_poach_staff_employed_at_another_tenant`
  testi — hujjatingizda o'zingiz "asimmetrik xatti-harakat" deb belgilagan
  joyni **hozirgi kod xulq-atvori** sifatida qayd etadi. Agar bu kutilgan
  bo'lmasa, `EmployeeService.hire()`dagi avtomatik-fire logikasini
  o'zgartirish kerak bo'ladi va shu testni ham yangilaymiz.
