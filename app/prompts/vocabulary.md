# Enum Values & ERG-Specific Jargon

## Valid Enum Values

- **Support Type**: Visit, Remote, Call
- **Status**: Open, Resolved, Follow-up (ERG), Follow-up (Customer), Scheduled
- **Root Cause**: HW Fault (Production), HW Fault (Customer), FW Bug, Dashboard Bug, User Error, Configuration, Feature Request, Pending, Other
- **Facility Type**: Food, Healthcare
- **Device Type**: Tag, Anchor, Gateway, Charging Dock, Power Bank, Power Adapter, USB Cable, Other
- **Contract Status**: Active, Pending, Expired, Pilot
- **Stock Condition**: New, Refurbished, Faulty, Reserved
- **Stock Location**: Istanbul Office, Adana Storage, Other

## ERG-Specific Device Jargon

| Term | Maps To | Notes |
|---|---|---|
| yaka kartı, kart, rozet, badge | Tag | |
| çapa | Anchor | |
| yatak anchoru | Anchor | notes: "Hasta yatağı anchor" |
| dezenfektan anchoru | Anchor | notes: "Dezenfektan dispenser anchor" |
| sabun anchoru | Anchor | notes: "Sabun anchor" |
| ağ geçidi | Gateway | |
| şarj istasyonu, şarj dock'u | Charging Dock | |
| taşınabilir şarj | Power Bank | |
| güç adaptörü | Power Adapter | |

## ERG Root Cause Rules

- False alarm, data delay ("veri gecikmesi"), no actual issue → **User Error** (not Dashboard Bug)
- Production defect, "bozuk gelmiş", factory fault → **HW Fault (Production)**
- Customer damage, "düşürmüş", broken by customer → **HW Fault (Customer)**
