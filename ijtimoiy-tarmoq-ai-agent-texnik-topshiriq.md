# Texnik Topshiriq: Ijtimoiy Tarmoqlar uchun Ochiq Kodli AI Agent Platformasi

**Loyiha kodi:** `social-ai-agents`
**Versiya:** 1.0
**Sana:** 2026-07-20
**Asos:** Mavjud Django loyihasi (`django-dars`) ustiga qurilgan yangi modul

---

## 1. Loyihaning maqsadi

Foydalanuvchi o'ziga tegishli ijtimoiy tarmoq akkauntlarini (Telegram, Instagram, Facebook, YouTube, TikTok) platformaga ulaydi, o'zining AI provayder kalitini (OpenAI, Claude, Gemini, DeepSeek, mahalliy/tekin modellar va h.k.) qo'shadi, so'ng har bir akkaunt uchun alohida — qaysi AI javob berishi, qanday ohangda (tone) javob berishi, qaysi manbalardan (bilim bazasi, sayt, hujjat, FAQ) foydalanishi kerakligini sozlaydi. Shundan so'ng tizim kiruvchi xabarlarni/kommentlarni avtomatik aniqlaydi va sozlangan AI orqali javob yozadi.

Loyiha **to'liq ochiq kodli** bo'ladi — har kim o'z serverida deploy qilib, o'z AI kalitlarini ulab foydalana oladi (self-hosted, BYOK — Bring Your Own Key).

### 1.1. Asosiy printsiplar
- **Provider-agnostic**: har qanday AI provayder (pullik yoki tekin) plagin sifatida qo'shilishi mumkin.
- **Account-level sozlash**: bitta foydalanuvchida 5 ta Telegram kanali bo'lsa, har biri boshqa AI, boshqa promptga ega bo'lishi mumkin.
- **Xavfsizlik**: barcha API kalitlar shifrlangan holda saqlanadi, hech qachon log yoki frontendga to'liq chiqarilmaydi.
- **Kengaytiriluvchanlik**: yangi ijtimoiy tarmoq yoki AI provayder qo'shish uchun mavjud kodni buzmasdan yangi modul qo'shish yetarli bo'lishi kerak (plugin arxitektura).

---

## 2. Asosiy tushunchalar (Domain Model)

| Tushuncha | Tavsif |
|---|---|
| **AIProvider** | Tizimga tanish AI xizmat turi (OpenAI, Anthropic, Gemini, DeepSeek, Ollama/local, va h.k.) — kod darajasida "adapter" sifatida mavjud. |
| **AIProviderCredential** | Foydalanuvchining o'z API kaliti — bitta AIProvider'ga bog'langan, foydalanuvchiga tegishli, shifrlangan. |
| **SocialPlatform** | Tizim qo'llab-quvvatlaydigan ijtimoiy tarmoq turi (Telegram, Instagram, Facebook, YouTube, TikTok). |
| **SocialAccount** | Foydalanuvchi ulagan aniq bitta akkaunt/kanal/bot (masalan: "@mening_botim" yoki "instagram.com/mystore"). |
| **AgentConfig** | Bitta SocialAccount uchun AI sozlamalari to'plami: qaysi AIProviderCredential ishlatiladi, tizim prompti (system prompt), ohang, tilni aniqlash, javob uzunligi va h.k. |
| **KnowledgeSource** | AgentConfig'ga bog'langan manba — matn, fayl (PDF/DOCX), URL, FAQ ro'yxati. RAG uchun ishlatiladi. |
| **RoutingRule** | Qaysi turdagi xabar/komment/DM qaysi AgentConfig orqali javob olishini belgilaydi (masalan: faqat DM'larga javob, kommentlarga yo'q). |
| **ConversationLog** | Har bir kiruvchi xabar va AI javobi tarixi — audit va sifat nazorati uchun. |
| **UsageStats** | Har bir akkaunt/provider bo'yicha token sarfi, javoblar soni statistikasi. |

