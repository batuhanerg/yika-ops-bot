# YIKA Ops Bot ("Mustafa") — Project Specification

## Overview

A Slack bot named **Mustafa** for ERG Controls that allows team members to manage customer support operations through natural conversation. The bot parses conversational input (Turkish or English), extracts structured data, and writes to a centralized Google Sheet that serves as the operational database.

ERG Controls provides IoT-based hand hygiene monitoring systems (branded "YIKA") to enterprise customers in food service and healthcare. The system consists of physical devices (tags/badges, anchors, gateways, charging docks) installed at customer sites, connected to a cloud dashboard. The team is small (4 people) and manages deployments across Turkey, Egypt, UAE, and Saudi Arabia.

**Slack workspace:** ergcontrols.slack.com  
**Channel:** #technical-operations  
**Bot display name:** Mustafa  
**Bot mention:** @mustafa

---

## Architecture

```
Team member sends message in #technical-operations (@mustafa mention)
    or sends DM to Mustafa
        ↓
Google Cloud Run receives Slack event webhook
        ↓
Loads thread context if this is a continuation
        ↓
Builds prompt: system prompt + sheet context + thread history + user message
        ↓
Claude Haiku 4.5 parses intent, extracts structured data, identifies gaps
        ↓
If missing fields or low confidence:
    → Bot asks clarifying questions in the thread (multi-turn)
    → Waits for user reply, loops back to Claude with accumulated context
If all fields present and confident:
    → Bot replies in thread with formatted confirmation + ✅/❌ buttons
        ↓
User clicks ✅ Confirm → Google Sheets API writes to the live sheet
        ↓
Read-back confirmation posted to thread
Write operation logged to Audit Log tab
```

### Tech Stack

- **Runtime:** Python 3.12, Google Cloud Run
- **Slack:** Slack Bolt for Python (`slack-bolt`)
- **LLM:** Claude Haiku 4.5 via Anthropic API (model: `claude-haiku-4-5-20251001`)
- **Data store:** Google Sheets API v4 via `gspread`
- **Auth:** GCP service account (Sheets), Slack Bot Token + Signing Secret, Anthropic API key
- **Secrets:** Environment variables on Cloud Run
- **Thread state:** In-memory dict keyed by Slack `thread_ts`

---

## Google Sheet Structure

**The sheet is read-only for all human users.** Only the bot's GCP service account has Editor access. Team members have Viewer access.

### Tab 1: Sites

| Col | Field | Type | Required | Validation |
|-----|-------|------|----------|------------|
| A | Site ID | String | Yes | Format: `XXX-CC-NN` (e.g., `ASM-TR-01`) |
| B | Customer | String | Yes | |
| C | City | String | Yes | |
| D | Country | String | Yes | |
| E | Address | String | No | |
| F | Facility Type | Enum | Yes | `Food`, `Healthcare` |
| G | Dashboard Link | URL | No | |
| H | Supervisor 1 | String | No | |
| I | Phone 1 | String | No | |
| J | Email 1 | String | No | |
| K | Supervisor 2 | String | No | |
| L | Phone 2 | String | No | |
| M | Email 2 | String | No | |
| N | Go-live Date | Date | Yes | YYYY-MM-DD |
| O | Contract Status | Enum | Yes | `Active`, `Pending`, `Expired`, `Pilot` |
| P | Notes | String | No | |

### Tab 2: Hardware Inventory

| Col | Field | Type | Required | Validation |
|-----|-------|------|----------|------------|
| A | Site ID | String | Yes | Must exist in Sites |
| B | Device Type | Enum | Yes | `Tag`, `Anchor`, `Gateway`, `Charging Dock`, `Power Bank`, `Power Adapter`, `USB Cable`, `Other` |
| C | HW Version | String | No | |
| D | FW Version | String | No | |
| E | Qty | Integer | Yes | Positive |
| F | Last Verified | Date | No | YYYY-MM-DD |
| G | Notes | String | No | Sub-type details (e.g., "Hasta yatağı anchor") |

### Tab 3: Implementation Details

One row per site. Columns grouped by category with colored headers.

