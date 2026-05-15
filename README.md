# MARAi

**Offline Desktop Password Manager — Hidden by Design**

MARAi is a zero-cloud, single-file password manager built with Python and tkinter. Your vault never leaves your machine. No accounts, no servers, no telemetry.

## Features

### Vault Security
- **AES-256-GCM** encryption with **Argon2id** key derivation (falls back to PBKDF2)
- **3-minute auto-lock** with live countdown — resets on activity
- **Clipboard history exclusion** on Windows — passwords don't appear in Win+V
- **Auto-clear clipboard** with live countdown (30s standard, 90s for AVD)
- Master password change without re-encrypting entries

### 🛡 Vault Health Dashboard
- **Breach detection** via Have I Been Pwned (k-anonymity — only 5 chars of SHA-1 hash sent)
- **Weak password detection** — flags anything below "Strong"
- **Reused password detection** — flags entries sharing the same password
- **Stale password detection** — entries not updated in 90+ days
- **Auto-check on launch** — optional toggle for automatic breach checks
- **Live shield indicator** — green ✓, amber !, or red count in toolbar
- **Health filter** — single click to show only entries with issues
- **Breach persistence** — results saved across sessions, cards highlighted until fixed

### 12 Entry Categories
| Category | Key Fields |
|---|---|
| Password | Username, password, URL |
| Bank Account | IFSC, Customer ID, Net Banking, App PIN, Profile Password |
| Credit Card | Card number, expiry, CVV, PIN, card type |
| Email Account | IMAP/SMTP, recovery email/phone |
| Domain Credential | Domain, username, password — linkable to servers |
| Server / RDP | Host, port, AVD workspace, linked credential |
| SSH Key | Host, passphrase, private/public key |
| Secure Note | Free-form encrypted text |
| Identity | ID type/number, issuing authority, dates |
| Wi-Fi Password | SSID, security type, router credentials |
| Software License | License key, version, purchase/expiry |
| Other | Flexible username/password/URL |

All categories support **custom fields** — add any name:value pairs.

### Domain Credential Linking
Create a Domain Credential, then link Server / RDP entries to it. Change the password once — all linked servers use the updated credential.

### Brand Icon System
- **150+ brands** — banks, tech, fintech, entertainment, shopping, Indian utilities
- Smart matching: longest match wins, short brands need word match
- 3-source fetch: Google Favicons → DuckDuckGo → direct favicon.ico
- Pillow LANCZOS resizing, white background removal, disk cache
- Custom icon upload per entry

### 10 Themes with Per-Vault Support
Dark, Emerald, Ocean, Mocha, Neon, Ferrari, Sage Green, Rose, Amber, Mint — each vault remembers its own theme.

### Adaptive Layout
- **Column chooser** — `◀ 3 columns ▶` adjusts from list (1 col) to dense grid (6 cols)
- Adaptive card height, saved in config
- Full-text search with 250ms debounce
- Work/Personal context toggles
- Category filter

### RDP & AVD Connections
- **Standard RDP**: credentials via Windows Credential Manager — never touches clipboard
- **Azure Virtual Desktop**: 90-second clipboard timer for double-paste MFA
- Connection labels for Production/Dev/UAT

### Import, Export & Backup
- JSON/CSV export and import
- Encrypted timestamped backup with reminder (⚠ after 7 days)

## Installation

### Requirements
- Python 3.8+
- Windows 10/11 (primary), Linux/macOS (basic support)

### From source
```bash
pip install cryptography pyperclip Pillow
pip install argon2-cffi  # optional, recommended
python marai.py
```

### Windows executable
Download `MARAi.exe` from the [latest release](https://github.com/ManPlate/Marai/releases).

### Build .exe
```bash
pyinstaller --onefile --windowed --icon=marai.ico --name=MARAi marai.py
```

## Dependencies

| Package | Required | Purpose |
|---|---|---|
| `cryptography` | Yes | AES-GCM encryption |
| `pyperclip` | Yes | Cross-platform clipboard |
| `Pillow` | Yes | Icon resizing, shield/eye rendering |
| `argon2-cffi` | Optional | Stronger key derivation (Argon2id) |

## Data Storage

```
~/.marai/
├── config.json        # Settings, themes, vault tabs
├── meta.json          # Salt + verification hash
├── vault.enc          # AES-256-GCM encrypted vault
├── breached.txt       # SHA-1 hashes of breached passwords
└── icons/             # Cached brand icons
```

Nothing is sent anywhere. No analytics, no cloud sync, no accounts.

## License

See [LICENSE](LICENSE) for details.

---

**Built by [ManPlate](https://github.com/ManPlate)**
