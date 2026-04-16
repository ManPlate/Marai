# MARAi

**Offline Desktop Password Manager — Hidden by Design**

MARAi is a zero-cloud, single-file password manager built with Python and tkinter. Your vault never leaves your machine. No accounts, no servers, no telemetry.

## Features

### Vault Security
- **AES-256-GCM** encryption with **Argon2id** key derivation (falls back to PBKDF2)
- **3-minute auto-lock** with live countdown timer — resets on any mouse/keyboard activity
- **Clipboard history exclusion** on Windows — passwords don't appear in Win+V
- **Auto-clear clipboard** after 30 seconds (90 seconds for AVD connections)
- Master password change without re-encrypting individual entries

### 12 Entry Categories
Each category has a tailored form with relevant fields:

| Category | Key Fields |
|---|---|
| Password | Username, password, URL |
| Bank Account | IFSC, Customer ID, App PIN, Profile Password |
| Credit Card | Card number, expiry, CVV, PIN, card type |
| Email Account | IMAP/SMTP servers, recovery email/phone |
| Domain Credential | Domain, username, password — linkable to servers |
| Server / RDP | Host, port, AVD workspace URL, linked credential |
| SSH Key | Host, port, passphrase, private/public key |
| Secure Note | Free-form encrypted text |
| Identity | ID type/number, issuing authority, dates |
| Wi-Fi Password | SSID, security type, router credentials |
| Software License | License key, version, purchase/expiry dates |
| Other | Flexible username/password/URL |

### Domain Credential Linking
Create a **Domain Credential** entry for shared org accounts, then link multiple **Server / RDP** entries to it. Change the password once — all linked servers use the updated credential automatically.

### Brand Icon System
- **150+ brand domains** mapped — banks, tech, fintech, entertainment, shopping
- Covers Indian banks (SBI, HDFC, ICICI, Axis, Kotak), international banks, and major services
- **Smart lookup**: entry name → word splitting → bank_name field → URL → domain heuristic
- **3-source fetch**: Google Favicons → DuckDuckGo → direct favicon.ico
- **Pillow LANCZOS** resizing at 64px/40px with automatic white background removal
- **Disk cache** at `~/.marai/icons/` — offline after first fetch
- **Custom icon upload** — pick any PNG/GIF per entry

### 10 Themes with Per-Vault Support
Each vault can have its own theme. Switch tabs and the entire UI transforms.

**Dark themes:** Dark (indigo), Emerald (green), Ocean (cyan), Mocha (brown), Neon (hot pink)

**Light themes:** Ferrari (red), Sage Green, Rose (pink), Amber (gold), Mint (teal)

### Multi-Vault Tabs
- Open multiple vaults side-by-side in tabs
- Each vault has its own lock screen, theme, and auto-lock timer
- **Tabs persist across restarts** — no need to re-add every time
- Add vaults from any directory (portable/USB friendly)

### RDP & AVD Connections
- **Standard RDP**: credentials passed via Windows Credential Manager (`CredWriteW`) — password never touches clipboard. Auto-cleaned after 10 seconds.
- **Azure Virtual Desktop**: password copied securely to clipboard with 90-second timer for double-paste MFA flows
- Connect buttons show **▶ AVD** or **▶ RDP** based on entry type
- **Connection Label** field — distinguish "Production", "Dev", "UAT" at a glance

### Views & Zoom
- **4 view modes**: List (single-line rows), Small (icon grid), Medium, Large
- **Zoom controls** (60%–180%) — adjust card and icon sizes
- **Move buttons** (▲▼) on all views for manual entry reordering
- **Work/Personal** multi-select toggles — filter by context without losing the other
- **Category filter** — quick-filter by any of the 12 entry types
- Full-text search across all fields

### Import, Export & Backup
- **Export** as JSON or CSV — compatible with other password managers
- **Import** from JSON or CSV with automatic format detection
- **Encrypted backup** — timestamped folder with vault files and manifest

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
Download `MARAi.exe` from the [latest release](https://github.com/ManPlate/Marai/releases) — no Python needed.

### Build your own .exe
```bash
pip install pyinstaller
pyinstaller --onefile --windowed --icon=marai.ico --name=MARAi marai.py
```

### Portable mode
Place `MARAi.exe` or `marai.py` on a USB drive. The vault stores next to the executable.

## Dependencies

| Package | Required | Purpose |
|---|---|---|
| `cryptography` | Yes | AES-GCM encryption |
| `pyperclip` | Yes | Cross-platform clipboard |
| `Pillow` | Yes | High-quality icon resizing |
| `argon2-cffi` | Optional | Stronger key derivation (Argon2id) |

## Data Storage

All data is stored locally:

```
~/.marai/
├── config.json        # Settings, themes, vault tabs
├── meta.json          # Salt + verification hash
├── vault.enc          # AES-256-GCM encrypted vault
└── icons/             # Cached brand icons (PNG)
```

Nothing is sent anywhere. No analytics, no cloud sync, no accounts.

## License

See [LICENSE](LICENSE) for details.

---

**Built by [ManPlate](https://github.com/ManPlate)** — contributions and feedback welcome.
