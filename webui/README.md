# Vikipediya Tarjimon — Veb-interfeys

Terminalga kirmasdan, brauzer orqali maqola tarjima qilish uchun mahalliy
veb-interfeys. Har bir hamkasb buni **o'z Windows kompyuterida** o'rnatadi va
ishlatadi — markazlashgan server emas, har kimning o'z API kaliti va o'z
tarjimalari.

## Bir martalik sozlash

1. Avval loyihaning asosiy sozlashini bajaring (agar hali qilmagan bo'lsangiz)
   — repo ildizidagi `CLAUDE.md`/`README.md`ga qarang:
   - `python -m venv .venv`
   - `.venv\Scripts\pip install -r requirements.txt`
   - `.env` faylida `OPENAI_API_KEY`ni sozlang
2. PowerShell'da loyiha ildizidan:
   ```powershell
   webui\setup_autostart.ps1
   ```
   Bu skript webui uchun kerakli qo'shimcha paketni (Flask) o'rnatadi va
   kompyuterga har kirganingizda avtomatik, fon jarayoni sifatida ishga
   tushadigan vazifa ro'yxatga oladi (Windows Task Scheduler orqali).
3. Brauzerda oching va xatcho'p qiling:
   ```
   http://127.0.0.1:5057
   ```

Shu bilan tamom — endi bu manzil doim ishlaydi, terminal yoki VS Code kerak
emas.

## Kundalik foydalanish

1. `http://127.0.0.1:5057`ni oching.
2. Chap paneldagi katakka:
   - **Maqola havolasi yoki nomini** joylang — o'sha maqola to'liq yuklab
     olinib tarjima qilinadi, **yoki**
   - **Tayyor wikitext**ni joylang — aynan shu matn tarjima qilinadi (katta
     maqolaning bir qismini yoki qo'lda tayyorlangan matnni tarjima qilish
     uchun qulay).
3. "Tarjima qilish"ni bosing va kutib turing — bosqichlar (Tayyorlash,
   Tarjima, Finalizatsiya, Lokalizatsiya, Tahrir, Saqlash) ko'rsatiladi.
4. Natija o'ng panelda chiqadi. "Nusxalash" bilan clipboard'ga olishingiz
   yoki "Yuklab olish" bilan `.txt` fayl sifatida saqlashingiz mumkin.
5. Maqola nomi orqali tarjima qilingan bo'lsa, natija avtomatik ravishda
   `temp_wiki/<maqola nomi>.txt`'ga ham saqlanadi — xuddi CLI'dan
   ishlatgandagidek.

### Phase 5 (tahrir)ni yoqish/o'chirish

Sahifa yuqorisidagi katakcha orqali `translation_rules.md` qoidalariga
asoslangan avtomatik tahrir bosqichini (Phase 5) yoqib/o'chirib qo'yishingiz
mumkin. Bu sozlama faqat sizning kompyuteringizda saqlanadi.

### Lokalizatsiya lug'atini tahrirlash

"Lokalizatsiya lug'ati" havolasi `localization_map.json`dagi barcha
inglizcha→o'zbekcha almashtirish qoidalarini ko'rsatadi. Qatorlarni
tahrirlashingiz, o'chirishingiz yoki yangisini qo'shishingiz va
"Saqlash"ni bosishingiz mumkin — o'zgarish darhol faylga yoziladi va
keyingi tarjimalarda qo'llaniladi.

> **Diqqat:** ba'zi qatorlarda boshida/oxirida bo'sh joy ataylab qoldirilgan
> (masalan, `" buyidlar"`), va ba'zilarida o'ng ustun ataylab bo'sh (matnni
> shunchaki o'chirib tashlash qoidasi). Tahrirlashda bularni o'zgartirmaslikka
> harakat qiling — interfeys hech narsani avtomatik kesib tashlamaydi, aynan
> nima yozsangiz shu saqlanadi.

## Sozlash

Portni o'zgartirish uchun `webui/.env` fayl yarating (repo ildizidagi
`.env`dan alohida):
```
WEBUI_PORT=5057
```

Log fayli: `webui/logs/webui.log` — muammo yuz bersa shu yerga qarang.

## O'chirish

```powershell
webui\uninstall_autostart.ps1
```

Bu avtostart vazifasini olib tashlaydi. Agar server hozir ishlab turgan
bo'lsa (shutdown endpoint yo'q, atayin — soddalik uchun), uni Task
Manager'dan `pythonw.exe` jarayonini tugatib yoki kompyuterdan chiqib-kirib
to'xtatishingiz mumkin.
