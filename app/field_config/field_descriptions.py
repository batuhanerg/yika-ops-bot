"""Turkish descriptions for implementation fields.

Technicians need context about what each Thingsboard attribute name means.
These descriptions are shown alongside the English attribute name in prompts.
Only implementation fields have descriptions — sites, hardware, support log,
and stock fields do not need them.
"""

from __future__ import annotations

FIELD_DESCRIPTIONS: dict[str, str] = {
    "clean_hygiene_time": "HP bölgesi dışında dezenfektan/sabun ile el temizliği yapıldıktan sonra badge'in yeşilden kırmızıya dönme süresi (saniye). HP bölgesine hiç girilmediğinde geçerlidir.",
    "hp_alert_time": "HP bölgesi içindeyken badge'in yeşilden kırmızıya dönme süresi (saniye). Örneğin kalite ekibi saatte bir el temizliği istiyorsa bu değer 3600 olur.",
    "hand_hygiene_time": "HP bölgesinden çıktıktan sonra badge'in yeşilden kırmızıya dönme süresi (saniye). Clean hygiene time'a benzer ama HP bölgesinden çıkış sonrası geçerlidir.",
    "hand_hygiene_interval": "Dashboard'da el hijyeni kontrol aralığı olarak görünen değer",
    "hand_hygiene_type": "El hijyeni türü — tek adımlı mı, iki adımlı mı",
    "tag_clean_to_red_timeout": "Tag'in temiz durumdan kırmızıya geçiş süresi (saniye)",
    "handwash_time": "El yıkama minimum süresi — ellerin sensör altında kalması gereken süre (saniye)",
    "entry_time": "Alana girdikten sonra el yıkama için tanınan süre (saniye)",
    "gateway_placement": "Gateway cihazının fiziksel konumu",
    "charging_dock_placement": "Şarj istasyonunun fiziksel konumu",
    "dispenser_anchor_placement": "Dezenfektan/sabun anchor'larının fiziksel konumu",
    "dispenser_anchor_power_type": "Anchor güç kaynağı türü — örneğin kablo, pil, power bank",
    "tag_buzzer_vibration": "Tag'lerde buzzer ve titreşim ayarı (açık/kapalı)",
    "internet_provider": "İnternet bağlantısını kim sağlıyor",
    "ssid": "WiFi ağ adı",
    "password": "WiFi şifresi",
}

# Implementation operations that should show descriptions
_IMPL_OPERATIONS = {"update_implementation"}


def get_field_description(field: str, operation: str) -> str | None:
    """Get description for a field, only for implementation operations."""
    if operation not in _IMPL_OPERATIONS:
        return None
    return FIELD_DESCRIPTIONS.get(field)