---

## 3. Mavjud loyiha tuzilishiga moslashtirish

Hozirgi struktura (`apps/api`, `apps/base`, `apps/telegram/bot`, `apps/telegram/telegram`) saqlanadi, ustiga quyidagi yangi app'lar qo'shiladi:

```
apps/
├── api/                     # mavjud — umumiy API (kengaytiriladi)
├── base/                    # mavjud — asosiy sahifalar
├── accounts/                # YANGI — foydalanuvchi autentifikatsiyasi, profil
├── ai_providers/            # YANGI — AI provayder adapterlari va credential'lar
├── agents/                  # YANGI — AgentConfig, RoutingRule, markaziy "miya"
├── knowledge/               # YANGI — KnowledgeSource, RAG, embedding'lar
├── social/
│   ├── telegram/            # mavjud kodni shu yerga ko'chirish/moslashtirish
│   ├── instagram/           # YANGI
│   ├── facebook/            # YANGI
│   ├── youtube/             # YANGI
│   └── tiktok/              # YANGI
└── dashboard/                # YANGI — foydalanuvchi boshqaruv paneli (frontend uchun API/view)
```

> **Muhim:** `apps/telegram/telegram` va `apps/telegram/bot` ikkalasi ham bitta ijtimoiy tarmoqqa tegishli bo'lgani uchun, ularni birlashtirib `apps/social/telegram` ga ko'chirish tavsiya etiladi (Bosqich 1da bajariladi). Bu boshqa tarmoqlar bilan bir xil naqshni (pattern) ta'minlaydi.

---

## 4. Ma'lumotlar bazasi modeli (asosiy jadvallar)

### 4.1. `ai_providers` app

```python
# AIProvider — tizim darajasida oldindan ro'yxatga olingan provayderlar (fixture orqali to'ldiriladi)
class AIProvider(models.Model):
    slug = models.SlugField(unique=True)          # "openai", "anthropic", "gemini", "deepseek", "ollama"
    name = models.CharField(max_length=100)
    adapter_class_path = models.CharField(max_length=255)  # "apps.ai_providers.adapters.openai.OpenAIAdapter"
    is_free_tier_available = models.BooleanField(default=False)
    default_base_url = models.URLField(blank=True)
    logo = models.ImageField(upload_to="providers/", blank=True)
    is_active = models.BooleanField(default=True)

# Foydalanuvchining shaxsiy kaliti
class AIProviderCredential(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ai_credentials")
    provider = models.ForeignKey(AIProvider, on_delete=models.CASCADE)
    label = models.CharField(max_length=100)        # "Mening OpenAI kalitim"
    encrypted_api_key = models.BinaryField()         # Fernet bilan shifrlanadi
    base_url_override = models.URLField(blank=True)
    model_name = models.CharField(max_length=100)    # "gpt-4o-mini", "claude-sonnet-4-6" va h.k.
    extra_config = models.JSONField(default=dict, blank=True)  # temperature, max_tokens...
    is_valid = models.BooleanField(default=True)     # oxirgi tekshiruvda kalit ishladimi
    last_checked_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

### 4.2. `social` app'lari (har biri uchun umumiy shablon)

```python
class SocialPlatform(models.Model):
    slug = models.SlugField(unique=True)   # telegram, instagram, facebook, youtube, tiktok

class SocialAccount(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="social_accounts")
    platform = models.ForeignKey(SocialPlatform, on_delete=models.CASCADE)
    display_name = models.CharField(max_length=150)
    external_id = models.CharField(max_length=255)      # bot_id, page_id, channel_id va h.k.
    encrypted_access_token = models.BinaryField()
    encrypted_refresh_token = models.BinaryField(blank=True, null=True)
    webhook_secret = models.CharField(max_length=100, blank=True)
    status = models.CharField(choices=[("active","Faol"),("paused","Pauza"),("error","Xato")], default="active")
    connected_at = models.DateTimeField(auto_now_add=True)
    meta = models.JSONField(default=dict, blank=True)   # platformaga xos qo'shimcha ma'lumot
