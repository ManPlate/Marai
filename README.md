# 🔐 Marai — Offline Password Manager

> *Marai* (மறை) — an ancient Tamil word meaning "that which is hidden". In Sangam literature, Marai referred to sacred knowledge concealed from the world, accessible only to those who hold the key.
>
> Your passwords deserve the same protection.

---

## ✨ Features

- 🔐 **AES-256-GCM encryption** — military-grade encryption on all stored passwords
- 🔑 **Password generator** — generate strong passwords with custom length and character options
- 📊 **Password strength meter** — see instantly how strong a password is
- 🗂️ **Categories** — organise entries as Work, Email, Social, Finance, Dev or Other
- 🔍 **Search** — find any entry instantly
- 🔒 **Auto-lock** — vault locks automatically after 5 minutes of inactivity
- 📋 **Clipboard protection** — copied passwords never appear in Windows clipboard history (Win+V)
- 🛡️ **Login lockout** — 5 failed attempts triggers a 30-second cooldown
- 🔑 **Change master password** — re-encrypts the entire vault with the new password
- 🔔 **Auto update checker** — notifies you when a new version is available
- 💾 **Fully offline** — no data ever leaves your computer

---

## 🚀 Download

👉 **[Download the latest Marai.exe from Releases](https://github.com/ManPlate/Marai/releases)**

No installation needed. Just download and double-click.

> ⚠️ If Windows shows "Windows protected your PC", click **More info → Run anyway**.
> This is normal for apps distributed outside the Microsoft Store.

---

## 📦 Version History

<!-- VERSION_TABLE_START -->
| Version | What's New |
|---|---|
| **v2.1.0** ← current | Upgraded to Argon2id key derivation — silent migration on login |
| **v2.0.0** | Rebranded from VaultKey to Marai |
| **v1.7.0** | Passwords never enter Windows clipboard history (Win+V) |
| **v1.6.0** | Added automatic update checker |
| **v1.5.0** | Security hardening: lockout, auto-lock, clipboard clear |
| **v1.4.0** | Added password generator with strength meter |
| **v1.3.0** | Added ability to change master password |
| **v1.2.0** | Fixed card layout and resize behaviour |
| **v1.1.0** | Fixed compatibility with Python 3.14 on Windows |
| **v1.0.0** | Initial release |
<!-- VERSION_TABLE_END -->

---

## 🔒 Security

- All passwords encrypted with **AES-256-GCM** (authenticated encryption)
- Master password never stored — used only to derive the encryption key
- Key derivation uses **PBKDF2-HMAC-SHA256** with 390,000 iterations
- Random 16-byte salt generated per vault
- Copied passwords never saved to Windows clipboard history
- Auto-locks after 5 minutes of inactivity
- Encrypted vault stored locally at `C:\Users\YourName\.marai\`

---

## 🖥️ How to Update

1. Download the new `Marai.exe` from [Releases](https://github.com/ManPlate/Marai/releases)
2. Replace the old `Marai.exe` with the new one
3. Your passwords are safe — they are stored separately from the app

See [HOW_TO_UPDATE.md](HOW_TO_UPDATE.md) for full instructions.

---

## 🛠️ For Developers

Want to build from source? See [README_DEV.md](README_DEV.md) for setup instructions.

---

*Built with Python + tkinter. Encryption powered by the [cryptography](https://cryptography.io) library.*