| Col | Field | Category |
|-----|-------|----------|
| A | Site ID | — |
| B | Internet connection | General (green) |
| C | Gateway placement | General (green) |
| D | Charging dock placement | General (green) |
| E | Dispenser anchor placement | General (green) |
| F | Handwash time | General (green) |
| G | Tag buzzer/vibration | General (green) |
| H | Entry time | General (green) |
| I | Clean hygiene time | Food (orange) |
| J | HP alert time | Food (orange) |
| K | Hand hygiene time | Food (orange) |
| L | Hand hygiene interval (dashboard) | Food (orange) |
| M | Hand hygiene type | Food (orange) — `Two Step`, `Soap Only`, `Disp Only` |
| N | Tag clean-to-red timeout | Healthcare (blue) |
| O | Dispenser anchor power type | Healthcare (blue) |
| P | Other details | Other (gray) |
| Q | Last Verified | Other (gray) — YYYY-MM-DD |

### Tab 4: Support Log

| Col | Field | Type | Required | Validation |
|-----|-------|------|----------|------------|
| A | Site ID | String | Yes | Must exist in Sites |
| B | Received Date | Date | Yes | Not future. Warn if >90 days ago. |
| C | Resolved Date | Date | Conditional | Required if Resolved. Must be ≥ Received. |
| D | Type | Enum | Yes | `Visit`, `Remote`, `Call` |
| E | Status | Enum | Yes | `Open`, `Resolved`, `Follow-up (ERG)`, `Follow-up (Customer)`, `Scheduled` |
| F | Root Cause | Enum | Yes | `HW Fault (Production)`, `HW Fault (Customer)`, `FW Bug`, `Dashboard Bug`, `Feature Request`, `Configuration`, `User Error`, `Other` |
| G | Reported By | String | No | |
| H | Issue Summary | String | Yes | |
| I | Resolution | String | Conditional | Required if Resolved. |
| J | Devices Affected | String | No | |
| K | Technician | String | Yes | Must be known team member |
| L | Notes | String | No | |

### Tab 5: Site Viewer
Read-only. Formula-driven. Bot never writes here.

### Tab 6: Stock

| Col | Field | Type | Required | Validation |
|-----|-------|------|----------|------------|
| A | Location | Enum | Yes | `Istanbul Office`, `Adana Storage`, `Other` |
| B | Device Type | Enum | Yes | Same as Hardware Inventory |
| C | HW Version | String | No | |
| D | FW Version | String | No | |
| E | Qty | Integer | Yes | Positive |
| F | Condition | Enum | Yes | `New`, `Refurbished`, `Faulty`, `Reserved` |
| G | Reserved For | String | No | |
| H | Notes | String | No | |

### Tab 7: Dashboard
Read-only. Formula-driven. Bot never writes here.

### Tab 8: Audit Log

| Col | Field |
|-----|-------|
| A | Timestamp (ISO 8601 UTC) |
| B | Slack User (display name) |
| C | Operation (CREATE / UPDATE / DELETE) |
| D | Target Tab |
| E | Site ID |
| F | Summary of changes |
| G | Raw message text |

---

## Operations

| # | Operation | Tabs Affected | Frequency |
|---|-----------|---------------|-----------|
| 1 | Log New Installation | Sites + Hardware + Implementation | Rare |
| 2 | Log Support Request | Support Log (+ maybe Stock) | Most common |
| 3 | Update Support Request | Support Log (+ maybe Stock) | Common |
| 4 | Update Site Info | Sites | Occasional |
| 5 | Update Hardware Inventory | Hardware Inventory | Occasional |
| 6 | Update Implementation Details | Implementation Details | Occasional |
| 7 | Update Stock | Stock | Occasional |
| 8 | Query Data | Read-only | Common |
| 9 | Help | None | On demand |

### 1. LOG NEW INSTALLATION (multi-step wizard)

Creates records across 3 tabs for a brand new customer site.

**Trigger phrases:** "yeni müşteri ekle", "yeni site oluştur", "kurulum yaptık şurada", "yeni kurulum logla", "new installation", "new site"

**Flow:**
1. User provides initial info (can be partial)
2. Bot extracts what it can, asks for missing required fields
3. Bot suggests a Site ID based on customer name + country
4. **Step 1 — Sites:** Show proposed entry → ✅ confirm → write
5. **Step 2 — Hardware:** Ask about devices → user provides → ✅ confirm → write
6. **Step 3 — Implementation:** Ask about relevant parameters based on Facility Type → user provides (can say "skip" / "leave blank") → ✅ confirm → write
7. Each step gets individual confirmation

User can dump everything in one message — bot parses it all.

**Required (Sites):** Customer, City, Country, Facility Type, Go-live Date, Contract Status  
**Required (Hardware):** At least device types + quantities  
**Implementation Details:** All optional

