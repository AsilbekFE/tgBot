# 🎬 Kino Time — Web App & Telegram Bot Platformasi

Telegram Bot va zamonaviy Veb ilovani birlashtirgan kinolar platformasi.

## 🌟 Imkoniyatlar

### 👑 1. Admin Web Paneli (`http://localhost:8000/admin`)
- Telefon yoki kompyuterdan qulay boshqarish.
- **Kino qo'shish:** Kino nomi, raqamli kodi (masalan: 101, 102), tavsifi, poster URL va video havolasi (yoki fayl ID).
- **Kinolar ro'yxati:** Barcha qo'shilgan kinolarni ko'rish va o'chirish.
- **Obunachilar nazorati:** Obuna sotib olgan yoki ro'yxatdan o'tgan foydalanuvchilar ro'yxati va ularni bitta tugma bilan **Aktiv (Active)** yoki **Nofaol (Deactive)** qilish.

### 🍿 2. Foydalanuvchi Web Katalogi (`http://localhost:8000/user`)
- Barcha premyera filmlar vitrinasi (Netflix/Cinema dizayni).
- Qidiruv tizimi (nomi yoki kodi bo'yicha).
- **Telegram Stars To'lovi:**
  - Narxi: **50 ⭐️ Stars** (1 oylik obuna).
  - To'g'ridan-to'g'ri Telegramning rasmiy Stars tizimi orqali 1-bosish bilan xavfsiz to'lov.
- **Filmlarni ochish:** To'lov qilingandan so'ng barcha filmlar kodlari ochiladi va *"▶️ Botda ko'rish"* tugmasi orqali filmni botdan qabul qilib olish mumkin.

### 🤖 3. Telegram Bot (@My_agentcha_bot)
- Foydalanuvchi `/start` bosganda:
  - **Admin** bo'lsa: "👑 Admin Web Panel" tugmasi chiqadi.
  - **Oddiy user** bo'lsa: "🎬 Kinolar va Obuna (Web)" tugmasi chiqadi.
- Foydalanuvchi botga kino kodini (masalan: `101`) yozsa yoki Web katalogdan *"Botda ko'rish"*ni bossa:
  - Agar foydalanuvchi **Faol obunachi** bo'lsa: Bot unga film posteri, tavsifi va videosini darhol tashlab beradi.
  - Agar obunasi bo'lmasa: Obuna sotib olish taklif qilinadi va veb to'lov sahifasiga yo'naltiradi.

---

## 🚀 Ishga tushirish

```bash
# 1. Kerakli paketlarni o'rnatish
pip install -r requirements.txt

# 2. Server va Botni ishga tushirish
python bot.py
```

Server ishga tushgach:
- **Admin Panel:** `http://localhost:8000/admin` (yoki telefon uchun `http://10.144.34.77:8000/admin`)
- **Foydalanuvchi Web sahifasi:** `http://localhost:8000/user`
- **Telegram Bot:** [@My_agentcha_bot](https://t.me/My_agentcha_bot)
