# Team & Business Context

This file is loaded at runtime as part of the Claude system prompt. Edit this file to update team info, site aliases, and business vocabulary.

## Team Members

| Slack Display Name | Technician Name | Role |
|---|---|---|
| Batu / Batuhan | Batu | Founder — remote support, business ops |
| Mehmet | Mehmet | Co-founder — day-to-day operations |
| Gökhan | Gökhan | Field technician — travels for site visits |
| Koray | Koray | Angel investor/advisor — customer operations |

"Koray bey" = Koray. "ben gittim" / first person = the Slack sender.

## Site Aliases

| Site ID | Customer | Aliases |
|---|---|---|
| MIG-TR-01 | Migros | Migros, MIG |
| MCD-EG-01 | McDonald's | McDonald's, MCD, McDonalds, Mek |
| ASM-TR-01 | Anadolu Sağlık Merkezi | ASM, Anadolu Sağlık, Anadolu |

Bot also reads Sites tab dynamically for the full mapping.

## Site ID Convention

Format: `XXX-CC-NN`
- XXX: 2-4 letter abbreviation from customer name
- CC: Country code (TR, EG, AE, SA)
- NN: Sequential (01, 02...)

## Device Vocabulary

| Turkish | Device Type | Notes |
|---|---|---|
| yaka kartı, kart, tag, badge, rozet | Tag | |
| anchor, çapa | Anchor | |
| yatak anchoru, hasta yatağı anchoru | Anchor | notes: "Hasta yatağı anchor" |
| dezenfektan anchoru, dispenser anchoru | Anchor | notes: "Dezenfektan dispenser anchor" |
| sabun anchoru | Anchor | notes: "Sabun anchor" |
| gateway, ağ geçidi | Gateway | |
| şarj istasyonu, şarj dock'u, dock | Charging Dock | |
| powerbank, taşınabilir şarj | Power Bank | |
| adaptör, güç adaptörü | Power Adapter | |
| USB kablo | USB Cable | |

## Status Vocabulary

| Turkish | Value |
|---|---|
| ziyaret, sahaya gittim, gidip baktık | Visit |
| uzaktan baktım, remote, uzaktan destek | Remote |
| aradı, telefon etti | Call |
| çözüldü, hallettik, giderdik | Resolved |
| açık, devam ediyor, henüz çözülmedi | Open |
| takip gerekiyor (bizden) | Follow-up (ERG) |
| takip gerekiyor (müşteriden) | Follow-up (Customer) |
| planlandı, randevu alındı | Scheduled |

## Root Cause Vocabulary

| Turkish | Value |
|---|---|
| üretim hatası, fabrika hatası, bozuk gelmiş | HW Fault (Production) |
| müşteri kırmış, düşürmüşler, hasar görmüş | HW Fault (Customer) |
| firmware bug, yazılım hatası | FW Bug |
| dashboard hatası, panel hatası, arayüz sorunu | Dashboard Bug |
| yanlış alarm, veri gecikmesi, false alarm | User Error |
| konfigürasyon, ayar sorunu, yanlış ayarlanmış | Configuration |
| yeni özellik istiyorlar, talep, feature request | Feature Request |

## Other Mappings

| Turkish | Value |
|---|---|
| gıda, restoran, market, fast food | Food |
| hastane, sağlık, klinik, sağlık merkezi | Healthcare |
| yeni, sıfır, kutusunda | New |
| yenilenmiş, refurbished, tamir edilmiş | Refurbished |
| arızalı, bozuk, çalışmıyor | Faulty |
| ayrılmış, rezerve | Reserved |
| İstanbul ofis, ofis, merkez | Istanbul Office |
| Adana depo, Adana | Adana Storage |

## Business Notes

- Migros is the most important logo client (4+ year relationship)
- McDonald's sites go through Diversey (partner)
- Some sites have multiple anchor sub-types (bed, soap, dispenser) as separate Hardware Inventory rows
- Gökhan is seasonal and travels between cities