### 2. LOG SUPPORT REQUEST

Adds a new row to Support Log.

**Trigger phrases:** "bugün ASM'ye gittim", "Arzu hanım aradı", "destek kaydı oluştur", "support log", "ziyaret yaptık", "uzaktan destek verdik"

**Required:** Site ID, Received Date, Type, Status, Root Cause, Issue Summary, Technician  
**Conditional:** Resolution required if Status = Resolved

**Extraction rules:**
- "bugün" → today, "dün" → yesterday, "geçen [day]" → last [day]
- Physical visit → Visit, phone/remote → Remote or Call
- Resolved in message → Status = Resolved, Resolved Date = Received Date
- "ben" / first person → map to Slack user's technician name
- Classify root cause from context (see vocabulary)

**Stock cross-reference:** If message mentions device replacement ("değiştirdim", "yenisiyle değiştik"), bot asks AFTER logging:
> "Bu değişim stok ile ilgili mi? Stok güncellemesi yapmamı ister misin?"
> ✅ Evet | ❌ Hayır

### 3. UPDATE SUPPORT REQUEST

Modifies an existing Support Log entry (e.g., closing a ticket, adding resolution).

**Trigger phrases:** "ticket'ı kapat", "destek kaydını güncelle", "dünkü ziyaretle ilgili güncelleme"

**Behavior:** Bot identifies which entry (if ambiguous, shows recent open entries for the site). Shows current vs. proposed values. Same stock inquiry if devices mentioned.

### 4. UPDATE SITE INFO

Updates any Sites tab field except Site ID (immutable).

**Trigger phrases:** "kontakt bilgisini güncelle", "sözleşme durumunu değiştir", "dashboard linki şu"

### 5. UPDATE HARDWARE INVENTORY

Adds, updates, or removes hardware rows.

**Trigger phrases:** "5 tag daha ekledik", "donanım güncelle", "hardware update"

**Behavior:** If Site ID + Device Type + sub-type exists → ask update or new row. Show before/after. Stock inquiry if relevant.

### 6. UPDATE IMPLEMENTATION DETAILS

Updates parameter cells for a site.

**Trigger phrases:** "yıkama süresi 30 saniye", "konfigürasyon değişikliği", "ayarları güncelle"

**Behavior:** Multiple parameters in one message OK. Creates row if none exists.

### 7. UPDATE STOCK

Adds/updates/removes stock entries.

**Trigger phrases:** "stoka ekle", "stoktan çıkar", "envanter güncelle"

**Behavior:** Additions → add or update qty. Removals → decrement, ask to delete if qty reaches 0. Show before/after.

### 8. QUERY DATA (read-only)

No writes, no confirmation needed.

**Trigger phrases:** "durumu ne?", "kaç tane?", "son ziyaret?", "açık ticket?", "stokta ne var?", "özet"

**Query types:** Site summary, open issues (per-site or all), stock availability, support history, hardware inventory, implementation details, aggregates.

### 9. HELP

**Trigger:** `/mustafa yardım` slash command or `@mustafa yardım` mention.

**Response:** Turkish user guide (see Help Guide section below).

---

## Conversation Design

### Multi-Turn

Conversations happen in Slack threads:
1. **Missing fields:** Bot asks for all missing fields at once. User replies. Bot accumulates.
2. **Clarification:** Bot asks when ambiguous.
3. **Correction:** User can fix values before confirmation ("hayır, tarih 3 Şubat'tı").
4. **Post-confirm follow-up:** Stock inquiry after device changes.

**Thread state:** In-memory dict keyed by `thread_ts`. Contains: accumulated data, missing fields, operation type, user ID. Cleared on ✅/❌.

### Activation

