# Changelog

## v1.8.9 — Unknown Field Sanitization (2026-02-16)

<!-- RELEASE_NOTES v1.8.9
🔧 Daha önce iletişim bilgisinde parantez içi açıklamalar (örn. "EKK Hemsiresi") kayboluyordu — artık bu bilgileri notlara ekliyorum.
-->

### Fixed
- **Unknown field sanitization** — when Haiku invents non-existent column names (e.g. `supervisor_1_role`, `supervisor_2_title`), the values are now stripped from data and appended to the `notes` field instead of being silently dropped
- **System prompt guard** — added explicit instruction to only use documented fields and put extra info in `notes`

### Tests
- 7 new tests: unknown field stripped → notes, known fields preserved, multiple unknowns, existing notes kept, support log unknowns, private keys ignored, unmapped ops noop
- 641 total tests passing

## v1.8.8 — Update Site Must-Field Fix (2026-02-16)

<!-- RELEASE_NOTES v1.8.8
🔧 Daha önce mevcut sahaya iletişim bilgisi eklerken müşteri adı, şehir, ülke gibi bilgiler istiyordum — artık sadece eklemek istediğiniz bilgileri yazmanız yeterli.
-->

### Fixed
- **update_site must-field enforcement** — `enforce_must_fields` was mapping `update_site` to the Sites tab, requiring all `create_site` must fields (customer, city, country, facility_type, contract_status). Now `update_site` only requires `site_id`; partial updates work correctly.

### Tests
- 3 new tests: update_site doesn't require create_site fields, empty missing list, create_site still enforces
- 640 total tests passing

## v1.8.7 — Dynamic Sites Context + Dedup Fix (2026-02-16)

<!-- RELEASE_NOTES v1.8.7
🔧 Daha önce "yeditepe koşuyolu için iletişim bilgisi ekle" dediğinizde sahayı tanıyamıyordum ve yeni saha oluşturmak istiyordum — artık tüm sahaları biliyorum ve doğru sahayı güncelliyorum.
🔧 Daha önce aynı mesaja 2-3 kez cevap veriyordum — artık tekrar eden mesajları doğru yakalıyorum.
-->

### Fixed
- **Dynamic sites context** — Claude now receives the full sites list before classification, so it correctly identifies existing customers (e.g., "yeditepe koşuyolu") and classifies as `update_site` instead of `create_site`
- **Dedup TTL** — increased from 30s to 300s to cover Slack's full retry window (~10s, ~60s, ~5min), preventing duplicate/triple bot responses during cold starts
- **create_site vs update_site prompt rules** — explicit decision rules added to system prompt for when to use each operation

### Changed
- Hardcoded site aliases removed from `team_context.md` — sites are now loaded dynamically from the sheet
- Site resolution in `process_message` reuses the early-read sites list instead of making duplicate sheet reads
- Duplicate site_id check for `create_site` also reuses the early-read sites list

### Tests
- 5 new tests: `build_sites_context` (4), sites context injection in `process_message` (1)
- 3 new dedup tests: TTL >= 300s, 60s retry caught, 290s retry caught
- 637 total tests passing

## v1.8.6 — Version-Aware Hardware Upsert (2026-02-16)

<!-- RELEASE_NOTES v1.8.6
✨ Artık farklı donanım sürümleri ayrı satırda tutuluyor — "3.6.2 sürüm tag ekledim" dediğinizde 3.6.1 satırını değil, 3.6.2 satırını güncelliyor.
✨ Onay kartında sürüm bilgisi görünüyor: "Tag (3.6.1): 32 → 35 (3 eklendi)".
🔧 Sürüm belirtmeden bir cihaz eklediğinizde ve birden fazla sürüm varsa, hangi sürüm olduğunu soruyorum.
🗑️ Gereksiz debug logları temizlendi.
-->

### Added
- **Version-aware hardware upsert** — `find_hardware_row` now matches on Site ID + Device Type + HW Version. Different versions of the same device type are kept as separate rows.
- **Ambiguous version detection** — when user doesn't specify a version and multiple rows exist for the same device type, enrichment marks the entry as ambiguous and the confirmation card lists available versions.
- **Version in confirmation card** — update labels now include version: "Tag (3.6.1): 32 → 35 (3 eklendi)", new version rows show "Tag (3.6.2) x3 (yeni kayit)"

### Fixed
- Removed verbose diagnostic logging from revision 00041 (dedup, handler, enrichment, upsert)
- Restored clean INFO-level logging for normal operations

### Tests
- 15 new tests: version-aware find_hardware_row (6), version-aware enrichment (4), version in confirmation card (3), version-aware upsert write (2)
- 637 total tests passing

## v1.8.5 — Hardware Upsert + Fuzzy Stock Location Matching (2026-02-15)

<!-- RELEASE_NOTES v1.8.5
✨ Artık "ASM'ye 5 tag ekledim" dediğinizde var olan satırı güncelliyorum — yeni satır açmıyorum (örn: 32 → 37).
✨ Onay kartında "Tag: 32 → 37 (5 eklendi)" şeklinde ne değişeceğini gösteriyorum.
🔧 Daha önce stok depo adını tam yazmak gerekiyordu — artık "Istanbuldan geldi" veya "İstanbul" yazmanız yeterli.
🔧 Stoktan çıkarma ("5 tag çıkardım") ve mutlak set ("32 tag var") de doğru çalışıyor.
-->