```

### 4.3. `agents` app

```python
class AgentConfig(models.Model):
    social_account = models.OneToOneField(SocialAccount, on_delete=models.CASCADE, related_name="agent_config")
    ai_credential = models.ForeignKey(AIProviderCredential, on_delete=models.SET_NULL, null=True)
    system_prompt = models.TextField()
    tone = models.CharField(max_length=50, default="do'stona")  # rasmiy, do'stona, hazilkash...
    language_mode = models.CharField(choices=[("auto","Avtomatik"),("uz","O'zbek"),("ru","Rus"),("en","Ingliz")], default="auto")
    max_response_length = models.PositiveIntegerField(default=500)
    is_enabled = models.BooleanField(default=True)
    fallback_to_human = models.BooleanField(default=True)   # AI ishonchsiz bo'lsa odamga o'tkazish
    working_hours = models.JSONField(default=dict, blank=True)  # ish vaqti sozlamalari
    updated_at = models.DateTimeField(auto_now=True)

class RoutingRule(models.Model):
    agent_config = models.ForeignKey(AgentConfig, on_delete=models.CASCADE, related_name="rules")
    trigger_type = models.CharField(choices=[
        ("dm","Shaxsiy xabar"), ("comment","Komment"), ("mention","Mention"), ("story_reply","Storiga javob")
    ])
    keyword_filter = models.CharField(max_length=255, blank=True)  # bo'sh bo'lsa — hammasiga
    is_active = models.BooleanField(default=True)
    priority = models.PositiveIntegerField(default=0)
```

### 4.4. `knowledge` app

```python
class KnowledgeSource(models.Model):
    agent_config = models.ForeignKey(AgentConfig, on_delete=models.CASCADE, related_name="knowledge_sources")
    source_type = models.CharField(choices=[("text","Matn"),("file","Fayl"),("url","URL"),("faq","FAQ")])
    title = models.CharField(max_length=200)
    raw_content = models.TextField(blank=True)
    file = models.FileField(upload_to="knowledge/", blank=True, null=True)
    url = models.URLField(blank=True)
    is_indexed = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

class KnowledgeChunk(models.Model):
    source = models.ForeignKey(KnowledgeSource, on_delete=models.CASCADE, related_name="chunks")
    content = models.TextField()
    embedding = models.JSONField()   # yoki pgvector ustuni (tavsiya etiladi)
```

### 4.5. `agents` app — muloqot tarixi va statistika

```python
class ConversationLog(models.Model):
    social_account = models.ForeignKey(SocialAccount, on_delete=models.CASCADE, related_name="logs")
    external_user_id = models.CharField(max_length=255)   # xabar yuborgan tashqi foydalanuvchi
    incoming_message = models.TextField()
    ai_response = models.TextField(blank=True)
    used_knowledge_chunks = models.ManyToManyField(KnowledgeChunk, blank=True)
    tokens_used = models.PositiveIntegerField(default=0)
    response_time_ms = models.PositiveIntegerField(default=0)
    status = models.CharField(choices=[("sent","Yuborildi"),("failed","Xato"),("escalated","Odamga o'tkazildi")])
    created_at = models.DateTimeField(auto_now_add=True)

class UsageStats(models.Model):
    social_account = models.ForeignKey(SocialAccount, on_delete=models.CASCADE)
    date = models.DateField()
    messages_count = models.PositiveIntegerField(default=0)
    tokens_used = models.PositiveIntegerField(default=0)
```

---

## 5. Arxitektura oqimi (yuqori darajadagi)

```
[Ijtimoiy tarmoq] --webhook/polling--> [social/<platform>/views.py]
        |
        v
[agents/dispatcher.py]  --- RoutingRule bo'yicha AgentConfig topadi
        |
        v
[knowledge/retriever.py] --- kerakli manbalardan tegishli parchalarni oladi (RAG)
        |
        v