- **Channel (#technical-operations):** Only when `@mustafa` mentioned
- **DMs:** All messages

### Language

- Responds in the language the user writes in (Turkish or English)
- Dropdown/enum values always stored in English
- Free-text fields stored in user's language

---

## Guardrails

### Confirmation Before Every Write
Parse → show formatted summary → ✅ Onayla / ❌ İptal buttons → only initiating user can click → write on confirm

### Required Field Validation
Check all required fields before showing confirmation. Ask for ALL missing fields at once.

### Value Validation
- **Site ID:** Must exist. Resolve names via site_resolver.
- **Dates:** No future dates. Warn if >90 days ago. Resolved ≥ Received.
- **Dropdowns:** Must match valid option.
- **Quantities:** Positive integers.
- **Technician:** Must be known team member.

### Duplicate Prevention
Before new Support Log entry, check same Site ID + same date + similar summary. Warn if found.

### Read-Back After Write
Confirm with contextual summary (total entries, open issues, last visit).

### Audit Trail
Every write → Audit Log tab with timestamp, user, operation, target, summary, raw message.

### Stock Cross-Reference
Device replacement mentions → ask about stock after logging.

---

## Help Guide (Turkish)

This is displayed when user types `@mustafa yardım` or `/mustafa yardım`. Formatted as a Slack message using Block Kit.

```
🤖 *Mustafa — Kullanım Kılavuzu*

Merhaba! Ben Mustafa, ERG Controls operasyon asistanınızım. Benimle Türkçe veya İngilizce konuşabilirsiniz.

*🔹 Nasıl Kullanılır?*
• Kanalda: `@mustafa` yazıp mesajınızı gönderin
• DM'den: Direkt mesaj atabilirsiniz

*🔹 Neler Yapabilirim?*

📋 *Yeni Kurulum Kaydet*
`@mustafa yeni müşteri: [isim], [şehir], [tesis türü], [tarih]`

📞 *Destek Kaydı Oluştur*
`@mustafa bugün ASM'ye gittim, 2 tag değiştirdim T12 T18, üretim hatası`

🔄 *Destek Kaydı Güncelle*
`@mustafa ASM'deki açık ticket'ı kapat, sorun çözüldü`

🔧 *Donanım Güncelle*
`@mustafa ASM'ye 5 tag daha ekledik`

⚙️ *Ayar Güncelle*
`@mustafa ASM yıkama süresi 30 saniye olarak güncellendi`

📦 *Stok Güncelle*
`@mustafa stoka 10 yeni tag ekle, İstanbul ofis`

🔍 *Bilgi Sorgula*
`@mustafa ASM'nin durumu ne?`
`@mustafa tüm sitelerde açık ticket var mı?`
`@mustafa stokta kaç tag var?`

📊 *Dashboard & Veri Görüntüleme*
Google Sheet'e buradan ulaşabilirsiniz: [link]
Sheet'teki sekmeler:
• *Dashboard* — Tüm sitelerin özet görünümü
• *Site Viewer* — Açılır menüden site seçerek detay görüntüleme
• *Support Log* — Tüm destek kayıtları
• *Hardware Inventory* — Sitelerdeki donanım envanteri
• *Stock* — Dağıtılmamış cihaz stoku

⚠️ *Önemli Notlar*
• Her yazma işlemi onay gerektirir — yanlışlıkla veri değişmez
• Sheet salt okunurdur, değişiklikler sadece benim üzerimden yapılır
• Eksik bilgi varsa size sorarım, tek mesajda her şeyi yazmanız gerekmez
• Gelecek tarihli destek kaydı oluşturulamaz
```

---

## Testing Scenarios

### 1. Support — resolved visit (Turkish)
```
Input: "bugün ASM'ye gittim, 2 tag değiştirdim T12 ve T18. Üretim hatası, kartlar değiştirildi. Gökhan gitti."
Expected: log_support, ASM-TR-01, today, Visit, Resolved, HW Fault (Production), Gökhan
Post-confirm: stock inquiry for -2 Tags
```

### 2. Support — missing fields
```
Input: "Arzu hanım aradı, bazı kartların verisi az gözüküyormuş"
Expected: missing date, status, technician, root cause → bot asks all at once
```

### 3. Support — false alarm
```
Input: "dün Migros'tan Ahmet bey aradı gateway offline gözüküyor dedi, kontrol ettim sorun yoktu, veri gecikmesiymiş"
Expected: MIG-TR-01, yesterday, Remote/Call, Resolved, User Error, Batu (if Batu sent it)
```

### 4. Support — English
```
Input: "Visited McDonald's Cairo today, replaced 3 anchors. Production defect. Gokhan handled it."
Expected: MCD-EG-01, today, Visit, Resolved, HW Fault (Production), Gökhan
```

### 5. Support — first person
```
Input: "Ben bugün ASM'ye gittim, firmware güncelledim"
Expected: technician = Slack sender's name
```

### 6. Create site
```
Input: "Yeni müşteri: Anadolu Sağlık Merkezi, Gebze Kocaeli, sağlık tesisi, 1 Mart'ta kurulum yaptık, aktif"
Expected: suggest ASM-TR-01, then guide hardware + implementation
```

### 7. Query — site summary
```
Input: "ASM'nin durumu ne?"
Expected: formatted summary from all tabs
```

### 8. Query — aggregate
```
Input: "Tüm sitelerde kaç açık ticket var?"
Expected: count by site
```

### 9. Update support — close ticket
```
Input: "ASM'deki pil optimizasyonu ticket'ını kapat"
Expected: find open entry, update to Resolved, ask for resolution notes
```

### 10. Future date rejection
```
Input: "Yarın ASM'ye gideceğim, bunu logla"
Expected: reject — "Gelecek tarihli destek kaydı oluşturulamaz."
```

### 11. Stock inquiry after replacement
```
Input: "Migros'ta 3 anchor değiştirdik"
Expected: after log → "Bu anchor'lar stoktan mı geldi?"
```

### 12. Update site info
```
Input: "ASM'nin dashboard linki: yika-anadolusaglik.ergcontrols.net"
Expected: update Sites col G for ASM-TR-01
```

### 13. Bulk hardware with sub-types
```
Input: "ASM'de 32 tag, 13 yatak anchoru, 20 dezenfektan anchoru, 4 sabun anchoru, 1 gateway, 4 şarj istasyonu var"
Expected: 6 hardware rows with appropriate notes
```

### 14. Help command
```
Input: "@mustafa yardım"
Expected: Turkish help guide displayed
```

---

## Setup Checklist

### 1. Google Sheet
- Upload `erg_customer_support_v4.xlsx` to Google Drive → Open as Google Sheets
- Note Sheet ID from URL
- Add "Audit Log" tab with columns: Timestamp, Slack User, Operation, Target Tab, Site ID, Summary, Raw Message

### 2. GCP Service Account
- Create service account in GCP Console
- Download JSON key
- Enable Google Sheets API
- Share sheet with service account as Editor
- Share sheet with team as Viewer only

### 3. Slack App
- Create at api.slack.com → "From scratch" in `ergcontrols` workspace
- Display name: Mustafa
- OAuth scopes: `app_mentions:read`, `chat:write`, `im:history`, `im:write`, `users:read`
- Event subscriptions: `app_mention`, `message.im`
- Interactivity: enable, same URL
- Install to workspace → copy Bot Token + Signing Secret
- Invite Mustafa to #technical-operations

### 4. Anthropic API Key
- Create at console.anthropic.com

### 5. Environment Variables
```
SLACK_BOT_TOKEN=xoxb-...
SLACK_SIGNING_SECRET=...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_SHEET_ID=...
GOOGLE_SERVICE_ACCOUNT_JSON={"type": "service_account", ...}
```

### 6. Local Development
- Run app locally
- Use ngrok to tunnel: `ngrok http 3000`
- Set Slack Event Subscription URL to ngrok URL + `/slack/events`

### 7. Deploy to Cloud Run
```bash
gcloud run deploy yika-ops-bot \
  --source . \
  --region europe-west1 \
  --allow-unauthenticated \
  --memory 512Mi \
  --timeout 60
```
Update Slack Event Subscription URL to Cloud Run URL.

---

## Error Handling

| Error | Response |
|-------|----------|
| Sheets API failure | Retry once → "Sheets'e yazamadım, lütfen tekrar deneyin." |
| Claude API failure | Retry once → "Mesajınızı işleyemiyorum, lütfen tekrar deneyin." |
| Unknown site | "Bu isimde bir site bulamadım. Mevcut siteler: [list]." |
| Unknown technician | "Teknisyen '[name]' tanımlı değil. Ekip: Batu, Gökhan, Mehmet, Koray." |
| Ambiguous input | Ask for clarification. Never guess. |
| Future date | "Gelecek tarihli kayıt oluşturulamaz." |
| Old date (>90 days) | "Bu kayıt 90 günden eski. Emin misin?" (allow if confirmed) |

---

## Future Enhancements (v2+)

- Rate limiting (per-user/channel daily limits)
- Token budget tracking and monthly spend alerts
- Message length limits
- Thread timeout with auto-cancel after inactivity
- Weekly summary messages posted to channel
- Slash commands beyond yardım
- Photo attachments from site visits (Google Drive)
- YIKA SaaS dashboard API integration
- Data migration from Sheets to dashboard DB
- Auto-deploy via Cloud Build
- Scheduled reminders for follow-up items