### Added
- **Hardware upsert** — `update_hardware` now checks for existing rows by Site ID + Device Type (case-insensitive). If found, updates qty in place instead of appending a duplicate row. Supports three modes: add (ekledim), subtract (çıkardım), and absolute set (X var).
- **Confirmation card shows upsert context** — "Tag: 32 → 37 (5 eklendi)" for updates, "Gateway x3 (yeni kayıt)" for new rows, negative qty warning with ⚠️
- `SheetsService.find_hardware_row(site_id, device_type)` — returns (row_index, row_data) or None
- `SheetsService.update_hardware_row(row_index, updates)` — updates specific cells in place
- `enrich_hardware_entries()` — annotates data with existing row info before confirmation
- **Fuzzy stock location matching** — Turkish suffix stripping (-dan, -den, -tan, -ten, 'dan, 'den, etc.) and İ/ı normalization. "Istanbuldan geldi", "İstanbul", "adanadan" all match correctly.
- Ambiguous location matches now ask for clarification instead of failing silently

### Fixed
- Existing HW/FW Version and Notes are preserved on upsert unless user explicitly provides new values
- Stock prompt location matching now handles Turkish suffixes and İ/I variants

### Tests
- 29 new tests in `tests/test_hardware_upsert.py` (find_hardware_row, update_hardware_row, qty mode detection, enrichment, upsert write, confirmation card)
- 14 new tests in `tests/test_fuzzy_location.py` (suffix stripping, İ normalization, ambiguous matches, integration)
- 622 total tests passing

## v1.8.4 — Stock Prompt After Hardware Writes + Version Normalization (2026-02-15)

<!-- RELEASE_NOTES v1.8.4
✨ Artık donanım envanterine cihaz eklediğinizde stok güncellemesi yapıp yapmayacağınızı soruyorum — hangi depodan geldiğini yazmanız yeterli.
🔧 Daha önce HW/FW Version alanına "v3.6.0" yazılınca "v" ile kaydediliyordu — artık otomatik temizliyorum.
-->

### Added
- **Stock prompt after hardware writes** — after confirming a hardware inventory write that includes device quantities, a follow-up prompt asks if stock should be updated. User replies with warehouse name to update stock, or "hayır" to skip. Handles device removal (reverse direction), negative stock warning, and unknown locations.
- `SheetsService.find_stock_row_index()` — finds stock row by location and device type

### Fixed
- **HW/FW Version normalization** — strips leading `v`/`V` prefix on write (`"v3.6.0"` → `"3.6.0"`)
- One-time cleanup script `scripts/normalize_versions.py` cleaned 18 existing cells in live sheet
- `_should_ask_stock` now only triggers for `log_support` (hardware uses the new dedicated stock prompt)
- Feedback handlers preserve stock prompt state when clearing thread

### Tests
- 18 new tests in `tests/test_stock_prompt.py` (triggering, state, reply handling, edge cases, sheets helper)
- 9 new tests in `tests/test_version_normalize.py` (normalization, append_hardware, append_stock)
- 579 total tests passing

## v1.8.3 — Fix Deploy Message in Docker (2026-02-15)

<!-- RELEASE_NOTES v1.8.3
🔧 Daha önce yeni versiyonda ne değiştiğini anlatırken eski bilgileri gösteriyordum — artık güncel notları okuyorum.
-->

### Fixed
- **CHANGELOG.md missing from Docker image** — `.dockerignore` had `*.md` which excluded `CHANGELOG.md`; added `!CHANGELOG.md` exception and `COPY CHANGELOG.md .` to Dockerfile
- **Stale fallback bullets** — removed hardcoded v1.8.0 release notes from `RELEASE_NOTES` in `version.py`; empty fallback now shows clean version-only message instead of outdated content

### Tests
- 5 new tests in `tests/test_deploy_message.py` (empty fallback, path resolution, Dockerfile/dockerignore checks, live parsing)
- 552 total tests passing

## v1.8.2 — Feedback Button UX Fix (2026-02-15)

<!-- RELEASE_NOTES v1.8.2
🔧 Daha önce 👍/👎 butonuna bastığınızda butonlar hâlâ tıklanabilir görünüyordu — artık seçiminiz sabit metin olarak gösteriliyor.
-->

### Fixed
- **Feedback buttons replaced with static text after click** — after clicking 👍 or 👎 on any feedback prompt, the original message is updated via `client.chat_update()` to replace the interactive buttons with a static context block showing the selection ("👍 Evet olarak değerlendirildi" or "👎 Hayır olarak değerlendirildi")
- **Graceful fallback** — if `chat_update` fails (message too old, permissions), the error is logged but the feedback response is still sent normally

### Tests
- 14 new tests in `tests/test_feedback_button_update.py` (button replacement, content preservation, failure handling, regressions)
- 547 total tests passing

## v1.8.1 — Human-Readable Deployment Messages (2026-02-15)

<!-- RELEASE_NOTES v1.8.1
🔧 Daha önce versiyon mesajları teknik ve robotik görünüyordu — artık takıma anlaşılır şekilde anlatıyorum.
✨ Artık her versiyon için Türkçe özet var — ne değişti, neyi fark edeceksiniz.
-->

