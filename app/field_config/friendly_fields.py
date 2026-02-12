"""Friendly Turkish field name map for missing-field prompts.

Maps snake_case field names to natural Turkish questions.
Used when the bot asks users for missing information.
"""

from __future__ import annotations

# Field name → friendly Turkish question
FRIENDLY_FIELD_MAP: dict[str, str] = {
    # Support Log fields
    "responsible": "Bu konuyla kim ilgileniyor?",
    "root_cause": "Sorunun kök sebebi ne?",
    "site_id": "Hangi müşteri/saha için?",
    "received_date": "Bu ne zaman oldu?",
    "status": "Konu çözüldü mü, hâlâ açık mı?",
    "issue_summary": "Ne olduğunu kısaca anlatır mısınız?",
    "type": "Ziyaret mi, telefon mu, uzaktan destek mi?",
    "resolution": "Sorun nasıl çözüldü?",
    "resolved_date": "Ne zaman çözüldü?",
    "devices_affected": "Hangi cihazlar etkilendi?",
    "reported_by": "Kim bildirdi?",

    # Sites fields
    "customer": "Müşterinin adı ne?",
    "city": "Hangi şehirde?",
    "country": "Hangi ülkede?",
    "facility_type": "Tesis türü ne? (Gıda/Sağlık)",
    "contract_status": "Sözleşme durumu ne?",
    "go_live_date": "Kurulum tarihi ne?",
    "supervisor_1": "Sahadaki sorumlu kişi kim?",
    "phone_1": "Sorumlu kişinin telefon numarası ne?",
    "address": "Sahanın adresi ne?",
    "dashboard_link": "Dashboard linki var mı?",
    "whatsapp_group": "WhatsApp grup linki var mı?",

    # Implementation fields
    "internet_provider": "İnternet bağlantısını kim sağlıyor? (ERG Controls/Müşteri)",
    "ssid": "İnternet ağ adı (SSID) ne?",
    "password": "İnternet şifresi ne?",
    "handwash_time": "El yıkama süresi ne?",
    "gateway_placement": "Gateway nereye yerleştirildi?",
    "entry_time": "Giriş süresi ne?",
    "tag_clean_to_red_timeout": "Tag temiz→kırmızı zaman aşımı kaç saniye?",
    "dispenser_anchor_power_type": "Dezenfektan anchor güç türü ne?",
    "charging_dock_placement": "Şarj dock'u nereye yerleştirildi?",
    "tag_buzzer_vibration": "Tag buzzer/titreşim ayarı ne?",
    "dispenser_anchor_placement": "Dezenfektan/sabun anchor'ları nereye yerleştirildi?",
    "clean_hygiene_time": "Clean hygiene süresi kaç saniye?",
    "hp_alert_time": "HP uyarı süresi kaç saniye?",
    "hand_hygiene_time": "El hijyeni süresi kaç saniye?",
    "hand_hygiene_interval": "Dashboard'da el hijyeni aralığı ne?",
    "hand_hygiene_type": "El hijyeni türü ne?",

    # Hardware fields
    "device_type": "Hangi cihaz türü?",
    "qty": "Kaç adet?",
    "hw_version": "Donanım versiyonu (HW) ne?",
    "fw_version": "Yazılım versiyonu (FW) ne?",

    # Stock fields
    "location": "Hangi lokasyonda?",
    "condition": "Cihaz durumu ne? (Yeni/Yenilenmiş/Arızalı)",
}
