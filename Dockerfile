# inventra/Dockerfile

# --- Base image ---
# Siz loyihada Python 3.12 ishlatganingiz uchun shu versiyaning
# "slim" variantidan foydalanamiz — to'liq image emas, faqat kerakli
# minimal narsalar bor, hajmi kichikroq.
FROM python:3.12-slim

# --- Tizim darajasidagi bog'liqliklar ---
# build-essential: gevent kabi ba'zi paketlar C-kod compile qiladi, shu
#   kutubxonalar bo'lmasa o'rnatish paytida xato beradi.
# curl: keyinchalik healthcheck qo'shsangiz kerak bo'ladi (hozir shart
#   emas, lekin zarar qilmaydi va kichik).
# Bitta RUN qatorida bajarish va apt cache'ni tozalash — image hajmini
# kichik ushlab turish uchun standart amaliyot.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# --- uv package manager ---
# Rasmiy uv image'idan tayyor binary fayllarni nusxalab olamiz,
# o'zimiz pip orqali o'rnatishimiz shart emas — bu tezroq va ishonchliroq.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# --- Ish papkasi ---
WORKDIR /app

# --- Avval faqat dependency fayllarini nusxalash ---
# Bu qator MUHIM: agar butun kodni birdan nusxalasangiz, kod ichida
# bitta qator o'zgarganda ham Docker "uv sync" qatorini qayta bajaradi
# (cache buziladi), bu esa har safar barcha paketlarni qayta yuklab
# o'rnatishga majbur qiladi — sekin va internet trafigini isrof qiladi.
# Faqat shu ikki faylni avval nusxalab, keyin sync qilsak, kod
# o'zgarganda faqat KOD qatlami qayta yig'iladi, paketlar cache'dan
# olinadi.
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-install-project

# --- Qolgan loyiha kodini nusxalash ---
COPY . .

# Loyihaning o'zini ham paket sifatida o'rnatish (agar pyproject.toml
# shunday sozlangan bo'lsa; aks holda bu qator zararsiz o'tib ketadi).
RUN uv sync --frozen

# --- Virtual environment'ni PATH'ga qo'shish ---
# uv paketlarni /app/.venv ichiga o'rnatadi, shuni PATH'ga qo'shmasak,
# "gunicorn: command not found" kabi xato chiqadi.
ENV PATH="/app/.venv/bin:$PATH"

# --- entrypoint.sh ni bajariladigan qilib belgilash ---
# Avval Windows'da saqlangan bo'lsa paydo bo'ladigan CRLF (\r\n) qator
# oxirlarini LF (\n) ga o'giramiz — "exec format error" xatosining eng
# ko'p uchraydigan sababi shu. "sed" buyrug'i har bir qatordagi "\r"
# belgisini olib tashlaydi.
RUN sed -i 's/\r$//' entrypoint.sh && chmod +x entrypoint.sh

# --- Port haqida hujjatlashtirish ---
# Bu qator real portni ochmaydi (docker-compose.yml da ochiladi),
# faqat "bu konteyner shu portda ishlaydi" degan ma'lumot beradi.
EXPOSE 8000

# --- Har doim bajariladigan qism ---
# entrypoint.sh migratsiyani bajaradi, keyin CMD orqali kelgan
# buyruqni ishga tushiradi.
ENTRYPOINT ["./entrypoint.sh"]

# --- entrypoint.sh ga argument sifatida uzatiladigan buyruq ---
# gunicorn config wsgi modulini nomlaydi ("config" — Django project
# papkangiz nomi, agar boshqacha bo'lsa shu joyni moslashtiring)
# va -c orqali gunicorn.conf.py faylidagi sozlamalarni o'qiydi.
CMD ["gunicorn", "config.wsgi:application", "-c", "gunicorn.conf.py"]