### Changed
- **Deployment messages now human-readable** — `_announce_version()` parses `<!-- RELEASE_NOTES vX.Y.Z -->` blocks from `CHANGELOG.md` instead of using hardcoded bullet points from `version.py`
- **Conversational format** — deploy message now reads "Merhaba! Birkaç iyileştirme yaptım (vX.Y.Z):" with release notes, closing with "Bir sorun yaşarsanız bana yazın! 💬"
- **Fallback preserved** — if no RELEASE_NOTES block exists for current version, falls back to old `RELEASE_NOTES` list in `version.py`

### Added
- `parse_release_notes()` — extracts RELEASE_NOTES from CHANGELOG content for a given version (max 5 entries)
- `format_deploy_message()` — formats conversational Slack announcement with release notes
- `get_release_notes_for_current_version()` — loads and parses notes for `__version__` from CHANGELOG.md
- **Retroactive RELEASE_NOTES** for all versions v1.0.0 through v1.8.0 in CHANGELOG.md
- **Writing guidelines** in CLAUDE.md for future RELEASE_NOTES authoring

### Tests
- 9 new tests in `tests/test_deploy_message.py` (parse, missing version, max entries, format with/without notes, fallback)
- 533 total tests passing

## v1.8.0 — Scheduled Messaging: Weekly Report + Daily Aging Alert (2026-02-15)

<!-- RELEASE_NOTES v1.8.0
✨ Artık her pazartesi otomatik haftalık veri kalitesi raporu gönderiyorum — eksik alanlar, yaşlanan ticketlar, eski veriler hep bir arada.
✨ 3 günden fazla açık kalan ticketlar için günlük uyarı atıyorum.
✨ Geçen haftadan bu yana kaç sorunun çözüldüğünü raporda gösteriyorum.
-->

### Added
- **Weekly data quality report** (`generate_weekly_report()`) — automated Slack report with sections:
  - 🔴 Acil (must fields missing), 🟡 Önemli (important fields missing)
  - 🟠 Yaşlanan ticketlar (open >3 days), 🔵 Eski veriler (Last Verified >30 days)
  - ✅ Overall status with completeness percentage
  - 📈 Resolution tracking: compares current vs last week's snapshot
- **Daily aging alert** (`generate_daily_aging_alert()`) — posts when tickets are open >3 days, skips silently otherwise
- **HTTP cron endpoints** — Flask Blueprint at `app/routes/cron.py`:
  - `POST /cron/weekly-report` — triggers weekly report
  - `POST /cron/daily-aging` — triggers daily aging alert
  - Bearer token auth via `CRON_SECRET` env var
- **Flask migration** — `app/main.py` now wraps Bolt with Flask via `SlackRequestHandler`
  - `GET /health` and `GET /` for Cloud Run health checks
  - Slack events routed through `POST /` and `POST /slack/events`
- **Resolution tracking via snapshots** — weekly report stores issue snapshot in Audit Log (`WEEKLY_REPORT_SNAPSHOT`), next week's report reads it for "X/Y çözüldü" tracking
  - Snapshot key includes `tab` to disambiguate same field across tabs (e.g., HW Version in Hardware vs Stock)
  - Awaiting Installation sites excluded from resolution counts (status change ≠ resolution)
  - 0/0 edge case suppressed (only shows severity parts with >0 prev issues)
- **Report thread handling** — replies to report threads processed as normal operations; feedback buttons wired with `operation="report"`
- **Cloud Scheduler setup instructions** in README

### New Files
- `app/services/scheduled_reports.py` — report generation functions
- `app/routes/__init__.py` — routes package
- `app/routes/cron.py` — cron HTTP endpoints
- `tests/test_scheduled_reports.py` — 28 tests (sections, completeness, resolution, edge cases)
- `tests/test_cron.py` — 13 tests (auth, weekly, daily endpoints)
- `tests/test_report_threads.py` — 6 tests (thread replies, feedback wiring)

### Changed
- `app/main.py` — Flask wrapping Bolt instead of `app.start(port=port)`
- `app/utils/formatters.py` — `format_feedback_buttons()` supports `context="report"`
- `app/handlers/actions.py` — feedback_positive recognizes `report_thread` state
- `app/handlers/messages.py` — negative feedback captures `operation="report"` for report threads
- `app/services/sheets.py` — added `read_latest_audit_by_operation()` for snapshot retrieval
- `requirements.txt` — added `flask>=3.0.0`

### Tests
- 47 new tests (28 scheduled reports + 13 cron + 6 report threads)
- 492 total tests passing

## v1.7.5 — Live Testing Bug Fixes Round 3 (2026-02-14)

<!-- RELEASE_NOTES v1.7.5
🔧 Daha önce toplu donanım girdiğinizde satırlar bazen yanlış sütunlara kayıyordu — artık doğru yere yazıyorum.
🔧 Artık dropdown alanlar için geçerli seçenekleri gösteriyorum (örn. "Seçenekler: ERG Controls, Müşteri").
🔧 Implementation alanlarının yanına Türkçe açıklama ekliyorum — "HP alert time" ne demek artık açık.
-->