[ai_providers/router.py] --- AgentConfig.ai_credential asosida to'g'ri adapterni chaqiradi
        |
        v
[ai_providers/adapters/<provider>.py] --- haqiqiy AI API'ga so'rov yuboradi
        |
        v
[social/<platform>/sender.py] --- javobni ijtimoiy tarmoqqa qaytarib yuboradi
        |
        v
[agents/models.ConversationLog] --- hammasi log qilinadi
```

Har bir qavat mustaqil, bir-biridan interfeys (abstract base class) orqali ajratilgan — bu yangi tarmoq yoki provayder qo'shishni osonlashtiradi.

---

## 6. Bosqichma-bosqich implementatsiya rejasi

### **Bosqich 0 — Tayyorgarlik va refaktoring** (1-2 kun)
1. `apps/telegram/telegram` va `apps/telegram/bot` kodini tahlil qilib, umumiy naqshni (webhook qabul qilish, xabar yuborish) alohida hujjatga yozib chiqish.
2. `apps/social/telegram/` papkasini yaratish, mavjud Telegram kodini shu yerga ko'chirish, testdan o'tkazish (eski funksionallik buzilmasligi kerak).
3. `SocialPlatform`, `AIProvider` uchun boshlang'ich fixture (JSON) tayyorlash.
4. `.env` fayliga `FERNET_SECRET_KEY` qo'shish — barcha kalitlarni shifrlash uchun (`cryptography` kutubxonasi).

**Natija:** eski Telegram funksionalligi yangi struktura ichida ishlayapti, hech narsa buzilmagan.

---

### **Bosqich 1 — `ai_providers` moduli** (3-4 kun)
1. `AIProvider`, `AIProviderCredential` modellarini yaratish, migratsiya.
2. `apps/ai_providers/adapters/base.py` — abstract `BaseAIAdapter` klassi:
   ```python
   class BaseAIAdapter(ABC):
       @abstractmethod
       def generate_reply(self, system_prompt: str, context: list[dict], user_message: str) -> AIResponse: ...
       @abstractmethod
       def validate_credential(self) -> bool: ...
   ```
3. Kamida 3 ta adapter yozish: `OpenAIAdapter`, `AnthropicAdapter`, `OllamaAdapter` (tekin/local variant sifatida).
4. `AIProviderCredential.encrypted_api_key` ni saqlash/o'qish uchun `EncryptedField` yordamchi funksiyalarini yozish (Fernet).
5. Foydalanuvchi panelida: "AI qo'shish" formasi — provider tanlash, API kalit kiritish, "Tekshirish" tugmasi (`validate_credential()` chaqiriladi, natija ko'rsatiladi).
6. Admin panelda `AIProvider` ro'yxatini boshqarish (yangi provider qo'shish faqat kod orqali, lekin admin ularni yoqib/o'chira oladi).

**Natija:** foydalanuvchi kabinetida o'z AI kalitini qo'shib, "tekshirish" orqali ishlashini tasdiqlashi mumkin.

---

### **Bosqich 2 — `agents` moduli (markaziy miya)** (3-4 kun)
1. `AgentConfig`, `RoutingRule` modellari va migratsiya.
2. Har bir `SocialAccount` yaratilganda avtomatik bo'sh `AgentConfig` yaratiladigan signal (`post_save`).
3. `apps/agents/dispatcher.py` — kiruvchi xabarni qabul qilib:
   - tegishli `SocialAccount` va `AgentConfig` ni topadi,
   - `RoutingRule` lar bo'yicha bu xabar javob olishi kerakmi tekshiradi,
   - agar kerak bo'lsa, `knowledge` va `ai_providers` modullarini chaqiradi.
4. Foydalanuvchi panelida "Agent sozlamalari" sahifasi: system prompt, ohang, til, javob uzunligi, ish vaqti sozlamalari.
5. `RoutingRule` uchun UI — masalan checkbox: "DM'larga javob ber", "Kommentlarga javob ber" va kalit so'z filtri.

**Natija:** har bir akkaunt uchun mustaqil AI sozlamasi mavjud, lekin hali haqiqiy xabar almashinuvi ulanmagan.

---

### **Bosqich 3 — `knowledge` moduli (RAG)** (4-5 kun)
1. `KnowledgeSource`, `KnowledgeChunk` modellari.
2. Fayl yuklash (PDF/DOCX/TXT) → matnga ajratish → chunklash (masalan 500 so'zdan) → embedding olish (tanlangan AI provider yoki alohida embedding modeli orqali) → `pgvector` yoki oddiy JSON+cosine similarity bilan saqlash.
   - **Tavsiya:** PostgreSQL + `pgvector` kengaytmasi ishlatilsin (tezlik va kengaytiriluvchanlik uchun).
3. URL manba uchun: sahifani yuklab olish, HTML'dan matn ajratish (`readability`/`trafilatura` kutubxonasi), keyin xuddi shu chunklash jarayoni.
4. `retriever.py` — foydalanuvchi savoliga eng mos N ta chunkni qaytaradi (cosine similarity yoki `pgvector` ANN qidiruvi).
5. Dashboard'da "Bilim bazasi" bo'limi: manba qo'shish, ro'yxatni ko'rish, indekslash holatini kuzatish, o'chirish.

**Natija:** agent endi faqat umumiy bilimga emas, balki foydalanuvchi bergan maxsus manbalarga tayanib javob bera oladi.

---

### **Bosqich 4 — Telegram integratsiyasi (to'liq)** (2-3 kun)
1. Mavjud `apps/social/telegram` kodini `dispatcher.py` bilan bog'lash — webhook kelganda endi qat'iy javob emas, balki `agents.dispatcher.handle_incoming()` chaqiriladi.
2. Har bir `SocialAccount` (bot) uchun webhook URL avtomatik ro'yxatdan o'tkaziladi (`setWebhook` API chaqiruvi).
3. Xatoликlarni qayta ishlash: agar AI javob bera olmasa (`fallback_to_human=True`), foydalanuvchiga "Operatorga ulanmoqdamiz" xabari va admin panelga bildirishnoma.
4. `ConversationLog` ga har bir muloqotni yozish.

**Natija:** Telegram bo'yicha to'liq ishlaydigan AI agent — bu MVP ning yadrosi.

---

### **Bosqich 5 — Instagram va Facebook integratsiyasi** (5-7 kun)
1. Meta Developer App yaratish bo'yicha hujjat yozish (foydalanuvchi o'zi App yaratib, Page Access Token olishi kerak bo'ladi — bu ochiq kodli, self-hosted loyihada muqarrar).
2. `apps/social/facebook` — Messenger webhook (`/webhook/facebook/`), komment va DM eventlarini qabul qilish.
3. `apps/social/instagram` — Instagram Graph API orqali DM va komment webhooklari (Instagram Business akkaunt talab qilinadi).
4. Ikkala platforma uchun umumiy `MetaAdapter` bazaviy klass yozish (chunki ikkalasi ham Meta Graph API ishlatadi) — kod takrorlanishini kamaytirish uchun.
5. Rate limit va Meta API cheklovlarini hisobga olgan holda navbat (queue) tizimi — **Celery + Redis** orqali asinxron ishlash tavsiya etiladi.

**Natija:** Instagram va Facebook akkauntlari ham xuddi Telegram kabi AgentConfig orqali boshqariladi.

---

### **Bosqich 6 — YouTube va TikTok integratsiyasi** (5-7 kun)
1. `apps/social/youtube` — YouTube Data API orqali video kommentlarini polling qilish (YouTube'da real-time webhook yo'q, shuning uchun **Celery Beat** bilan davriy so'rov, masalan har 2-5 daqiqada).
2. `apps/social/tiktok` — TikTok API (Business/Content Posting API) orqali komment va DM'lar; TikTok API cheklovlari sababli boshlang'ich versiyada faqat kommentlarga javob bilan cheklanishi mumkin.
3. Har ikkalasi uchun ham `RoutingRule` va `AgentConfig` bir xil interfeys orqali ishlaydi — foydalanuvchi tomonidan farq sezilmaydi.

**Natija:** barcha 5 ta platforma bir xil markaziy tizim orqali boshqariladi.

---

### **Bosqich 7 — Dashboard (boshqaruv paneli)** (5-6 kun)
1. `apps/dashboard` — foydalanuvchi login qilgandan so'ng ko'radigan asosiy panel:
   - "Ijtimoiy akkauntlarim" — ulash/uzish, holatni ko'rish.
   - "AI kalitlarim" — qo'shish, tekshirish, o'chirish.
   - "Har bir akkaunt sozlamasi" — AgentConfig + RoutingRule + KnowledgeSource formalar birlashtirilgan sahifa.
   - "Muloqotlar tarixi" — `ConversationLog` filtri (sana, akkaunt, status bo'yicha).
   - "Statistika" — `UsageStats` grafik ko'rinishida (token sarfi, javoblar soni).
2. Frontend uchun mavjud `theme/` papkasi (Tailwind, judging by loyihaning umumiy dizayni) asosida qurish, yangi framework kiritmaslik.
3. Real vaqt yangilanishlar uchun (ixtiyoriy, keyingi bosqich) Django Channels/WebSocket qo'shish mumkin.

**Natija:** texnik bilimi kam foydalanuvchi ham interfeys orqali hamma narsani sozlay oladi.

---

### **Bosqich 8 — Xavfsizlik, test va relizga tayyorlash** (4-5 kun)
1. Barcha kalitlar (AI va ijtimoiy tarmoq tokenlari) faqat shifrlangan holda saqlanishini tekshirish (unit test bilan).
2. Webhook endpointlar uchun imzo tekshiruvi (Telegram secret token, Meta `X-Hub-Signature-256`, va h.k.) majburiy qilish.
3. Rate limiting — bitta foydalanuvchi/akkaunt haddan tashqari ko'p so'rov yubormasligi uchun (`django-ratelimit` yoki Celery navbat cheklovi).
4. `apps/api/tests.py`, har bir yangi app uchun `tests.py` to'ldirish — kamida asosiy oqimlar (happy path + xatolik holatlari) qamrab olinishi kerak.
5. `docker-compose.yml` tayyorlash: Django + PostgreSQL(+pgvector) + Redis + Celery worker + Celery beat.
6. `README.md` — o'rnatish, `.env.example`, har bir platformada App/Bot yaratish bo'yicha qo'llanma (Telegram BotFather, Meta Developer, Google Cloud Console, TikTok Developer).
7. `CONTRIBUTING.md` — yangi AI provider yoki yangi ijtimoiy tarmoq qo'shish bo'yicha yo'riqnoma (chunki loyiha ochiq kodli, hissa qo'shuvchilar uchun aniq qoida kerak).

**Natija:** loyiha GitHub'da ochiq kodli sifatida e'lon qilishga tayyor.

---

## 7. Texnologik stack (tavsiya)

| Qatlam | Texnologiya |
|---|---|
| Backend | Django (mavjud), Django REST Framework (mavjud `apps/api`) |
| Asinxron vazifalar | Celery + Redis (webhooklar, davriy polling, AI so'rovlari) |
| Ma'lumotlar bazasi | PostgreSQL + `pgvector` (embedding qidiruvi uchun) |
| Shifrlash | `cryptography` (Fernet) |
| AI adapterlari | Har bir provayder uchun rasmiy SDK (`openai`, `anthropic`) yoki `httpx` orqali to'g'ridan-to'g'ri REST |
| Frontend | Mavjud `theme/` (Tailwind asosida), kerak bo'lsa HTMX qo'shish (server-rendered, sodda interaktivlik uchun) |
| Deploy | Docker + docker-compose, keyinchalik Kubernetes (ixtiyoriy) |

---

## 8. API endpoint'lar (asosiy, `apps/api` kengaytmasi sifatida)

```
POST   /api/ai-credentials/              — yangi AI kalit qo'shish
POST   /api/ai-credentials/{id}/validate/ — kalitni tekshirish
GET    /api/social-accounts/             — foydalanuvchi akkauntlari ro'yxati
POST   /api/social-accounts/             — yangi akkaunt ulash
GET    /api/social-accounts/{id}/agent-config/  — sozlamalarni olish
PATCH  /api/social-accounts/{id}/agent-config/  — sozlamalarni yangilash
POST   /api/social-accounts/{id}/knowledge-sources/  — manba qo'shish
GET    /api/conversations/?account={id}  — muloqotlar tarixi
POST   /webhook/telegram/{account_uuid}/     — Telegram webhook qabul qiluvchi
POST   /webhook/facebook/{account_uuid}/     — Facebook/Messenger webhook
POST   /webhook/instagram/{account_uuid}/    — Instagram webhook
```

---

## 9. Xavfsizlik talablari (majburiy)

1. Barcha API kalit va tokenlar bazada faqat shifrlangan holda saqlanadi, admin panelda ham to'liq ko'rinmaydi (faqat oxirgi 4 belgi ko'rsatiladi).
2. Webhook endpointlar imzo/token orqali tekshiriladi — begona so'rovlar rad etiladi.
3. Har bir foydalanuvchi faqat o'z akkauntlari va kalitlarini ko'ra oladi (`request.user` bo'yicha qat'iy filtr, Django permission tizimi).
4. AI'ga yuboriladigan promptlarda foydalanuvchi shaxsiy ma'lumotlari (masalan boshqa foydalanuvchi tokenlari) hech qachon aralashtirilmasligi kerak — prompt injection'dan himoya sifatida system prompt va user content aniq ajratilgan bo'lishi shart.
5. `fallback_to_human` yoqilgan bo'lsa, AI ishonch darajasi past javoblarni avtomatik yubormasdan, admin/operatorga bildirishnoma yuborish kerak.

---

## 10. MVP doirasi (birinchi relizga kiritish shart bo'lganlar)

Agar vaqt cheklangan bo'lsa, quyidagi tartibda ustuvorlik berish tavsiya etiladi:

1. ✅ Bosqich 0-1-2 (refaktoring + AI provider + agent config) — bularsiz hech narsa ishlamaydi.
2. ✅ Bosqich 4 (Telegram to'liq) — eng oson va tez natija beradigan platforma, isbotlash uchun ideal.
3. ✅ Bosqich 7 (Dashboard, hech bo'lmasa minimal) — foydalanuvchi buni ko'rmasa, sozlay olmaydi.
4. ⏳ Bosqich 3 (Knowledge/RAG) — MVP'da soddalashtirilgan holda (embeddingsiz, faqat to'liq matnni promptga qo'shish) bo'lishi mumkin, keyin to'liq RAG'ga o'tkaziladi.
5. ⏳ Bosqich 5-6 (Instagram/Facebook/YouTube/TikTok) — keyingi bosqichlarda, chunki har biri o'z API murakkabliklariga ega.
6. ⏳ Bosqich 8 — relizdan oldin albatta bajarilishi shart (xavfsizlik shart, kechiktirib bo'lmaydi).

---

## 11. Claude Code uchun ishlatish bo'yicha eslatma

Ushbu hujjatni Claude Code'ga berganda, har bir bosqichni **alohida sessiyada, alohida promptda** bajarish tavsiya etiladi (masalan avval "Bosqich 0 ni bajar", keyin natijani tekshirib "Bosqich 1 ni bajar"). Bitta so'rovda hamma bosqichni birdan so'rash sifatni pasaytiradi va katta migratsiya xatolariga olib kelishi mumkin.