### Fixed
- **Bug 8: Hardware bulk write column offset** — all `append_row()` calls now pass `table_range` parameter to constrain table detection to actual data columns (A-G for hardware, A-Q for sites, etc.); prevents Google Sheets API from detecting helper columns (H+) as part of the table and misplacing bulk entry rows
- **Bug 9: Implementation dropdown fields** — new `IMPLEMENTATION_DROPDOWNS` config with valid options for Internet Provider, Hand hygiene type, and Tag buzzer/vibration; `format_missing_fields_message()` and `format_chain_input_prompt()` now show "Seçenekler: ..." for dropdown fields; `validate_impl_dropdown()` supports exact, case-insensitive, and fuzzy matching
- **Bug 10: English Thingsboard attribute names** — friendly field prompts now use English attribute names (e.g., "Clean hygiene time değeri kaç saniye?" instead of "Clean hygiene süresi kaç saniye?") since technicians need to recognize these from the Thingsboard dashboard
- **Bug 11: Field descriptions for technicians** — new `FIELD_DESCRIPTIONS` config with Turkish explanations for all implementation fields; descriptions are shown alongside English attribute names in missing field prompts and chain input prompts (e.g., "HP alert time değeri kaç saniye? — HP bölgesi içindeyken badge'in yeşilden kırmızıya dönme süresi")

### Added
- `app/field_config/field_options.py` — dropdown options config + fuzzy validation
- `app/field_config/field_descriptions.py` — Turkish field descriptions for technicians

### Tests
- 27 new tests (5 bulk write + table_range, 9 dropdown validation, 7 English attribute names, 6 field descriptions)
- 445 total tests passing

## v1.7.4 — Live Testing Bug Fixes Round 2 (2026-02-14)

<!-- RELEASE_NOTES v1.7.4
🔧 Daha önce sorgu yaparken müşteri adını doğru sahaya çeviremiyordum — artık "Este Nove durumu ne?" diye sorduğunuzda doğru sahayı buluyorum.
🔧 Gıda sahası eklerken clean hygiene time gibi zorunlu alanları sormayı atlıyordum — artık hepsini soruyorum.
🔧 Onay kartında "Ssid" yazıyordu — artık düzgün "SSID" görünüyor.
-->

### Fixed
- **Bug 5: Query site_id resolution** — query operations (missing_data, stale_data, etc.) now resolve customer names to Site IDs via `SiteResolver` before querying sheets; previously queries bypassed resolution and passed raw names like "este nove" directly to sheet lookups
- **Bug 6: Food must fields missing in chain** — `facility_type` now propagates through chain state via `chain_ctx`; implementation step for Food sites correctly shows 5 food-specific must fields (clean_hygiene_time, hp_alert_time, etc.); `enforce_must_fields` also reads `facility_type` from existing thread state
- **Bug 7: "Ssid" capitalization** — added column header key entries to `FIELD_LABELS` so Claude's implementation keys (e.g., `"SSID"`, `"Internet Provider"`) display correctly instead of being `.title()`-cased; also fixed `format_query_response()` to use `FIELD_LABELS`

### Tests
- 10 new tests (3 query resolution, 3 food/healthcare chain facility_type, 4 SSID/field label capitalization)
- 418 total tests passing

## v1.7.2 — Live Testing Bug Fixes (2026-02-13)

<!-- RELEASE_NOTES v1.7.2
🔧 Daha önce yeni saha eklerken sonraki adımlarda saha bilgisi kayboluyordu — artık her adımda hatırlıyorum.
🔧 Daha önce müşteri adı yazıp sorgu yaptığınızda bazen yanlış sahayı buluyordum — artık doğru eşleştiriyorum.
🔧 Artık Türkçe mesajlarda "site" yerine "saha" diyorum.
🔧 Olumsuz geri bildirimde artık daha doğal bir soru soruyorum: "Nasıl daha iyi yapabilirdim?"
-->

### Fixed
- **Bug 1: Chain step loses site_id context** — `enforce_must_fields()` now removes fields from Claude's missing list when they're already present in data; `format_chain_input_prompt()` no longer lists site_id as required (it's always known in chain context); chain input now injects `[Site: XXX] [Operation: ...]` prefix so Claude sees the site context; bulk hardware `entries` list satisfies `device_type`/`qty` must fields; implementation fields recognized by both snake_case and sheet column header keys (e.g. `"Internet Provider"` ↔ `internet_provider`)
- **Bug 2: Este Nove resolving to wrong site** — site resolver's `by_customer` and `by_alias` indexes now store lists instead of overwriting on collision; alias fuzzy matching uses `fuzz.ratio` instead of `fuzz.partial_ratio` to prevent short aliases (e.g., "est") from outscoring full customer names
- **Bug 3: "site" instead of "saha" in chain response** — added Turkish terminology rule to system prompt instructing Claude to use "saha" in Turkish text; verified zero Turkish-inflected "site" strings in Python code
- **Bug 4: Negative feedback wording** — unified 👎 response from write-specific "Ne olmalıydı? Lütfen doğru bilgiyi yazın." to "Nasıl daha iyi yapabilirdim?" which works for all interaction types

### Tests
- 23 new tests in `tests/test_bug_fixes_s6.py` (10 chain site_id + context injection + entries + impl keys, 4 site resolver collision, 2 saha terminology, 2 feedback wording, 5 impl key mapping)
- 408 total tests passing

## v1.7.1 — Live Sheet Alignment (2026-02-13)

<!-- RELEASE_NOTES v1.7.1
🔧 Google Sheets'teki renk kuralları gerçek tablo yapısıyla uyumlu hale geldi — eksik alanlar artık doğru renkte görünüyor.
🔧 Stok tablosunda "Last Verified" sütunu artık doğru yere yazılıyor.
-->

### Fixed (Priority 1 — Code Fixes)
- **Stock tab `Last Verified` column** — added to `STOCK_COLUMNS` constant so appended rows land in the correct column
- **Conditional formatting script** — 7 fixes to match live sheet:
  - Stale verified (blue) now covers Hardware Inventory, Implementation Details, and Stock (was HW only)
  - Stale ticket threshold corrected to 3 days (was 7), highlights full row A:M (was single column)
  - Device type version rules now include Gateway (was Tag/Anchor only) with yellow severity (was red)
  - Facility type conditional rules use red severity (was yellow)
  - Support Log conditional rules added: root_cause (when status ≠ Open), resolution + resolved_date (when Resolved)
  - `devices_affected` flagged as important (yellow)
  - Stale verified rules include "Awaiting Installation" guard via `_ContractStatus` helper column
- **`_SiteLabel` helper column blacklist** — `read_sites()` now strips helper columns (like `_SiteLabel`) via `_strip_helper_columns()`, matching behavior of `read_hardware()` and `read_support_log()`

### Changed (Priority 2 — Manual Sheet Fixes)
- Column order aligned across all tabs to match live Google Sheet
- Missing helper columns (`_ContractStatus`, `_FacilityType`) added to relevant tabs
- `Last Verified` column added to Stock tab in live sheet

### Tests
- 15 new conditional formatting tests (stale verified 3 tabs, stale ticket threshold, SL conditionals, devices_affected, Site Viewer data rules)
- 1 new `test_sites_excludes_helper_columns` test for `_SiteLabel` filtering

## v1.7.0 — Validation, Feedback, and Sheet Migrations (2026-02-12)

<!-- RELEASE_NOTES v1.7.0
✨ Artık her işlemden sonra (sorgu dahil) 👍/👎 ile geri bildirim verebilirsiniz.
✨ Yeni saha eklerken her adımda zorunlu alanları Türkçe sorularla gösteriyorum.
🔧 Daha önce Claude'un kaçırdığı zorunlu alanlar fark edilmiyordu — artık ekstra doğrulama yapıyorum.
-->

### Added
- **Must-field validation independent of Claude** — `enforce_must_fields()` validates required fields using `FIELD_REQUIREMENTS` before showing confirmation, catching fields Claude may have missed
- **Chain step must-field prompts** — each chain step shows required fields as friendly Turkish questions (e.g., "Hangi cihaz türü?") with `format_chain_input_prompt()`; facility-type-aware for implementation steps
- **Feedback on every interaction** — 👍/👎 buttons now appear after queries, data quality reports, cancel confirmations, and chain completions (previously only after writes)
  - Context-aware question: "Doğru kaydedildi mi?" for writes, "Faydalı oldu mu?" for queries
- **Help command field requirements section** — `/mustafa yardım` now shows required fields per operation with friendly Turkish names, dynamically generated from `FIELD_REQUIREMENTS` and `FRIENDLY_FIELD_MAP`
- **Dashboard migration script** (`scripts/migrate_dashboard.py`) — replaces "Total Devices" column with 5 device-type breakdown columns (Tags, Anchors, Gateways, Charging Docks, Other) using SUMIFS formulas
- **Site Viewer migration script** (`scripts/migrate_site_viewer.py`) — customer name selector ("Migros (MIG-TR-01)"), support log sorted by Received Date descending, widened key columns
- **Conditional formatting migration script** (`scripts/migrate_conditional_formatting.py`) — color-coded rules across all tabs: 🔴 red for empty must fields, 🟡 yellow for empty important fields, 🔵 blue for stale Last Verified (>30 days), 🟠 orange for aging open tickets (>7 days); supports `--dry-run` flag

### New Files
- `scripts/migrate_dashboard.py` — Dashboard device breakdown migration
- `scripts/migrate_site_viewer.py` — Site Viewer UX migration
- `scripts/migrate_conditional_formatting.py` — Conditional formatting migration
- `tests/test_chain_step_prompts.py` — 10 tests for chain step field prompts
- `tests/test_migrate_dashboard.py` — 11 tests for dashboard migration
- `tests/test_migrate_site_viewer.py` — 6 tests for site viewer migration
- `tests/test_migrate_conditional_formatting.py` — 22 tests for conditional formatting

### Changed
- `format_feedback_buttons()` now accepts `context` parameter ("write" or "query")
- `format_help_text()` dynamically generates field requirements from config
- Cancel handler sends feedback buttons after ending interaction
- Query handler stores `feedback_pending: True` in thread state

## v1.6.1 — Schema Patch: Column Alignment and Facility-Type Conditionals (2026-02-12)

<!-- RELEASE_NOTES v1.6.1
🔧 Gıda sahalarına özel zorunlu alanlar (clean hygiene time vb.) artık doğru tespit ediliyor.
🔧 Implementation Details sütun sırası düzeltildi — veriler artık doğru hücrelere yazılıyor.
-->

### Fixed
- **Implementation Details column order** — mock and system prompt now match actual Google Sheet column order (Dispenser anchor power type at position 11, after Entry time)
- **"saha" terminology** — fixed remaining "site" → "saha" in Turkish ambiguous-match message

### Added
- **6 new Implementation Details columns** in field labels, system prompt, and friendly field map: Dispenser anchor placement, Clean hygiene time, HP alert time, Hand hygiene time, Hand hygiene interval, Hand hygiene type
- **`must_when_facility_type` classification** — Food sites require clean_hygiene_time, hp_alert_time, hand_hygiene_time, hand_hygiene_interval, hand_hygiene_type; Healthcare sites require tag_clean_to_red_timeout
- **Facility-type-aware data quality** — `find_missing_data()` evaluates implementation must fields based on site's Facility Type
- **Facility-type-aware missing fields** — `format_missing_fields_message()` accepts `facility_type` param for correct must/important classification
- 6 new facility-type data quality tests, 4 new facility-type classification tests, 2 new friendly field coverage tests

## v1.6.0 — Schema Changes, Field Classification, and Data Quality Overhaul (2026-02-12)

<!-- RELEASE_NOTES v1.6.0
✨ Artık eksik alanları Türkçe sorularla soruyorum — alan adı yerine "Bu konuyla kim ilgileniyor?" gibi.
✨ Veri kalitesi raporunda önem seviyesi eklendi: 🔴 zorunlu alanlar, 🟡 önemli alanlar.
🔧 "Awaiting Installation" durumundaki sahalar artık gereksiz veri kalitesi uyarısı almıyor.
-->

### Added
- **Field classification config** (`app/field_config/field_requirements.py`) — structured `must` / `important` / `important_conditional` / `optional` classification per tab, driving validation and data quality checks
- **Friendly missing fields messages** — missing fields shown as natural Turkish questions (e.g., "Bu konuyla kim ilgileniyor?") instead of raw field names; must fields block, important fields suggest
- **WhatsApp Group column** on Sites tab
- **Internet Provider / SSID / Password columns** replace "Internet Connection" on Implementation Details tab
- **Context-aware data quality** — "Awaiting Installation" sites skip hardware, implementation, and support log checks
- **Conditional field importance** — FW/HW Version only flagged for electronic devices (not Charging Dock, Power Bank, etc.); root_cause only flagged when status ≠ Open
- **Severity levels in data quality reports** — 🔴 for must fields, 🟡 for important fields
- `CONTEXT_RULES` config for status-based tab skipping
- `FRIENDLY_FIELD_MAP` with Turkish questions for all field names
- `format_missing_fields_message()` utility that classifies and formats missing fields

### Changed
- **Contract Status enum**: "Pending" renamed to "Awaiting Installation" across code, prompts, and vocabulary
- **Turkish terminology**: all user-facing Turkish text uses "saha" instead of "site" (e.g., "müşteri sahası", "Mevcut sahalar")
- **Data quality engine** (`data_quality.py`) fully rewritten to use `FIELD_REQUIREMENTS` instead of hardcoded field lists
- **Missing fields handling** in `common.py`: only must fields block the flow; important-only fields proceed to confirmation with a suggestion note
- `INTERNET_PROVIDERS` enum added: "ERG Controls", "Müşteri"
- `internet_provider` added to `DROPDOWN_FIELDS` for validation

### New Files
- `app/field_config/__init__.py` — field config package
- `app/field_config/field_requirements.py` — `FIELD_REQUIREMENTS` + `CONTEXT_RULES`
- `app/field_config/friendly_fields.py` — `FRIENDLY_FIELD_MAP`
- `app/utils/missing_fields.py` — `format_missing_fields_message()`
- `tests/test_field_requirements.py` — 16 tests for field config
- `tests/test_friendly_fields.py` — 15 tests for friendly field messages

## v1.5.0 — Create-Site Wizard, Data Quality, and UX Polish (2026-02-11)

<!-- RELEASE_NOTES v1.5.0
✨ Artık yeni saha eklerken donanım ve ayar bilgilerini otomatik soruyorum — atlama seçeneğiyle.
🔧 Daha önce telefon numarası (+90...) yazınca Google Sheets hata veriyordu — artık düzgün kaydediliyor.
🔧 Daha önce geri bildirim verdikten sonra thread'de yazamazdınız — artık devam edebilirsiniz.
-->

### Added
- **Proactive chain wizard after create_site** — every new site now prompts for hardware and implementation details (with skip option), even if not mentioned in the original message
- **Empty chain step prompt** — when a chain step has no pre-filled data, shows "write your data or skip" with ⏭️ Atla button instead of an empty confirmation card
- **Explicit feedback via text** — users can type `feedback: ...` or `geri bildirim: ...` to log feedback directly to the Feedback sheet
- **Visible feedback confirmation** — clicking 👍 now shows "Teşekkürler, geri bildiriminiz kaydedildi!" with a closing message
- **Data quality: missing hardware/implementation** — `missing_data` query now flags sites with zero hardware or implementation records
- **Address in data quality checks** — missing Address is now flagged in the missing data report

### Fixed
- **Phone number formula parse error** — phone numbers starting with `+` (e.g., `+90...`) no longer cause `#ERROR!` in Google Sheets; all cell values are sanitized against formula injection (`+`, `=`, `@` prefixed with `'`)
- **Thread dies after feedback** — after 👍/👎 + closing message, thread is properly cleared with guidance to start a new thread
- **Chain context lost in follow-ups** — chain state (pending operations, step numbers, completed/skipped tracking) now survives through missing_fields prompts and multi-turn follow-ups in `process_message`
- **Chain step input misclassified** — when user provides data for a chain step (e.g., hardware details at step 2), Claude could misclassify it as a different operation (e.g., `update_stock`); now forces the operation to match the chain's expected step when `awaiting_chain_input` is set

### Changed
- `_normalize_create_site_data` always injects `update_hardware` and `update_implementation` as pending chain steps
- `_show_confirmation` accepts optional `chain_state` parameter for continuing existing chains
- `process_message` preserves chain context from existing thread state and passes it through to confirmation
- `_sanitize_cell()` applied to all `append_row` calls in sheets.py
- Post-feedback messages now include thread closure guidance

## v1.4.0 — Hotfix: Multi-turn Flow, Feedback, and Cancel (2026-02-11)

<!-- RELEASE_NOTES v1.4.0
🔧 Daha önce eksik bilgi sorduğumda bazen önceki verileri kaybediyordum — artık bağlam korunuyor.
🔧 Daha önce iptal ettikten sonra thread'de yazamazdınız — artık devam edebilirsiniz.
✨ Artık her yeni versiyonda ne değiştiğini kanala yazıyorum.
-->

### Fixed
- **Missing fields reply lost create_site context** — when Claude re-classified a short reply (e.g., "İstanbul") as `update_site`, the bot cleared all `create_site` data; now keeps original operation when state has `missing_fields`
- **Feedback buttons not rendering** — `say(blocks=...)` without `text` fallback caused some Slack clients to not display the 👍/👎 buttons
- **Post-cancel replies ignored** — `thread_store.clear()` on cancel removed all state, so "tekrar yazabilirsiniz" was a lie; now keeps minimal thread state alive after cancel

### Added
- **Version announcement on deploy** — Mustafa posts a changelog message to the channel on first startup of each version (deduplicated via Audit Log)
- `app/version.py` with `__version__` and `RELEASE_NOTES`
- `SLACK_ANNOUNCE_CHANNEL` env var for deploy announcements

## v1.3.0 — Polish, Feedback Loop, and Data Quality (2026-02-11)

<!-- RELEASE_NOTES v1.3.0
✨ Artık sorgudan sonra aynı thread'de devam edebilirsiniz — her seferinde @mustafa yazmanıza gerek yok.
✨ Artık "eksik veriler var mı?" diye sorabilirsiniz — veri kalitesi raporu çıkarıyorum.
✨ Her yazma işleminden sonra 👍/👎 ile geri bildirim verebilirsiniz.
🔧 Daha önce sorgu yaptıktan sonra aynı thread'de yazamazdınız — artık sorunsuz geçiş yapabilirsiniz.
-->

### Added
- **Follow-up queries in threads** — queries now store thread state, enabling natural multi-query conversations without repeating `@mustafa`
- **New query types**: `implementation`, `hardware`, `support_history`, `ticket_detail`
  - Implementation: shows all site configuration parameters
  - Hardware: lists device inventory with totals
  - Support history: last 10 entries with status icons
  - Ticket detail: all fields for a specific ticket (e.g., SUP-004)
- **Context inheritance across operation transitions** — `site_id` and `ticket_id` carry forward from query → write and clarify → write transitions, so users don't need to re-specify identifiers
- **Feedback loop** — 👍/👎 buttons after every write operation; negative feedback captures "what should have happened" and writes to Feedback tab
- **Renamed Technician → Responsible** globally (code fields, prompts, sheet column header)
- **Google Sheet link** in help text and post-action readback messages via `get_google_sheet_url()`
- **Data quality queries** — two new query types:
  - `missing_data`: scans Sites, Hardware, Support Log for empty/incomplete fields
  - `stale_data`: reports records where Last Verified > 30 days old (configurable threshold)
- `format_data_quality_response()` formatter — groups issues by site with counts
- `read_all_implementation()` on SheetsService for cross-site stale data scans
- **Stock readback** after stock update confirmations (e.g., "📦 `İstanbul`: stokta toplam 45 birim")
- **Audit log guardrails** — failed writes logged with `FAILED` operation type (includes error snippet); cancellations logged with `CANCELLED` operation type
- `_build_audit_summary()` and `_operation_to_tab()` helpers in actions.py

### Fixed
- **Follow-up queries silently ignored** — queries didn't store thread state, so thread replies after a query were dropped by the message handler
- **Clarify → write lost context** — clarify handler stored empty `data: {}`, losing `site_id`/`ticket_id` from previous state; multi-turn merge then cleared thread context on operation change
- **Query → write lost identifiers** — transitioning from a query to a write operation (e.g., "add a note to this ticket") cleared state and required re-specifying site_id
- **Stock readback always empty** — `_build_readback()` returned "" early when no `site_id`, but stock uses `location` not `site_id`; moved stock handler before the early return
- **Flaky `test_missing_fields_detected`** — Claude Haiku sometimes returned `clarify` instead of `log_support` for messages with many missing fields; sharpened prompt boundary between `clarify` (ambiguous intent) and `missing_fields` (known operation, incomplete data)

### Changed
- `_handle_query` now accepts `user_id`, `messages`, `language` params and stores thread state after every query response
- Clarify handler carries forward `site_id`/`ticket_id` from existing state into clarify state data
- Multi-turn merge treats `query` and `clarify` as transparent — inherits identifiers instead of clearing state
- System prompt: added `missing_data`/`stale_data` query types, sharpened `clarify` vs `missing_fields` boundary, strengthened `log_support` instruction
- Help text: added "Veri Kalitesi" section with data quality query examples
- `confirm_action` handler: wraps write in try/except with FAILED audit logging
- `cancel_action` handler: logs CANCELLED to audit before proceeding with chain

## v1.2.0 — Cloud Run Deploy + End-to-End Testing (2026-02-10/11)

<!-- RELEASE_NOTES v1.2.0
✨ Artık yeni saha eklerken donanım → ayarlar → destek kaydı adımlarını zincirleme soruyorum.
✨ Tek bir mesajda hem saha hem donanım hem ayar bilgisi yazabilirsiniz — hepsini ayrı ayrı çıkarıyorum.
🔧 Daha önce aynı mesajı bazen iki kez işliyordum — artık Slack tekrarlarını engelliyorum.
-->

### Added
- **Dockerfile** and `.dockerignore` for Cloud Run deployment
- **Create-site wizard** with chained operations: create_site → update_hardware → update_implementation → log_support
  - Roadmap message posted before first confirmation card
  - Step indicator on each card header ("Adım 1/4 — Yeni Site")
  - Final summary showing written vs skipped steps (`site ✅, donanım ✅, ayarlar ⏭️, destek kaydı ✅`)
  - Each step can be confirmed or skipped independently
- **Multi-tab extraction** in Claude prompt: single message can contain site + hardware + implementation + support data, returned as `extra_operations`
- **Last Verified date** injected automatically (defaults to today) for hardware and implementation writes; user can override via natural language
- **Duplicate site_id check** before create_site — warns if site already exists
- **Event deduplication** to prevent double-processing from Slack retries (thread-safe TTL cache on `event_ts`)
- **`extra_operations`** field on `ParseResult` model for chained operation support
- `build_chain_roadmap()` and `build_chain_final_summary()` formatters
- `CHAIN_LABELS` dict for short Turkish operation labels
- `step_info` parameter on `format_confirmation_message` for step indicators

### Fixed
- **Support log write error** (`gspread APIError: Invalid values — list_value`): `devices_affected` was passed as a Python list; now serialized to comma-separated string
- **Duplicate message processing**: roadmap and first card appeared twice due to Slack `app_mention` event retries when handler takes >3s (Claude API call)

### Changed
- `app/handlers/actions.py`: overhauled confirm/cancel handlers for chain tracking (pending_operations, completed_operations, skipped_operations, chain_steps)
- `app/handlers/common.py`: added `_normalize_create_site_data()` for contacts flattening, country code expansion, and extra_operations extraction
- `app/services/claude.py`: parses `extra_operations` from Claude JSON response
- `app/services/sheets.py`: list serialization in `append_support_log`, new methods for stock/hardware reads
- `app/prompts/system_prompt.md`: added multi-tab extraction rules and last_verified extraction instruction

## v1.1.0 — Sheets + Slack Integration (2026-02-10/11)

<!-- RELEASE_NOTES v1.1.0
✨ Artık Slack'ten mesaj yazarak Google Sheets'e veri girebilirsiniz — @mustafa ile veya DM ile.
✨ Her yazma işleminden önce onay kartı gösteriyorum — ✅ ile onaylayın, ❌ ile iptal edin.
✨ Aynı thread'de eksik bilgileri tamamlayabilirsiniz — her seferinde baştan yazmanıza gerek yok.
-->

### Added
- Google Sheets service: read/write all tabs (Sites, Hardware, Implementation Details, Support Log, Stock, Audit Log)
- Slack Bolt app with @mustafa mention handler, DM handler, and channel thread reply handler
- Thread state management (in-memory, keyed by thread_ts) with merge, expire, and clear
- Shared message processing pipeline: parse → validate → resolve site → confirm/ask
- Multi-turn conversation support: operation lock + data merge for thread follow-ups
- Code-level validation of missing fields (filters Claude's over-reporting)
- update_support row lookup: finds most recent non-resolved entry for the site
- Confirm/cancel button handlers with initiating-user enforcement
- Post-write readback summaries (total entries, open tickets)
- Stock cross-reference inquiry after device replacement mentions
- `/mustafa yardım` slash command
- Audit Log tab created in Google Sheet with proper headers
- Query handlers for site summary, open issues, and stock
- "Pending" root cause enum; root_cause optional when status is Open

### Fixed (live testing)
- Confirm button thread_ts lookup (was using bot message ts instead of thread root)
- Stale date in system prompt (now refreshed per parse_message call)
- Thread replies in private channels (requires message.groups event subscription)
- Multi-turn context not carried through confirmation state
- Claude switching operation type in follow-ups (code-level enforcement)

### Changed
- Simplified system prompt: removed verbose Turkish→English tables, condensed date/field rules
- Trimmed vocabulary.md to enum values + ERG-specific jargon only
- Trimmed team_context.md: removed duplicate vocabulary sections

## v1.0.0 — Core Engine (2026-02-10)

<!-- RELEASE_NOTES v1.0.0
✨ Merhaba, ben Mustafa! Türkçe ve İngilizce mesajlarınızı anlayıp yapılandırılmış veriye dönüştürüyorum.
✨ Destek kaydı, saha oluşturma, donanım güncellemesi, sorgu — hepsini yapabiliyorum.
-->

### Added
- Pydantic models for all 9 operation types with enum definitions and required field mappings
- Claude Haiku 4.5 integration for parsing Turkish/English messages into structured JSON
- System prompt with vocabulary mappings and team context for accurate extraction
- Field validators: Site ID format, future date rejection, old date warnings, resolved-after-received, required fields, dropdown values, positive integers
- Site resolver with exact match, abbreviation, alias, and fuzzy matching (thefuzz)
- Slack Block Kit formatters: confirmation messages with buttons, query responses, error messages
- Turkish help guide text (Kullanim Kilavuzu)
