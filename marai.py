#!/usr/bin/env python3
"""
Marai — Offline Desktop Password Manager
Requires: pip install cryptography pyperclip
"""

import tkinter as tk
from tkinter import messagebox, ttk
import json, os, base64, secrets, string, threading, urllib.request, webbrowser, subprocess, ctypes, sys, datetime

# ── Version ────────────────────────────────────────────────────────────────
VERSION = "2.4.2"
CHANGELOG = [
    ("2.4.2", "Auto-copy password when launching URL or RDP session"),
    ("2.4.1", "Portable USB mode — zero setup on any machine"),
    ("2.4.0", "Category filters, URL launch, search all fields, custom vault folder"),
    ("2.3.0", "RDP session launch from Server entries"),
    ("2.2.0", "Favourite entries and password age indicator"),
    ("2.1.0", "Upgraded to Argon2id key derivation — silent migration on login"),
    ("2.0.0", "Rebranded from VaultKey to Marai"),
    ("1.7.0", "Passwords never enter Windows clipboard history (Win+V)"),
    ("1.6.0", "Added automatic update checker"),
    ("1.5.0", "Security hardening: lockout, auto-lock, clipboard clear"),
    ("1.4.0", "Added password generator with strength meter"),
    ("1.3.0", "Added ability to change master password"),
    ("1.2.0", "Fixed card layout and resize behaviour"),
    ("1.1.0", "Fixed compatibility with Python 3.14 on Windows"),
    ("1.0.0", "Initial release"),
]

# ── Update Checker ────────────────────────────────────────────────────────
GITHUB_USER    = "ManPlate"
GITHUB_REPO    = "Marai"
VERSION_URL    = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main/version.json"
RELEASES_URL   = f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}/releases"

def check_for_update(callback):
    """Runs in a background thread. Calls callback(new_version) if update found."""
    def _check():
        try:
            req = urllib.request.Request(
                VERSION_URL,
                headers={"User-Agent": f"Marai/{VERSION}"}
            )
            with urllib.request.urlopen(req, timeout=5) as r:
                data    = json.loads(r.read().decode())
                latest  = data.get("version", "")
                if latest and latest != VERSION:
                    # Compare version tuples e.g. 1.6.0 vs 1.5.0
                    def parse(v): return tuple(int(x) for x in v.split("."))
                    if parse(latest) > parse(VERSION):
                        callback(latest)
        except Exception:
            pass   # Silently fail — app works fully offline
    threading.Thread(target=_check, daemon=True).start()

try:
    import pyperclip
    CLIPBOARD_OK = True
except ImportError:
    CLIPBOARD_OK = False

try:
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    CRYPTO_OK = True
except ImportError:
    CRYPTO_OK = False

try:
    from argon2.low_level import hash_secret_raw, Type
    ARGON2_OK = True
except ImportError:
    ARGON2_OK = False

# ── Paths ──────────────────────────────────────────────────────────────────
# CONFIG_DIR always lives at ~/.marai on the local machine
CONFIG_DIR  = os.path.join(os.path.expanduser("~"), ".marai")
os.makedirs(CONFIG_DIR, exist_ok=True)

def _exe_dir():
    """Return the directory containing the running exe or script."""
    import sys
    if getattr(sys, "_MEIPASS", None):
        # PyInstaller bundle — use the exe's directory
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def _portable_config_file():
    """config.json next to the exe — used when running from USB."""
    return os.path.join(_exe_dir(), "config.json")

def _local_config_file():
    """config.json in ~/.marai — used for normal installs."""
    return os.path.join(CONFIG_DIR, "config.json")

def _active_config_file():
    """
    Prefer config.json next to the exe (portable/USB mode).
    Fall back to ~/.marai/config.json for normal installs.
    Portable config is detected by its presence next to the exe,
    OR by vault files existing next to the exe.
    """
    portable = _portable_config_file()
    exe_dir  = _exe_dir()
    # If config.json already exists next to exe, always use it (USB mode)
    if os.path.exists(portable):
        return portable
    # If vault files exist next to exe, auto-create portable config there
    if (os.path.exists(os.path.join(exe_dir, "vault.enc")) or
            os.path.exists(os.path.join(exe_dir, "meta.json"))):
        return portable
    return _local_config_file()

def _load_config():
    """Load app config. Returns dict with defaults if file missing."""
    cfg_file = _active_config_file()
    defaults = {"vault_dir": os.path.dirname(cfg_file)
                if cfg_file == _portable_config_file() else CONFIG_DIR}
    try:
        if os.path.exists(cfg_file):
            with open(cfg_file, encoding="utf-8") as f:
                data = json.load(f)
            defaults.update(data)
    except Exception:
        pass
    return defaults

def _save_config(data):
    cfg_file = _active_config_file()
    try:
        with open(cfg_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        # If we cannot write next to exe (e.g. read-only), fall back to local
        try:
            with open(_local_config_file(), "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

def _get_vault_dir():
    return _load_config().get("vault_dir", CONFIG_DIR)

def _set_vault_dir(path):
    cfg = _load_config()
    cfg["vault_dir"] = path
    _save_config(cfg)
    _refresh_paths(path)

def _refresh_paths(vault_dir=None):
    """Update module-level VAULT_FILE and META_FILE to point at vault_dir."""
    global APP_DIR, VAULT_FILE, META_FILE
    APP_DIR    = vault_dir or _get_vault_dir()
    VAULT_FILE = os.path.join(APP_DIR, "vault.enc")
    META_FILE  = os.path.join(APP_DIR, "meta.json")
    os.makedirs(APP_DIR, exist_ok=True)

# Initialise paths from config on startup
APP_DIR    = CONFIG_DIR
VAULT_FILE = os.path.join(APP_DIR, "vault.enc")
META_FILE  = os.path.join(APP_DIR, "meta.json")
_refresh_paths()

# ── Migrate from VaultKey if needed ───────────────────────────────────────
def migrate_from_vaultkey():
    old_dir = os.path.join(os.path.expanduser("~"), ".vaultkey")
    if not os.path.exists(old_dir):
        return
    if os.path.exists(os.path.join(CONFIG_DIR, "meta.json")):
        return
    import shutil
    try:
        for fname in ["vault.enc", "meta.json"]:
            src = os.path.join(old_dir, fname)
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(CONFIG_DIR, fname))
        open(os.path.join(CONFIG_DIR, ".needs_token_patch"), "w").close()
    except Exception:
        pass

migrate_from_vaultkey()


def patch_verify_token_if_needed(key):
    """Called after successful unlock to update VAULTKEY_OK -> MARAI_OK."""
    flag = os.path.join(CONFIG_DIR, ".needs_token_patch")
    if not os.path.exists(flag):
        return
    try:
        new_verify = encrypt_data(key, "MARAI_OK")
        with open(META_FILE, encoding="utf-8") as f:
            meta = json.load(f)
        meta["verify"] = base64.b64encode(new_verify).decode()
        with open(META_FILE, "w", encoding="utf-8") as f:
            json.dump(meta, f)
        os.remove(flag)
    except Exception:
        pass

# ── Crypto ─────────────────────────────────────────────────────────────────
# Argon2id parameters (OWASP recommended minimums)
ARGON2_TIME_COST   = 3       # iterations
ARGON2_MEMORY_COST = 65536   # 64 MB
ARGON2_PARALLELISM = 4
ARGON2_HASH_LEN    = 32
KDF_VERSION        = "argon2id"

def derive_key_argon2id(password, salt):
    """Argon2id — memory-hard, GPU-resistant. Current default."""
    return hash_secret_raw(
        secret      = password.encode(),
        salt        = salt,
        time_cost   = ARGON2_TIME_COST,
        memory_cost = ARGON2_MEMORY_COST,
        parallelism = ARGON2_PARALLELISM,
        hash_len    = ARGON2_HASH_LEN,
        type        = Type.ID
    )

def derive_key_pbkdf2(password, salt):
    """PBKDF2 — legacy, used for migrating old vaults only."""
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=390000)
    return kdf.derive(password.encode())

def derive_key(password, salt, kdf=None):
    """Derive key using the appropriate KDF. Defaults to Argon2id."""
    if kdf == "pbkdf2" or (not ARGON2_OK):
        return derive_key_pbkdf2(password, salt)
    return derive_key_argon2id(password, salt)

def encrypt_data(key, plaintext):
    iv = secrets.token_bytes(12)
    ct = AESGCM(key).encrypt(iv, plaintext.encode(), None)
    return iv + ct

def decrypt_data(key, ciphertext):
    iv, ct = ciphertext[:12], ciphertext[12:]
    return AESGCM(key).decrypt(iv, ct, None).decode()

def load_meta():
    if os.path.exists(META_FILE):
        with open(META_FILE, encoding="utf-8") as f:
            return json.load(f)
    return None

def save_meta(salt_b64, verify_b64, kdf=KDF_VERSION):
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump({"salt": salt_b64, "verify": verify_b64, "kdf": kdf}, f)

def vault_exists():
    return os.path.exists(META_FILE) and os.path.exists(VAULT_FILE)

# ── Theme ──────────────────────────────────────────────────────────────────
BG       = "#0e0e16"
SURFACE  = "#16161f"
SURFACE2 = "#1e1e2a"
BORDER   = "#2d2d42"
ACCENT   = "#7c5cfc"
GREEN    = "#4ecca3"
RED      = "#fc5c7d"
TEXT     = "#e4e4f0"
MUTED    = "#6b6b90"

SURFACE3   = "#23233a"   # card hover state
CARD_BORDER= "#3a3a55"   # card border — slightly lighter than BORDER

FNT_TITLE  = ("Courier New", 22, "bold")
FNT_HEAD   = ("Segoe UI", 12, "bold")
FNT_BODY   = ("Segoe UI", 11)
FNT_MONO   = ("Courier New", 11)
FNT_SM     = ("Segoe UI", 9)
FNT_BTN    = ("Segoe UI", 11, "bold")

CAT_COLORS = {
    "Server":  ("#60d0a0", "#0e2a20"),
    "Work":    ("#9f7eff", "#1a1035"),
    "Email":   ("#ff7a9a", "#300f20"),
    "Social":  ("#4ecca3", "#0e2e27"),
    "Finance": ("#ffb347", "#2e1e0a"),
    "Dev":     ("#61dafb", "#0a2030"),
    "Other":   ("#8888aa", "#18182a"),
}
CAT_EMOJI  = {"Work":"💼","Email":"📧","Social":"🌐","Finance":"💳","Dev":"💻","Server":"🖥","Other":"📁"}

def _password_age(entry):
    """
    Returns (age_text, colour) based on when the password was last updated.
    Green < 30 days, Yellow 30-90 days, Red > 90 days, Grey if unknown.
    """
    ts = entry.get("updated_at")
    if not ts:
        return "Age unknown", MUTED
    try:
        updated = datetime.datetime.fromisoformat(ts)
        days = (datetime.datetime.now() - updated).days
        if days < 30:
            return f"Updated {days}d ago", GREEN
        elif days < 90:
            return f"Updated {days}d ago", "#ffb347"
        else:
            return f"Updated {days}d ago ⚠", RED
    except Exception:
        return "Age unknown", MUTED
CATEGORIES = list(CAT_COLORS.keys())

# ── Styled Button helper ───────────────────────────────────────────────────
class Tooltip:
    """Shows a small dark tooltip popup on hover."""
    def __init__(self, widget, text):
        self.widget = widget
        self.text   = text
        self.tip    = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)

    def _show(self, e=None):
        x = self.widget.winfo_rootx() + self.widget.winfo_width() // 2
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(tw, text=self.text, font=("Segoe UI", 9),
                 bg="#2a2a3d", fg=TEXT, relief="flat",
                 padx=8, pady=4).pack()

    def _hide(self, e=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None


def mk_btn(parent, text, cmd, bg=ACCENT, fg="white", w=16, tooltip=None):
    b = tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg,
                  font=FNT_BTN, relief="flat", cursor="hand2",
                  activebackground=ACCENT, activeforeground="white",
                  padx=14, pady=8, width=w, bd=0)
    b.bind("<Enter>", lambda e: b.config(bg=_lighten(bg)))
    b.bind("<Leave>", lambda e: b.config(bg=bg))
    if tooltip:
        Tooltip(b, tooltip)
    return b

def _lighten(hex_color):
    r,g,b = int(hex_color[1:3],16),int(hex_color[3:5],16),int(hex_color[5:7],16)
    r,g,b = min(255,r+30),min(255,g+30),min(255,b+30)
    return f"#{r:02x}{g:02x}{b:02x}"

def mk_entry(parent, var, show=None, mono=False, w=30):
    return tk.Entry(parent, textvariable=var,
                    font=FNT_MONO if mono else FNT_BODY,
                    bg=SURFACE2, fg=TEXT, insertbackground=TEXT,
                    relief="flat", show=show or "", width=w)

# ══════════════════════════════════════════════════════════════════════════════
# Lock Screen
# ══════════════════════════════════════════════════════════════════════════════
def _draw_concentric_logo(canvas, cx, cy, size, bg):
    """
    Draw the MARAi concentric heptagon logo on a canvas.
    size controls the outermost ring radius.
    bg is the canvas background colour — used for the inner fill.
    """
    import math
    def pts(rx, ry, n, rot):
        p = []
        for i in range(n):
            a = math.radians(rot + i * 360 / n)
            p.extend([cx + rx * math.cos(a), cy + ry * math.sin(a)])
        return p

    s = size / 60  # scale factor relative to design size 60
    canvas.create_polygon(pts(52*s,48*s,7,12), fill="", outline="#2a1f5e", width=1)
    canvas.create_polygon(pts(46*s,42*s,7,22), fill="", outline="#3d2d8a", width=1)
    canvas.create_polygon(pts(39*s,36*s,7,5),  fill="", outline="#5438b0", width=2*s if 2*s > 1 else 1)
    canvas.create_polygon(pts(31*s,29*s,7,18), fill="", outline=ACCENT,    width=2*s if 2*s > 1 else 1)
    canvas.create_polygon(pts(22*s,21*s,7,8),  fill="", outline="#9d7fff", width=2*s if 2*s > 1 else 1)
    canvas.create_polygon(pts(13*s,13*s,7,20), fill="#1e1040", outline="#c4b0ff", width=max(1, 1.5*s))
    canvas.create_oval(cx-9*s, cy-9*s, cx+9*s, cy+9*s, fill="#c4b0ff", outline="")
    canvas.create_oval(cx-5*s, cy-5*s, cx+5*s, cy+5*s, fill="#ffffff",  outline="")


class LockScreen(tk.Frame):
    def __init__(self, master, on_unlock):
        super().__init__(master, bg=BG)
        self.on_unlock = on_unlock
        self.pack(fill="both", expand=True)
        self._build()

    def _build(self):
        # ── About button — top right corner ──────────────────────────────
        about_btn = tk.Button(self, text="ℹ  About MARAi",
                              font=("Segoe UI", 10),
                              bg=SURFACE2, fg=TEXT,
                              relief="flat", cursor="hand2", bd=0,
                              padx=14, pady=8,
                              command=lambda: VaultApp._show_about_static(
                                  self.winfo_toplevel()))
        about_btn.place(relx=1.0, rely=0.0, anchor="ne", x=-16, y=16)
        about_btn.bind("<Enter>", lambda e: about_btn.config(bg=ACCENT, fg="white"))
        about_btn.bind("<Leave>", lambda e: about_btn.config(bg=SURFACE2, fg=TEXT))

        # ── Vault location button — bottom left corner ────────────────────
        def _change_location():
            from tkinter import filedialog
            new_dir = filedialog.askdirectory(
                title="Choose Vault Folder",
                initialdir=_get_vault_dir(),
                parent=self.winfo_toplevel()
            )
            if not new_dir:
                return
            _set_vault_dir(new_dir)
            _refresh_paths(new_dir)
            # Rebuild lock screen via App so the window stays intact
            app = self.winfo_toplevel()
            if hasattr(app, "_show_lock"):
                app._show_lock()

        loc_btn = tk.Button(self, text="📂  Vault Location",
                            font=("Segoe UI", 9),
                            bg=SURFACE2, fg=MUTED,
                            relief="flat", cursor="hand2", bd=0,
                            padx=12, pady=6,
                            command=_change_location)
        loc_btn.place(relx=0.0, rely=1.0, anchor="sw", x=16, y=-16)
        loc_btn.bind("<Enter>", lambda e: loc_btn.config(fg=TEXT))
        loc_btn.bind("<Leave>", lambda e: loc_btn.config(fg=MUTED))

        center = tk.Frame(self, bg=BG)
        center.place(relx=0.5, rely=0.5, anchor="center")

        # ── Concentric logo icon ──────────────────────────────────────────
        icon_size = 120
        c = tk.Canvas(center, width=icon_size, height=icon_size,
                      bg=BG, highlightthickness=0)
        c.pack(pady=(0, 10))
        _draw_concentric_logo(c, icon_size/2, icon_size/2, icon_size/2, BG)

        # ── Name with letter spacing ──────────────────────────────────────
        tk.Label(center, text="M  A  R  A  i",
                 font=("Segoe UI", 26, "bold"),
                 fg=ACCENT, bg=BG).pack()
        tk.Label(center, text="Your offline password vault, hidden by design.",
                 font=("Segoe UI", 10, "italic"), fg=MUTED, bg=BG).pack(pady=(4, 24))

        card = tk.Frame(center, bg=SURFACE, padx=40, pady=32,
                        highlightbackground=BORDER, highlightthickness=1)
        card.pack()

        if not vault_exists():
            self._build_setup(card)
        else:
            self._build_login(card)

    def _build_login(self, card):
        self._attempts   = 0
        self._locked_out = False

        tk.Label(card, text="MASTER PASSWORD", font=FNT_SM,
                 fg=MUTED, bg=SURFACE).pack(anchor="w")
        self.pw_var = tk.StringVar()
        self._pw_entry = mk_entry(card, self.pw_var, show="●", mono=True, w=32)
        self._pw_entry.pack(fill="x", ipady=10, pady=(4,0))
        self._pw_entry.bind("<Return>", lambda _: self._do_login())
        self._pw_entry.focus_set()

        self.err_lbl = tk.Label(card, text="", font=FNT_SM, fg=RED, bg=SURFACE)
        self.err_lbl.pack(pady=(8,0))

        tk.Frame(card, bg=SURFACE, height=12).pack()
        self._unlock_btn = mk_btn(card, "Unlock Vault", self._do_login, w=24)
        self._unlock_btn.pack(fill="x")

    def _do_login(self):
        if self._locked_out:
            return
        pw = self.pw_var.get()
        meta = load_meta()
        if not meta:
            self.err_lbl.config(text="No vault found."); return
        salt     = base64.b64decode(meta["salt"])
        kdf_used = meta.get("kdf", "pbkdf2")   # old vaults have no kdf field
        try:
            key    = derive_key(pw, salt, kdf=kdf_used)
            verify = base64.b64decode(meta["verify"])
            # Accept both old VaultKey token and new Marai token
            decrypted = decrypt_data(key, verify)
            if decrypted not in ("MARAI_OK", "VAULTKEY_OK"):
                raise ValueError
            self._attempts = 0
            patch_verify_token_if_needed(key)
            # Silent upgrade: if vault still uses PBKDF2, re-derive with
            # Argon2id and re-encrypt everything in the background
            if kdf_used == "pbkdf2" and ARGON2_OK:
                self.after(200, lambda: self._upgrade_kdf(pw, key))
            self.on_unlock(key)
        except Exception:
            self._attempts += 1
            remaining = 5 - self._attempts
            if self._attempts >= 5:
                self._locked_out = True
                self._unlock_btn.config(state="disabled")
                self._pw_entry.config(state="disabled")
                self._countdown(30)
            else:
                self.err_lbl.config(
                    text=f"Incorrect password. {remaining} attempt{'s' if remaining != 1 else ''} remaining.",
                    fg=RED)
            self.pw_var.set("")

    def _upgrade_kdf(self, password, old_key):
        """
        Silently re-encrypts the vault using Argon2id.
        Runs once after first login on any PBKDF2 vault.
        The user never sees this happen.
        """
        try:
            # Load existing vault data with old key
            with open(VAULT_FILE, "rb") as f:
                raw = f.read()
            vault_json = decrypt_data(old_key, raw)

            # Generate new salt and derive Argon2id key
            new_salt = secrets.token_bytes(16)
            new_key  = derive_key(password, new_salt, kdf="argon2id")

            # Re-encrypt vault and verification token
            new_vault_ct  = encrypt_data(new_key, vault_json)
            new_verify_ct = encrypt_data(new_key, "MARAI_OK")

            with open(VAULT_FILE, "wb") as f:
                f.write(new_vault_ct)
            save_meta(
                base64.b64encode(new_salt).decode(),
                base64.b64encode(new_verify_ct).decode(),
                kdf="argon2id"
            )
            # Update the in-memory key so auto-save uses new key
            # Find the VaultApp frame inside app.content
            app = self.winfo_toplevel()
            for child in app.winfo_children():
                if hasattr(child, "key"):
                    child.key = new_key
                    break
        except Exception:
            pass   # If anything fails, vault remains on PBKDF2 — no data loss

    def _countdown(self, secs):
        if secs > 0:
            self.err_lbl.config(
                text=f"Too many attempts. Wait {secs}s before trying again.",
                fg="#ffb347")
            self.after(1000, lambda: self._countdown(secs - 1))
        else:
            self._locked_out = False
            self._attempts   = 0
            self._unlock_btn.config(state="normal")
            self._pw_entry.config(state="normal")
            self.err_lbl.config(text="You may try again.", fg=GREEN)
            self._pw_entry.focus_set()

    def _build_setup(self, card):
        tk.Label(card, text="Welcome! Set up your vault.",
                 font=FNT_BODY, fg=TEXT, bg=SURFACE).pack(pady=(0,16))

        # ── Vault location picker ─────────────────────────────────────────
        loc_frame = tk.Frame(card, bg=SURFACE)
        loc_frame.pack(fill="x", pady=(0,14))
        tk.Label(loc_frame, text="VAULT LOCATION", font=FNT_SM,
                 fg=MUTED, bg=SURFACE).pack(anchor="w")
        loc_row = tk.Frame(loc_frame, bg=SURFACE)
        loc_row.pack(fill="x", pady=(4,0))
        self._loc_var = tk.StringVar(value=_get_vault_dir())
        loc_lbl = tk.Label(loc_row, textvariable=self._loc_var,
                           font=("Segoe UI", 8), fg=MUTED, bg=SURFACE2,
                           anchor="w", padx=8, pady=6)
        loc_lbl.pack(side="left", fill="x", expand=True)

        def _pick_location():
            from tkinter import filedialog
            new_dir = filedialog.askdirectory(
                title="Choose where to store your vault",
                initialdir=_get_vault_dir(),
                parent=self.winfo_toplevel()
            )
            if new_dir:
                _set_vault_dir(new_dir)
                _refresh_paths(new_dir)
                self._loc_var.set(new_dir)

        mk_btn(loc_row, "📂 Browse", _pick_location,
               bg=SURFACE2, fg=TEXT, w=10).pack(side="left", padx=(6,0))
        tk.Label(loc_frame,
                 text="Default saves to your user folder. Change to a USB drive for portable use.",
                 font=("Segoe UI", 8), fg=MUTED, bg=SURFACE,
                 wraplength=300, justify="left").pack(anchor="w", pady=(4,0))

        tk.Frame(card, bg=BORDER, height=1).pack(fill="x", pady=(0,14))

        # ── Master password ───────────────────────────────────────────────
        tk.Label(card, text="MASTER PASSWORD", font=FNT_SM,
                 fg=MUTED, bg=SURFACE).pack(anchor="w")
        self.pw_var = tk.StringVar()
        mk_entry(card, self.pw_var, show="●", mono=True, w=32).pack(
            fill="x", ipady=10, pady=(4,14))

        tk.Label(card, text="CONFIRM PASSWORD", font=FNT_SM,
                 fg=MUTED, bg=SURFACE).pack(anchor="w")
        self.conf_var = tk.StringVar()
        e2 = mk_entry(card, self.conf_var, show="●", mono=True, w=32)
        e2.pack(fill="x", ipady=10, pady=(4,0))
        e2.bind("<Return>", lambda _: self._do_setup())

        self.err_lbl = tk.Label(card, text="", font=FNT_SM, fg=RED, bg=SURFACE)
        self.err_lbl.pack(pady=(8,0))

        tk.Frame(card, bg=SURFACE, height=12).pack()
        mk_btn(card, "Create Vault", self._do_setup, w=24).pack(fill="x")
        tk.Label(card,
                 text="This password encrypts all data.\nThere is no recovery if forgotten.",
                 font=FNT_SM, fg=MUTED, bg=SURFACE, justify="center").pack(pady=(12,0))

    def _do_setup(self):
        pw = self.pw_var.get()
        cf = self.conf_var.get()
        if not pw:
            self.err_lbl.config(text="Password cannot be empty."); return
        if pw != cf:
            self.err_lbl.config(text="Passwords do not match."); return
        salt      = secrets.token_bytes(16)
        key       = derive_key(pw, salt, kdf="argon2id" if ARGON2_OK else "pbkdf2")
        verify_ct = encrypt_data(key, "MARAI_OK")
        save_meta(base64.b64encode(salt).decode(),
                  base64.b64encode(verify_ct).decode(),
                  kdf="argon2id" if ARGON2_OK else "pbkdf2")
        raw = encrypt_data(key, json.dumps([]))
        with open(VAULT_FILE, "wb") as f:
            f.write(raw)
        self.on_unlock(key)


# ── Dialog Title Bar helper ───────────────────────────────────────────────
def make_dialog(win, title, w, h):
    """
    Applies a consistent custom title bar to any Toplevel dialog.
    Replaces the native OS title bar with a styled dark bar.
    """
    win.overrideredirect(True)
    win.configure(bg=SURFACE)
    _centre_on_parent(win, win.master if win.master else win, w, h)
    win.grab_set()

    # Title bar frame
    bar = tk.Frame(win, bg=TITLEBAR_BG, height=TITLEBAR_H)
    bar.pack(fill="x", side="top")
    bar.pack_propagate(False)

    # Title label
    lbl = tk.Label(bar, text=title, font=("Segoe UI", 10, "bold"),
                   fg=TEXT, bg=TITLEBAR_BG, anchor="w")
    lbl.pack(side="left", padx=12, fill="y")

    # Close button
    def _close():
        win.grab_release()
        win.destroy()

    close_btn = tk.Label(bar, text="✕", width=4,
                         font=("Segoe UI", 10), fg="#aaaacc",
                         bg=TITLEBAR_BG, cursor="hand2")
    close_btn.pack(side="right")
    close_btn.bind("<Enter>",    lambda e: close_btn.config(bg=BTN_CLOSE_HOV, fg="white"))
    close_btn.bind("<Leave>",    lambda e: close_btn.config(bg=TITLEBAR_BG,   fg="#aaaacc"))
    close_btn.bind("<Button-1>", lambda e: _close())

    # Drag support
    drag = {"x": 0, "y": 0}
    def _start(e):
        drag["x"] = e.x_root - win.winfo_x()
        drag["y"] = e.y_root - win.winfo_y()
    def _drag(e):
        win.geometry(f"+{e.x_root - drag['x']}+{e.y_root - drag['y']}")
    for w_ in (bar, lbl):
        w_.bind("<ButtonPress-1>", _start)
        w_.bind("<B1-Motion>",     _drag)

    # Thin separator
    tk.Frame(win, bg=BORDER, height=1).pack(fill="x")

    return _close   # caller can use this as the destroy function


# ── Styled scrollbar ──────────────────────────────────────────────────────
def mk_scrollbar(parent, **kw):
    """A ttk scrollbar styled to match the dark theme."""
    style = ttk.Style()
    style.theme_use("clam")
    style.configure("Dark.Vertical.TScrollbar",
                    background=SURFACE2,
                    troughcolor=SURFACE,
                    bordercolor=SURFACE,
                    arrowcolor=MUTED,
                    darkcolor=SURFACE2,
                    lightcolor=SURFACE2)
    style.map("Dark.Vertical.TScrollbar",
              background=[("active", ACCENT)])
    return ttk.Scrollbar(parent, style="Dark.Vertical.TScrollbar", **kw)


# ── Password Generator Helper ─────────────────────────────────────────────
def generate_password(length=16, upper=True, lower=True,
                      digits=True, symbols=True):
    pool = ""
    required = []
    if upper:
        pool += string.ascii_uppercase
        required.append(secrets.choice(string.ascii_uppercase))
    if lower:
        pool += string.ascii_lowercase
        required.append(secrets.choice(string.ascii_lowercase))
    if digits:
        pool += string.digits
        required.append(secrets.choice(string.digits))
    if symbols:
        sym = "!@#$%^&*()_+-=[]{}|;:,.<>?"
        pool += sym
        required.append(secrets.choice(sym))
    if not pool:
        pool = string.ascii_letters + string.digits
    remaining = [secrets.choice(pool) for _ in range(length - len(required))]
    pw_list = required + remaining
    secrets.SystemRandom().shuffle(pw_list)
    return "".join(pw_list)

def password_strength(pw):
    score = 0
    if len(pw) >= 8:  score += 1
    if len(pw) >= 12: score += 1
    if len(pw) >= 16: score += 1
    if any(c.isupper() for c in pw):   score += 1
    if any(c.islower() for c in pw):   score += 1
    if any(c.isdigit() for c in pw):   score += 1
    if any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in pw): score += 1
    if score <= 2:   return "Weak",   "#fc5c7d", score / 7
    if score <= 4:   return "Fair",   "#ffb347", score / 7
    if score <= 5:   return "Good",   "#61dafb", score / 7
    return             "Strong", "#4ecca3", score / 7


class GeneratorDialog(tk.Toplevel):
    """Standalone password generator — callable from header or entry dialog."""
    def __init__(self, master, on_use=None):
        super().__init__(master)
        self.wm_attributes("-alpha", 0)
        self.on_use = on_use
        self.title("Password Generator")
        self.configure(bg=SURFACE)
        self.resizable(False, False)
        self.grab_set()
        try:
            _ico = getattr(master.winfo_toplevel(), "_ico_path", None)
            if _ico:
                self.iconbitmap(_ico)
        except Exception:
            pass
        w, h = 500, 480
        _centre_on_parent(self, master, w, h)
        self._build()
        self._generate()
        self.update()
        _apply_dwm_to_widget(self)
        self.wm_attributes("-alpha", 1)

    def _build(self):
        pad = tk.Frame(self, bg=SURFACE, padx=30, pady=24)
        pad.pack(fill="both", expand=True)

        tk.Label(pad, text="⚙️  Password Generator", font=FNT_HEAD,
                 fg=TEXT, bg=SURFACE).pack(anchor="w", pady=(0, 20))

        # Generated password display
        pw_frame = tk.Frame(pad, bg=SURFACE2,
                            highlightbackground=BORDER, highlightthickness=1)
        pw_frame.pack(fill="x", pady=(0, 6))
        self.v_pw = tk.StringVar()
        self.pw_lbl = tk.Entry(pw_frame, textvariable=self.v_pw,
                               font=("Courier New", 13, "bold"),
                               bg=SURFACE2, fg=GREEN,
                               insertbackground=GREEN, relief="flat",
                               justify="center", state="readonly")
        self.pw_lbl.pack(fill="x", ipady=14, padx=10)

        # Strength bar
        self.str_lbl = tk.Label(pad, text="", font=FNT_SM,
                                fg=MUTED, bg=SURFACE)
        self.str_lbl.pack(anchor="w")
        bar_bg = tk.Frame(pad, bg=SURFACE2, height=6)
        bar_bg.pack(fill="x", pady=(2, 16))
        bar_bg.pack_propagate(False)
        self.str_bar = tk.Frame(bar_bg, bg=ACCENT, height=6)
        self.str_bar.place(x=0, y=0, relheight=1, relwidth=0)

        tk.Frame(pad, bg=BORDER, height=1).pack(fill="x", pady=(0, 14))

        # Length slider
        tk.Label(pad, text="LENGTH", font=FNT_SM,
                 fg=MUTED, bg=SURFACE).pack(anchor="w")
        len_row = tk.Frame(pad, bg=SURFACE)
        len_row.pack(fill="x", pady=(4, 14))
        self.v_len = tk.IntVar(value=16)
        self.len_lbl = tk.Label(len_row, text="16",
                                font=("Courier New", 12, "bold"),
                                fg=ACCENT, bg=SURFACE, width=3)
        self.len_lbl.pack(side="right")
        slider = tk.Scale(len_row, from_=8, to=48,
                          orient="horizontal", variable=self.v_len,
                          bg=SURFACE, fg=TEXT, troughcolor=SURFACE2,
                          activebackground=ACCENT, highlightthickness=0,
                          showvalue=False, relief="flat",
                          command=self._on_len)
        slider.pack(side="left", fill="x", expand=True)

        tk.Frame(pad, bg=BORDER, height=1).pack(fill="x", pady=(0, 14))

        # Character options
        tk.Label(pad, text="INCLUDE", font=FNT_SM,
                 fg=MUTED, bg=SURFACE).pack(anchor="w", pady=(0, 8))

        self.v_upper   = tk.BooleanVar(value=True)
        self.v_lower   = tk.BooleanVar(value=True)
        self.v_digits  = tk.BooleanVar(value=True)
        self.v_symbols = tk.BooleanVar(value=True)

        opts = [
            ("A-Z  Uppercase",  self.v_upper),
            ("a-z  Lowercase",  self.v_lower),
            ("0-9  Numbers",    self.v_digits),
            ("!@#  Symbols",    self.v_symbols),
        ]
        opt_grid = tk.Frame(pad, bg=SURFACE)
        opt_grid.pack(fill="x", pady=(0, 16))
        for i, (label, var) in enumerate(opts):
            r, c = divmod(i, 2)
            cb = tk.Checkbutton(opt_grid, text=label, variable=var,
                                font=FNT_SM, bg=SURFACE, fg=TEXT,
                                selectcolor=SURFACE2, activebackground=SURFACE,
                                activeforeground=TEXT, relief="flat",
                                cursor="hand2",
                                command=self._generate)
            cb.grid(row=r, column=c, sticky="w", padx=(0, 20), pady=3)

        tk.Frame(pad, bg=BORDER, height=1).pack(fill="x", pady=(0, 14))

        # Buttons
        btn_row = tk.Frame(pad, bg=SURFACE)
        btn_row.pack(fill="x")
        mk_btn(btn_row, "🔄 Regenerate", self._generate,
               bg=SURFACE2, fg=TEXT, w=14).pack(side="left")
        mk_btn(btn_row, "📋 Copy", self._copy,
               bg=SURFACE2, fg=TEXT, w=10).pack(side="left", padx=(8, 0))
        if self.on_use:
            mk_btn(btn_row, "Use Password", self._use,
                   w=16).pack(side="right")
        else:
            mk_btn(btn_row, "Close", self.destroy,
                   bg=SURFACE2, fg=MUTED, w=10).pack(side="right")

    def _on_len(self, val):
        self.len_lbl.config(text=str(val))
        self._generate()

    def _generate(self):
        pw = generate_password(
            length=self.v_len.get(),
            upper=self.v_upper.get(),
            lower=self.v_lower.get(),
            digits=self.v_digits.get(),
            symbols=self.v_symbols.get()
        )
        self.v_pw.set(pw)
        self._update_strength(pw)

    def _update_strength(self, pw):
        label, color, ratio = password_strength(pw)
        self.str_lbl.config(text=f"Strength: {label}", fg=color)
        self.str_bar.place(relwidth=ratio)
        self.str_bar.config(bg=color)

    def _copy(self):
        pw = self.v_pw.get()
        if CLIPBOARD_OK:
            pyperclip.copy(pw)
        else:
            self.clipboard_clear()
            self.clipboard_append(pw)
        self.str_lbl.config(text="✅  Copied to clipboard!", fg=GREEN)
        self.after(1500, lambda: self._update_strength(self.v_pw.get()))

    def _use(self):
        if self.on_use:
            self.on_use(self.v_pw.get())
        self.destroy()


# ══════════════════════════════════════════════════════════════════════════════
# Add / Edit Dialog
# ══════════════════════════════════════════════════════════════════════════════
class EntryDialog(tk.Toplevel):
    def __init__(self, master, on_save, entry=None):
        super().__init__(master)
        self.wm_attributes("-alpha", 0)
        self.on_save = on_save
        self.entry   = entry
        self.title("Edit Entry" if entry else "New Entry")
        self.configure(bg=SURFACE)
        self.resizable(True, True)
        self.grab_set()
        try:
            _ico = getattr(master.winfo_toplevel(), "_ico_path", None)
            if _ico:
                self.iconbitmap(_ico)
        except Exception:
            pass
        w, h = 460, 580
        _centre_on_parent(self, master, w, h)
        self.minsize(420, 460)
        self._build()
        self.update()
        _apply_dwm_to_widget(self)
        self.wm_attributes("-alpha", 1)

    def _lbl(self, parent, text, ret=False):
        lbl = tk.Label(parent, text=text, font=FNT_SM, fg=MUTED, bg=SURFACE)
        lbl.pack(anchor="w")
        if ret:
            return lbl

    def _build(self):
        # Scrollable canvas so all fields are always reachable regardless of window height
        canvas = tk.Canvas(self, bg=SURFACE, highlightthickness=0)
        sb = ttk.Scrollbar(self, orient="vertical", command=canvas.yview,
                           style="Dark.Vertical.TScrollbar")
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        pad = tk.Frame(canvas, bg=SURFACE, padx=30, pady=24)
        win_id = canvas.create_window((0, 0), window=pad, anchor="nw")

        def _on_frame_configure(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
        def _on_canvas_configure(e):
            canvas.itemconfig(win_id, width=e.width)
        pad.bind("<Configure>", _on_frame_configure)
        canvas.bind("<Configure>", _on_canvas_configure)

        # Mouse wheel scrolling
        def _on_mousewheel(e):
            canvas.yview_scroll(int(-1*(e.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        self.bind("<Destroy>", lambda e: canvas.unbind_all("<MouseWheel>"))

        tk.Label(pad, text="✏️  Edit Entry" if self.entry else "🗝️  New Entry",
                 font=FNT_HEAD, fg=TEXT, bg=SURFACE).pack(anchor="w", pady=(0,18))

        g = self.entry or {}
        self.v_name  = tk.StringVar(value=g.get("name",""))
        self.v_user  = tk.StringVar(value=g.get("user",""))
        self.v_pass  = tk.StringVar(value=g.get("password",""))
        self.v_url   = tk.StringVar(value=g.get("url",""))
        self.v_notes = tk.StringVar(value=g.get("notes",""))
        self.v_cat   = tk.StringVar(value=g.get("category","Work"))
        self.v_host      = tk.StringVar(value=g.get("host",""))
        self.v_port      = tk.StringVar(value=g.get("port","3389"))
        self.v_workspace = tk.StringVar(value=g.get("workspace",""))

        self._lbl(pad, "SERVICE / APP NAME")
        mk_entry(pad, self.v_name, w=38).pack(fill="x", ipady=9, pady=(4,14))

        self._lbl(pad, "USERNAME / EMAIL")
        mk_entry(pad, self.v_user, w=38).pack(fill="x", ipady=9, pady=(4,14))

        self._lbl(pad, "PASSWORD")
        pw_row = tk.Frame(pad, bg=SURFACE)
        pw_row.pack(fill="x", pady=(4, 4))
        self.pw_entry = mk_entry(pw_row, self.v_pass, show="●", mono=True, w=26)
        self.pw_entry.pack(side="left", fill="x", expand=True, ipady=9)
        self.pw_entry.bind("<KeyRelease>", lambda e: self._update_pw_strength())
        self.show_pw = False
        tk.Button(pw_row, text="👁", font=FNT_SM, bg=SURFACE2, fg=MUTED,
                  relief="flat", cursor="hand2", bd=0,
                  command=self._toggle_pw).pack(side="left", padx=(6,0), ipady=9, ipadx=6)
        tk.Button(pw_row, text="⚙️ Generate", font=FNT_SM, bg=ACCENT, fg="white",
                  relief="flat", cursor="hand2", bd=0, padx=8,
                  command=self._open_generator).pack(side="left", padx=(6,0), ipady=9)

        # Strength bar under password
        str_row = tk.Frame(pad, bg=SURFACE)
        str_row.pack(fill="x", pady=(2, 10))
        self.str_lbl = tk.Label(str_row, text="", font=FNT_SM,
                                fg=MUTED, bg=SURFACE)
        self.str_lbl.pack(side="left")
        bar_bg = tk.Frame(str_row, bg=SURFACE2, height=5, width=160)
        bar_bg.pack(side="right")
        bar_bg.pack_propagate(False)
        self.str_bar = tk.Frame(bar_bg, bg=ACCENT, height=5)
        self.str_bar.place(x=0, y=0, relheight=1, relwidth=0)
        self._update_pw_strength()

        # Single container that always sits between password and category.
        # We show either the URL section or the server section inside it —
        # the container itself never moves, so layout order is always correct.
        conn = tk.Frame(pad, bg=SURFACE)
        conn.pack(fill="x")

        # ── URL section (non-server entries) ─────────────────────────────
        self._url_frame = tk.Frame(conn, bg=SURFACE)
        self._url_lbl   = tk.Label(self._url_frame, text="URL (optional)",
                                   font=FNT_SM, fg=MUTED, bg=SURFACE)
        self._url_lbl.pack(anchor="w")
        self._url_ent   = mk_entry(self._url_frame, self.v_url, w=38)
        self._url_ent.pack(fill="x", ipady=9, pady=(4,14))

        # ── Server section (Server category only) ────────────────────────
        self._srv_frame = tk.Frame(conn, bg=SURFACE)

        tk.Label(self._srv_frame, text="HOST / IP ADDRESS",
                 font=FNT_SM, fg=MUTED, bg=SURFACE).pack(anchor="w")
        self._host_ent = mk_entry(self._srv_frame, self.v_host, w=38)
        self._host_ent.pack(fill="x", ipady=9, pady=(4,6))

        port_row = tk.Frame(self._srv_frame, bg=SURFACE)
        port_row.pack(fill="x", pady=(0,14))
        tk.Label(port_row, text="PORT", font=FNT_SM,
                 fg=MUTED, bg=SURFACE).pack(side="left", anchor="w")
        mk_entry(port_row, self.v_port, w=8).pack(side="left", ipady=9, padx=(8,0))

        tk.Label(self._srv_frame, text="AVD WORKSPACE URL (optional)",
                 font=FNT_SM, fg=MUTED, bg=SURFACE).pack(anchor="w")
        self._ws_ent = mk_entry(self._srv_frame, self.v_workspace, w=38)
        self._ws_ent.pack(fill="x", ipady=9, pady=(4,2))
        tk.Label(self._srv_frame,
                 text="Leave blank for standard RDP. Add workspace URL for Azure Virtual Desktop.",
                 font=FNT_SM, fg=MUTED, bg=SURFACE,
                 wraplength=380, justify="left").pack(anchor="w", pady=(0,12))

        self._lbl(pad, "CATEGORY")
        cat_f = tk.Frame(pad, bg=SURFACE)
        cat_f.pack(anchor="w", fill="x", pady=(4,16))
        # Split into two rows of 4 to avoid clipping
        row1 = tk.Frame(cat_f, bg=SURFACE)
        row1.pack(anchor="w", pady=(0,4))
        row2 = tk.Frame(cat_f, bg=SURFACE)
        row2.pack(anchor="w")
        for i, cat in enumerate(CATEGORIES):
            c, _ = CAT_COLORS[cat]
            parent = row1 if i < 4 else row2
            tk.Radiobutton(parent, text=f"{CAT_EMOJI[cat]} {cat}",
                           variable=self.v_cat, value=cat,
                           bg=SURFACE, fg=c, selectcolor=SURFACE2,
                           activebackground=SURFACE, activeforeground=c,
                           font=FNT_SM, relief="flat",
                           cursor="hand2",
                           command=self._on_cat_change).pack(side="left", padx=(0,10))

        self._on_cat_change()  # set initial visibility

        btn_row = tk.Frame(pad, bg=SURFACE)
        btn_row.pack(fill="x", pady=(6,0))
        mk_btn(btn_row, "Cancel", self.destroy,
               bg=SURFACE2, fg=MUTED, w=12).pack(side="left")
        mk_btn(btn_row, "Save Entry", self._save, w=16).pack(side="right")

    def _on_cat_change(self):
        """Show server fields for Server category, URL field for everything else."""
        is_server = self.v_cat.get() == "Server"
        if is_server:
            self._url_frame.pack_forget()
            self._srv_frame.pack(fill="x")
        else:
            self._srv_frame.pack_forget()
            self._url_frame.pack(fill="x")

    def _toggle_pw(self):
        self.show_pw = not self.show_pw
        self.pw_entry.config(show="" if self.show_pw else "●")

    def _open_generator(self):
        def use_password(pw):
            self.v_pass.set(pw)
            self._update_pw_strength()
        GeneratorDialog(self, on_use=use_password)

    def _update_pw_strength(self):
        pw = self.v_pass.get()
        if not pw:
            self.str_lbl.config(text="")
            self.str_bar.place(relwidth=0)
            return
        label, color, ratio = password_strength(pw)
        self.str_lbl.config(text=f"Strength: {label}", fg=color)
        self.str_bar.place(relwidth=ratio)
        self.str_bar.config(bg=color)

    def _save(self):
        n = self.v_name.get().strip()
        u = self.v_user.get().strip()
        p = self.v_pass.get()
        if not n or not u or not p:
            messagebox.showwarning("Missing Fields",
                                   "Name, Username, and Password are required.",
                                   parent=self.winfo_toplevel())
            return
        # Stamp updated_at only if password changed (or new entry)
        existing_pw = (self.entry or {}).get("password", "")
        now_ts = datetime.datetime.now().isoformat(timespec="seconds")
        updated_at = now_ts if (p != existing_pw or not self.entry) else self.entry.get("updated_at", now_ts)
        self.on_save({"name": n, "user": u, "password": p,
                      "url": self.v_url.get().strip(),
                      "notes": self.v_notes.get().strip(),
                      "category": self.v_cat.get(),
                      "host": self.v_host.get().strip(),
                      "port": self.v_port.get().strip() or "3389",
                      "workspace": self.v_workspace.get().strip(),
                      "updated_at": updated_at,
                      "favourite": (self.entry or {}).get("favourite", False)})
        self.destroy()


# ══════════════════════════════════════════════════════════════════════════════
# Main Vault UI
# ══════════════════════════════════════════════════════════════════════════════
class VaultApp(tk.Frame):
    def __init__(self, master, key, on_lock):
        super().__init__(master, bg=BG)
        self.key     = key
        self.on_lock = on_lock
        self.vault   = []
        self.pw_visible = {}
        self._load_vault()
        self.pack(fill="both", expand=True)
        self._build_ui()
        self._render()
        self._auto_lock_job   = None
        self._AUTO_LOCK_SECS  = 300   # 5 minutes
        self._reset_auto_lock()
        # Bind mouse/keyboard activity to reset the auto-lock timer
        self.winfo_toplevel().bind_all("<Motion>",   lambda e: self._reset_auto_lock())
        self.winfo_toplevel().bind_all("<KeyPress>",  lambda e: self._reset_auto_lock())
        # Check for updates in background
        check_for_update(self._on_update_found)

    def _load_vault(self):
        if not os.path.exists(VAULT_FILE):
            return
        with open(VAULT_FILE, "rb") as f:
            raw = f.read()
        self.vault = json.loads(decrypt_data(self.key, raw))
        # Backfill missing updated_at for existing entries
        now_ts = datetime.datetime.now().isoformat(timespec="seconds")
        changed = False
        for entry in self.vault:
            if not entry.get("updated_at"):
                entry["updated_at"] = now_ts
                changed = True
        if changed:
            self._save_vault()

    def _save_vault(self):
        raw = encrypt_data(self.key, json.dumps(self.vault))
        with open(VAULT_FILE, "wb") as f:
            f.write(raw)

    def _build_ui(self):
        # Header
        hdr = tk.Frame(self, bg=SURFACE, pady=12,
                       highlightbackground=BORDER, highlightthickness=1)
        hdr.pack(fill="x")
        left = tk.Frame(hdr, bg=SURFACE)
        left.pack(side="left", padx=20)
        tk.Label(left, text="MARAi", font=("Segoe UI",15,"bold"),
                 fg=ACCENT, bg=SURFACE).pack(side="left")
        tk.Label(left, text=f"v{VERSION}", font=("Courier New",9),
                 fg=MUTED, bg=SURFACE).pack(side="left", padx=(8,0), pady=(4,0))
        right = tk.Frame(hdr, bg=SURFACE)
        right.pack(side="right", padx=20)
        self.count_lbl = tk.Label(right, text="", font=FNT_SM, fg=MUTED, bg=SURFACE)
        self.count_lbl.pack(side="left", padx=(0,10))
        self.lock_timer_lbl = tk.Label(right, text="", font=FNT_SM, fg=MUTED, bg=SURFACE)
        self.lock_timer_lbl.pack(side="left", padx=(0,10))
        self._update_lock_timer_display()
        mk_btn(right, "+ Add Entry", self._add_entry, w=12).pack(side="left", padx=(0,8))
        mk_btn(right, "⚙️ Generate", self._open_generator, bg=SURFACE2, fg=TEXT, w=12).pack(side="left", padx=(0,4))
        mk_btn(right, "🔑", self._change_password, bg=SURFACE2, fg=MUTED, w=3,
               tooltip="Change Master Password").pack(side="left", padx=(0,4))
        mk_btn(right, "📂", self._change_vault_location, bg=SURFACE2, fg=MUTED, w=3,
               tooltip="Change Vault Location").pack(side="left", padx=(0,4))
        mk_btn(right, "ℹ", self._show_about, bg=SURFACE2, fg=MUTED, w=3,
               tooltip="About MARAi").pack(side="left", padx=(0,4))
        mk_btn(right, "🔒", self.on_lock, bg=SURFACE2, fg=MUTED, w=3,
               tooltip="Lock Vault").pack(side="left")

        # Update banner (hidden until update found)
        self._update_banner = tk.Frame(self, bg="#1a2a10",
                                       highlightbackground="#4ecca3",
                                       highlightthickness=1)
        self._update_lbl = tk.Label(self._update_banner,
                                    text="", font=FNT_SM,
                                    fg="#4ecca3", bg="#1a2a10")
        self._update_lbl.pack(side="left", padx=16, pady=8)
        self._update_btn = tk.Button(self._update_banner,
                                     text="Download",
                                     font=("Segoe UI", 9, "bold"),
                                     bg="#4ecca3", fg="#0a0a0a",
                                     relief="flat", cursor="hand2",
                                     padx=10, pady=4,
                                     command=lambda: webbrowser.open(RELEASES_URL))
        self._update_btn.pack(side="right", padx=16, pady=6)
        tk.Button(self._update_banner, text="✕",
                  font=FNT_SM, bg="#1a2a10", fg="#4ecca3",
                  relief="flat", cursor="hand2", bd=0,
                  command=self._dismiss_update_banner).pack(side="right", padx=(0,4))

        # Search
        sf = tk.Frame(self, bg=BG)
        sf.pack(fill="x", padx=20, pady=(12,6))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._render())
        wrap = tk.Frame(sf, bg=SURFACE2, highlightbackground=BORDER, highlightthickness=1)
        wrap.pack(fill="x")
        tk.Label(wrap, text="🔍", font=FNT_BODY, bg=SURFACE2, fg=MUTED).pack(
            side="left", padx=(10,4))
        tk.Entry(wrap, textvariable=self.search_var, font=FNT_BODY,
                 bg=SURFACE2, fg=TEXT, insertbackground=TEXT,
                 relief="flat").pack(side="left", fill="x", expand=True, ipady=9)

        # Category filter bar
        self.active_filter = tk.StringVar(value="All")
        ff = tk.Frame(self, bg=BG)
        ff.pack(fill="x", padx=20, pady=(0,10))
        self._filter_btns = {}
        for cat in ["All"] + list(CATEGORIES):
            label = cat if cat == "All" else f"{CAT_EMOJI.get(cat,'')} {cat}"
            btn = tk.Button(ff, text=label,
                            font=("Segoe UI", 9),
                            relief="flat", cursor="hand2",
                            bd=0, padx=10, pady=4)
            btn.pack(side="left", padx=(0,4))
            self._filter_btns[cat] = btn
            btn.config(command=lambda c=cat: self._set_filter(c))
        self._update_filter_btns()

        # Scrollable area
        outer = tk.Frame(self, bg=BG)
        outer.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(outer, bg=BG, highlightthickness=0)
        sb = mk_scrollbar(outer, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.cards_frame = tk.Frame(self.canvas, bg=BG)
        self._cw = self.canvas.create_window((0,0), window=self.cards_frame, anchor="nw")
        self._resize_job = None
        self._last_canvas_width = 0
        self.cards_frame.bind("<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", self._on_canvas_resize)
        self.canvas.bind_all("<MouseWheel>",
            lambda e: self.canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

    def _set_filter(self, cat):
        self.active_filter.set(cat)
        self._update_filter_btns()
        self._render()

    def _update_filter_btns(self):
        active = self.active_filter.get()
        for cat, btn in self._filter_btns.items():
            if cat == active:
                btn.config(bg=ACCENT, fg="white")
            else:
                fg_c = CAT_COLORS.get(cat, (MUTED, SURFACE2))[0] if cat != "All" else MUTED
                btn.config(bg=SURFACE2, fg=fg_c)

    def _on_canvas_resize(self, event):
        self.canvas.itemconfig(self._cw, width=event.width)
        if event.width != self._last_canvas_width:
            self._last_canvas_width = event.width
            if self._resize_job:
                self.after_cancel(self._resize_job)
            self._resize_job = self.after(120, self._render)

    def _render(self):
        for w in self.cards_frame.winfo_children():
            w.destroy()
        self.pw_visible.clear()

        q      = self.search_var.get().lower()
        fcat   = self.active_filter.get()

        def _matches(e):
            # Category filter
            if fcat != "All" and e.get("category","Other") != fcat:
                return False
            # Search all fields
            if not q:
                return True
            return (q in e.get("name","").lower()
                    or q in e.get("user","").lower()
                    or q in e.get("category","").lower()
                    or q in e.get("url","").lower()
                    or q in e.get("host","").lower()
                    or q in e.get("notes","").lower()
                    or q in e.get("workspace","").lower())

        filtered = [e for e in self.vault if _matches(e)]

        # Favourites always appear first
        filtered.sort(key=lambda e: (not e.get("favourite", False),))

        n = len(self.vault)
        self.count_lbl.config(text=f"{n} entr{'y' if n==1 else 'ies'}")

        if not filtered:
            msg = ("No results found." if q
                   else "Your vault is empty.\nClick '+ Add Entry' to store your first password.")
            tk.Label(self.cards_frame, text=msg, font=FNT_BODY,
                     fg=MUTED, bg=BG, justify="center").pack(pady=80)
            return

        # Responsive columns — 1 column below 640px, 2 above
        cw   = self.canvas.winfo_width()
        cols = 1 if cw < 640 else 2

        for c in range(2):
            self.cards_frame.grid_columnconfigure(
                c, weight=1 if c < cols else 0,
                uniform="col" if c < cols else "")

        CARD_H   = 220   # consistent card height
        num_rows = (len(filtered) + cols - 1) // cols
        for r in range(num_rows):
            self.cards_frame.grid_rowconfigure(r, weight=0, minsize=CARD_H)

        for i, entry in enumerate(filtered):
            real_idx = self.vault.index(entry)
            row, col  = divmod(i, cols)
            cell = tk.Frame(self.cards_frame, bg=BG)
            cell.grid(row=row, column=col, sticky="nsew", padx=10, pady=8)
            cell.grid_rowconfigure(0, weight=1)
            cell.grid_columnconfigure(0, weight=1)
            self._make_card(cell, entry, real_idx)

    def _bind_mousewheel(self, widget):
        pass  # canvas.bind_all in _build_ui already handles this globally

    def _make_card(self, parent, entry, idx):
        cat      = entry.get("category", "Other")
        fg_c, bg_c = CAT_COLORS.get(cat, (MUTED, SURFACE2))
        is_fav   = entry.get("favourite", False)

        # ── Card frame ────────────────────────────────────────────────────
        card = tk.Frame(parent, bg=SURFACE,
                        highlightbackground=CARD_BORDER, highlightthickness=1)
        card.grid(row=0, column=0, sticky="nsew")

        # Hover effect
        def _on_enter(e, c=card):
            c.config(highlightbackground=ACCENT)
        def _on_leave(e, c=card):
            c.config(highlightbackground=CARD_BORDER)
        card.bind("<Enter>", _on_enter)
        card.bind("<Leave>", _on_leave)

        # Left colour accent stripe
        tk.Frame(card, bg=fg_c, width=4).pack(side="left", fill="y")

        inner = tk.Frame(card, bg=SURFACE, padx=14, pady=12)
        inner.pack(side="left", fill="both", expand=True)

        # ── Header row ────────────────────────────────────────────────────
        hdr = tk.Frame(inner, bg=SURFACE)
        hdr.pack(fill="x")

        # Emoji badge
        badge = tk.Label(hdr, text=CAT_EMOJI.get(cat,"📁"),
                         font=("Segoe UI", 16),
                         bg=bg_c, fg=fg_c, padx=6, pady=2,
                         relief="flat")
        badge.pack(side="left")

        info = tk.Frame(hdr, bg=SURFACE)
        info.pack(side="left", padx=(10,0), fill="x", expand=True)

        tk.Label(info, text=entry.get("name",""),
                 font=FNT_HEAD, fg=TEXT, bg=SURFACE,
                 anchor="w").pack(anchor="w")
        tk.Label(info, text=cat,
                 font=FNT_SM, fg=fg_c, bg=SURFACE).pack(anchor="w")

        # Action buttons
        acts = tk.Frame(hdr, bg=SURFACE)
        acts.pack(side="right", padx=(4,0))

        is_fav = entry.get("favourite", False)
        star_btn = tk.Button(acts,
                             text="★" if is_fav else "☆",
                             font=("Segoe UI", 12),
                             bg=SURFACE, fg="#f5c518" if is_fav else MUTED,
                             relief="flat", cursor="hand2", bd=0, padx=3)
        star_btn.pack(side="left")

        def _toggle_fav(i=idx, btn=star_btn):
            self.vault[i]["favourite"] = not self.vault[i].get("favourite", False)
            self._save_vault()
            self._render()
        star_btn.config(command=_toggle_fav)

        edit_btn = tk.Button(acts, text="✏️", font=FNT_SM,
                             bg=SURFACE, fg=MUTED,
                             relief="flat", cursor="hand2", bd=0, padx=4,
                             command=lambda i=idx: self._edit(i))
        edit_btn.pack(side="left", padx=(2,0))

        del_btn = tk.Button(acts, text="🗑", font=FNT_SM,
                            bg=SURFACE, fg=RED,
                            relief="flat", cursor="hand2", bd=0, padx=4,
                            command=lambda i=idx: self._delete(i))
        del_btn.pack(side="left", padx=(2,0))

        # ── Divider ───────────────────────────────────────────────────────
        tk.Frame(inner, bg=BORDER, height=1).pack(fill="x", pady=(10,8))

        # ── Fields ───────────────────────────────────────────────────────
        self._field(inner, "User", entry.get("user",""),     idx, masked=False)
        self._field(inner, "Pass", entry.get("password",""), idx, masked=True)

        if cat == "Server":
            host      = entry.get("host","")
            port      = entry.get("port","3389")
            workspace = entry.get("workspace","").strip()
            is_avd    = bool(workspace)
            if host:
                self._field(inner, "Host",
                            f"{host}:{port}" if port != "3389" else host,
                            idx, masked=False)
            if is_avd:
                ws_display = workspace if len(workspace) <= 48 else workspace[:45] + "..."
                tk.Label(inner, text=f"☁  AVD  •  {ws_display}",
                         font=FNT_SM, fg="#60d0a0", bg=SURFACE,
                         anchor="w", wraplength=340).pack(anchor="w", pady=(4,0))
            btn_label = "▶  Connect via AVD" if is_avd else "▶  Connect via RDP"
            mk_btn(inner, btn_label,
                   lambda i=idx: self._rdp_connect(i),
                   bg="#1a5c3a", fg="#60d0a0", w=22
                   ).pack(anchor="w", pady=(8,2))
        else:
            if entry.get("url"):
                url_val = entry["url"]
                self._field(inner, "URL", url_val, idx, masked=False)
                # Launch URL button
                pw_val = entry.get("password","")
                def _open_url(u=url_val, pw=pw_val):
                    if not u.startswith(("http://","https://")):
                        u = "https://" + u
                    self._copy_secure(pw)
                    webbrowser.open(u)
                url_btn = mk_btn(inner, "🌐  Open URL",
                                 _open_url, bg=SURFACE2, fg=ACCENT, w=14)
                url_btn.pack(anchor="w", pady=(4,0))
                # Show "Copied!" feedback on the button briefly
                orig_cmd = url_btn.cget("command")
                def _open_url_with_feedback(b=url_btn, u=url_val, pw=pw_val):
                    if not u.startswith(("http://","https://")):
                        u = "https://" + u
                    self._copy_secure(pw)
                    webbrowser.open(u)
                    b.config(text="✓  Password Copied", fg=GREEN)
                    self.after(2000, lambda: b.config(text="🌐  Open URL", fg=ACCENT))
                url_btn.config(command=_open_url_with_feedback)

        if entry.get("notes"):
            tk.Label(inner, text=f"📝  {entry['notes']}",
                     font=FNT_SM, fg=MUTED, bg=SURFACE,
                     anchor="w", wraplength=320).pack(anchor="w", pady=(6,0))

        # ── Password age ──────────────────────────────────────────────────
        age_text, age_colour = _password_age(entry)
        tk.Label(inner, text=age_text, font=FNT_SM,
                 fg=age_colour, bg=SURFACE, anchor="w").pack(anchor="w", pady=(6,0))

    def _field(self, parent, label, value, idx, masked):
        row = tk.Frame(parent, bg=SURFACE2,
                       highlightbackground=BORDER, highlightthickness=1)
        row.pack(fill="x", pady=2)
        tk.Label(row, text=label, font=("Segoe UI", 8), fg=MUTED,
                 bg=SURFACE2, width=5, anchor="w").pack(side="left", padx=(10,6))
        key = f"{label}_{idx}"
        display = "● ● ● ● ● ●" if masked else value
        lbl = tk.Label(row, text=display, font=FNT_MONO,
                       fg=TEXT, bg=SURFACE2, anchor="w")
        lbl.pack(side="left", fill="x", expand=True, ipady=6)

        if masked:
            self.pw_visible[key] = False
            def toggle(l=lbl, v=value, k=key):
                self.pw_visible[k] = not self.pw_visible[k]
                l.config(text=v if self.pw_visible[k] else "● ● ● ● ● ●")
            tk.Button(row, text="👁", font=FNT_SM, bg=SURFACE2, fg=MUTED,
                      relief="flat", cursor="hand2", bd=0, padx=4,
                      command=toggle).pack(side="right", padx=2)

        tk.Button(row, text="📋", font=FNT_SM, bg=SURFACE2, fg=MUTED,
                  relief="flat", cursor="hand2", bd=0, padx=4,
                  command=lambda v=value, r=row: self._copy(v, r)
                  ).pack(side="right", padx=2)

    def _copy(self, value, row):
        self._copy_secure(value)
        orig = SURFACE2
        widgets = [row] + list(row.winfo_children())
        for w in widgets:
            try: w.config(bg="#0e3028")
            except: pass
        self.after(500, lambda: [w.config(bg=orig)
                                 for w in widgets if w.winfo_exists()])

    def _copy_secure(self, value):
        """
        Copy to clipboard bypassing Windows clipboard history (Win+V).
        Uses ExcludeClipboardContentFromMonitorProcessing flag via ctypes.
        Falls back to normal copy on non-Windows or if API call fails.
        """
        copied = False
        if sys.platform == "win32":
            try:
                u32      = ctypes.windll.user32
                kernel32 = ctypes.windll.kernel32

                # Register the special format that tells Windows to skip history
                CF_EXCLUDE     = u32.RegisterClipboardFormatW(
                    "ExcludeClipboardContentFromMonitorProcessing")
                CF_UNICODETEXT = 13
                GMEM_MOVEABLE  = 0x0002

                # Encode text as null-terminated UTF-16-LE
                encoded  = (value + "\0").encode("utf-16-le")
                h_mem    = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(encoded))
                if h_mem:
                    p_mem = kernel32.GlobalLock(h_mem)
                    if p_mem:
                        ctypes.memmove(p_mem, encoded, len(encoded))
                        kernel32.GlobalUnlock(h_mem)
                        if u32.OpenClipboard(0):
                            u32.EmptyClipboard()
                            u32.SetClipboardData(CF_UNICODETEXT, h_mem)
                            u32.SetClipboardData(CF_EXCLUDE, None)
                            u32.CloseClipboard()
                            copied = True
            except Exception:
                pass

        if not copied:
            # Fallback for non-Windows or if ctypes call failed
            if CLIPBOARD_OK:
                pyperclip.copy(value)
            else:
                self.winfo_toplevel().clipboard_clear()
                self.winfo_toplevel().clipboard_append(value)

    def _on_update_found(self, new_version):
        """Called from background thread — use after() to safely update UI."""
        self.after(0, lambda: self._show_update_banner(new_version))

    def _show_update_banner(self, new_version):
        self._update_lbl.config(
            text=f"🎉  MARAi v{new_version} is available!  You are on v{VERSION}.")
        self._update_banner.pack(fill="x", after=self.winfo_children()[0])

    def _dismiss_update_banner(self):
        self._update_banner.pack_forget()

    def _reset_auto_lock(self):
        if self._auto_lock_job:
            self.after_cancel(self._auto_lock_job)
        self._auto_lock_job = self.after(
            self._AUTO_LOCK_SECS * 1000,
            self._auto_lock_trigger)
        self._lock_start = self.winfo_toplevel().tk.call("clock", "seconds")
        self._update_lock_timer_display()

    def _update_lock_timer_display(self):
        try:
            now     = int(self.winfo_toplevel().tk.call("clock", "seconds"))
            elapsed = now - int(self._lock_start) if hasattr(self, "_lock_start") else 0
            remain  = max(0, self._AUTO_LOCK_SECS - elapsed)
            mins, secs = divmod(remain, 60)
            self.lock_timer_lbl.config(text=f"🔒 {mins}:{secs:02d}")
            self.after(1000, self._update_lock_timer_display)
        except Exception:
            pass

    def _auto_lock_trigger(self):
        # Clear decrypted vault from memory before locking
        self.vault = []
        self.key   = None
        self.on_lock()


    def _open_generator(self):
        GeneratorDialog(self.winfo_toplevel())

    def _change_password(self):
        win = tk.Toplevel(self.winfo_toplevel())
        win.wm_attributes("-alpha", 0)
        win.title("Change Master Password")
        win.configure(bg=SURFACE)
        win.resizable(False, False)
        win.grab_set()
        try:
            _ico = getattr(self.winfo_toplevel(), "_ico_path", None)
            if _ico:
                win.iconbitmap(_ico)
        except Exception:
            pass
        w, h = 420, 460
        _centre_on_parent(win, self.winfo_toplevel(), w, h)

        pad = tk.Frame(win, bg=SURFACE, padx=30, pady=28)
        pad.pack(fill="both", expand=True)

        tk.Label(pad, text="🔑  Change Master Password", font=FNT_HEAD,
                 fg=TEXT, bg=SURFACE).pack(anchor="w", pady=(0, 20))

        # Current password
        tk.Label(pad, text="CURRENT PASSWORD", font=FNT_SM,
                 fg=MUTED, bg=SURFACE).pack(anchor="w")
        v_current = tk.StringVar()
        mk_entry(pad, v_current, show="●", mono=True, w=36).pack(
            fill="x", ipady=10, pady=(4, 14))

        # New password
        tk.Label(pad, text="NEW PASSWORD", font=FNT_SM,
                 fg=MUTED, bg=SURFACE).pack(anchor="w")
        v_new = tk.StringVar()
        mk_entry(pad, v_new, show="●", mono=True, w=36).pack(
            fill="x", ipady=10, pady=(4, 14))

        # Confirm new password
        tk.Label(pad, text="CONFIRM NEW PASSWORD", font=FNT_SM,
                 fg=MUTED, bg=SURFACE).pack(anchor="w")
        v_confirm = tk.StringVar()
        mk_entry(pad, v_confirm, show="●", mono=True, w=36).pack(
            fill="x", ipady=10, pady=(4, 0))

        # Error label
        err_lbl = tk.Label(pad, text="", font=FNT_SM, fg=RED, bg=SURFACE)
        err_lbl.pack(pady=(8, 0))

        # Success label
        ok_lbl = tk.Label(pad, text="", font=FNT_SM, fg=GREEN, bg=SURFACE)
        ok_lbl.pack()

        def do_change():
            current  = v_current.get()
            new_pw   = v_new.get()
            confirm  = v_confirm.get()
            err_lbl.config(text="")
            ok_lbl.config(text="")

            # Verify current password
            meta = load_meta()
            salt = base64.b64decode(meta["salt"])
            try:
                kdf_used = meta.get("kdf", "pbkdf2")
                test_key = derive_key(current, salt, kdf=kdf_used)
                verify   = base64.b64decode(meta["verify"])
                if decrypt_data(test_key, verify) not in ("MARAI_OK", "VAULTKEY_OK"):
                    raise ValueError
            except Exception:
                err_lbl.config(text="Current password is incorrect.")
                return

            if not new_pw:
                err_lbl.config(text="New password cannot be empty.")
                return
            if len(new_pw) < 6:
                err_lbl.config(text="New password must be at least 6 characters.")
                return
            if new_pw != confirm:
                err_lbl.config(text="New passwords do not match.")
                return
            if new_pw == current:
                err_lbl.config(text="New password must be different from current.")
                return

            # Re-encrypt vault with new Argon2id key
            new_salt = secrets.token_bytes(16)
            new_key  = derive_key(new_pw, new_salt, kdf="argon2id" if ARGON2_OK else "pbkdf2")

            # Save new meta with kdf field
            new_verify = encrypt_data(new_key, "MARAI_OK")
            save_meta(base64.b64encode(new_salt).decode(),
                      base64.b64encode(new_verify).decode(),
                      kdf="argon2id" if ARGON2_OK else "pbkdf2")

            # Re-encrypt vault data
            raw = encrypt_data(new_key, json.dumps(self.vault))
            with open(VAULT_FILE, "wb") as f:
                f.write(raw)

            # Update the live key in memory
            self.key = new_key

            ok_lbl.config(text="✅  Master password changed successfully!")
            err_lbl.config(text="")

            # Clear fields
            v_current.set("")
            v_new.set("")
            v_confirm.set("")

            # Auto close after 2 seconds
            win.after(2000, win.destroy)

        tk.Frame(pad, bg=SURFACE, height=4).pack()
        btn_row = tk.Frame(pad, bg=SURFACE)
        btn_row.pack(fill="x", pady=(8, 0))
        mk_btn(btn_row, "Cancel", win.destroy, bg=SURFACE2, fg=MUTED, w=12).pack(side="left")
        mk_btn(btn_row, "Change Password", do_change, w=18).pack(side="right")
        win.update()
        _apply_dwm_to_widget(win)
        win.wm_attributes("-alpha", 1)

    @staticmethod
    def _show_about_static(root):
        """Open the About dialog from outside the VaultApp instance (e.g. lock screen)."""
        # Temporarily create a minimal proxy to call _show_about logic
        win = tk.Toplevel(root)
        win.wm_attributes("-alpha", 0)
        win.title("About MARAi")
        win.configure(bg=SURFACE)
        win.resizable(False, False)
        win.grab_set()
        try:
            _ico = getattr(root, "_ico_path", None)
            if _ico:
                win.iconbitmap(_ico)
        except Exception:
            pass
        w, h = 520, 560
        _centre_on_parent(win, root, w, h)
        VaultApp._build_about_content(win, root)
        win.update()
        _apply_dwm_to_widget(win)
        win.wm_attributes("-alpha", 1)

    @staticmethod
    def _build_about_content(win, root):
        """Build About dialog content — shared between _show_about and _show_about_static."""
        hdr = tk.Frame(win, bg=SURFACE, padx=30, pady=20)
        hdr.pack(fill="x")
        ac = tk.Canvas(hdr, width=64, height=64, bg=SURFACE, highlightthickness=0)
        ac.pack()
        _draw_concentric_logo(ac, 32, 32, 32, SURFACE)
        tk.Label(hdr, text="M  A  R  A  i", font=("Segoe UI",18,"bold"),
                 fg=ACCENT, bg=SURFACE).pack()
        tk.Label(hdr, text=f"Version {VERSION}", font=FNT_SM,
                 fg=MUTED, bg=SURFACE).pack(pady=(2,0))

        tk.Frame(win, bg=BORDER, height=1).pack(fill="x", padx=30, pady=(12,0))

        tk.Label(win, text="What's New", font=("Segoe UI",10,"bold"),
                 fg=TEXT, bg=SURFACE).pack(anchor="w", padx=30, pady=(10,4))

        scroll_frame = tk.Frame(win, bg=SURFACE, height=160)
        scroll_frame.pack(fill="x", padx=30)
        scroll_frame.pack_propagate(False)

        cv = tk.Canvas(scroll_frame, bg=SURFACE, highlightthickness=0)
        sb = mk_scrollbar(scroll_frame, orient="vertical", command=cv.yview)
        inner = tk.Frame(cv, bg=SURFACE)
        inner.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.create_window((0, 0), window=inner, anchor="nw")
        cv.configure(yscrollcommand=sb.set)
        cv.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        for ver, note in CHANGELOG:
            row = tk.Frame(inner, bg=SURFACE)
            row.pack(fill="x", pady=3)
            tag_bg = ACCENT if ver == VERSION else SURFACE2
            tag_fg = "white" if ver == VERSION else MUTED
            tk.Label(row, text=f" v{ver} ", font=("Courier New",9,"bold"),
                     bg=tag_bg, fg=tag_fg, width=8).pack(side="left")
            tk.Label(row, text=note, font=FNT_SM,
                     fg=TEXT if ver == VERSION else MUTED,
                     bg=SURFACE, anchor="w", wraplength=340,
                     justify="left").pack(side="left", padx=(10,0), fill="x")

        tk.Frame(win, bg=BORDER, height=1).pack(fill="x", padx=30, pady=(12,0))
        ftr = tk.Frame(win, bg=SURFACE, padx=30, pady=14)
        ftr.pack(fill="x")
        tk.Label(ftr, text="Your data is stored in  ~/.marai/  on your machine.",
                 font=FNT_SM, fg=MUTED, bg=SURFACE).pack()
        gh_url = f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}"
        gh_lbl = tk.Label(ftr, text=gh_url, font=FNT_SM,
                           fg=ACCENT, bg=SURFACE, cursor="hand2")
        gh_lbl.pack(pady=(6,0))
        gh_lbl.bind("<Button-1>", lambda e: webbrowser.open(gh_url))
        gh_lbl.bind("<Enter>",    lambda e: gh_lbl.config(fg=GREEN))
        gh_lbl.bind("<Leave>",    lambda e: gh_lbl.config(fg=ACCENT))
        mk_btn(ftr, "Close", lambda: [win.grab_release(), win.destroy()],
               bg=SURFACE2, fg=MUTED, w=10).pack(pady=(14,0))

    def _show_about(self):
        win = tk.Toplevel(self.winfo_toplevel())
        win.wm_attributes("-alpha", 0)
        win.title("About MARAi")
        win.configure(bg=SURFACE)
        win.resizable(False, False)
        win.grab_set()
        try:
            _ico = getattr(self.winfo_toplevel(), "_ico_path", None)
            if _ico:
                win.iconbitmap(_ico)
        except Exception:
            pass
        w, h = 520, 560
        _centre_on_parent(win, self.winfo_toplevel(), w, h)
        VaultApp._build_about_content(win, self.winfo_toplevel())
        win.update()
        _apply_dwm_to_widget(win)
        win.wm_attributes("-alpha", 1)

    def _change_vault_location(self):
        """Let user pick a new folder for vault.enc and meta.json."""
        from tkinter import filedialog
        current = _get_vault_dir()
        new_dir = filedialog.askdirectory(
            title="Choose Vault Folder",
            initialdir=current,
            parent=self.winfo_toplevel()
        )
        if not new_dir:
            return

        import shutil
        new_vault = os.path.join(new_dir, "vault.enc")
        new_meta  = os.path.join(new_dir, "meta.json")

        # Check if vault already exists there
        if os.path.exists(new_vault) or os.path.exists(new_meta):
            answer = messagebox.askyesno(
                "Vault Exists",
                f"A vault already exists in:\n{new_dir}\n\n"
                "Do you want to switch to it? Your current vault will stay where it is.",
                parent=self.winfo_toplevel()
            )
            if not answer:
                return
        else:
            # Ask if they want to move or just point there
            answer = messagebox.askyesno(
                "Move Vault Files",
                f"Copy your vault files to:\n{new_dir}\n\n"
                "Your original files will remain in their current location as a backup.",
                parent=self.winfo_toplevel()
            )
            if not answer:
                return
            try:
                os.makedirs(new_dir, exist_ok=True)
                shutil.copy2(VAULT_FILE, new_vault)
                shutil.copy2(META_FILE,  new_meta)
            except Exception as e:
                messagebox.showerror("Error", f"Could not copy vault files:\n{e}",
                                     parent=self.winfo_toplevel())
                return

        # Update config and restart app to load from new location
        _set_vault_dir(new_dir)
        answer = messagebox.askyesno(
            "Vault Location Updated",
            f"Vault location set to:\n{new_dir}\n\n"
            "MARAi needs to restart to use the new location. Restart now?",
            parent=self.winfo_toplevel()
        )
        if answer:
            _restart_app()

    def _add_entry(self):
        def on_save(r):
            self.vault.insert(0, r)
            self._save_vault(); self._render()
        EntryDialog(self.winfo_toplevel(), on_save)

    def _rdp_connect(self, idx):
        entry     = self.vault[idx]
        host      = entry.get("host","").strip()
        port      = entry.get("port","3389").strip()
        username  = entry.get("user","").strip()
        password  = entry.get("password","")
        workspace = entry.get("workspace","").strip()

        if not workspace and not host:
            messagebox.showwarning("Missing Details",
                                   "No host address or workspace URL stored for this entry.",
                                   parent=self.winfo_toplevel())
            return

        # Copy password to clipboard before launching so it is ready to paste
        self._copy_secure(password)

        ok, err = _launch_rdp(host, port, username, password, workspace)
        if not ok:
            messagebox.showerror("Connection Error",
                                 f"Could not launch session:\n\n{err}",
                                 parent=self.winfo_toplevel())

    def _edit(self, idx):
        def on_save(r):
            self.vault[idx] = r
            self._save_vault(); self._render()
        EntryDialog(self.winfo_toplevel(), on_save, entry=self.vault[idx])

    def _delete(self, idx):
        if messagebox.askyesno("Delete",
                               f"Delete '{self.vault[idx]['name']}'? Cannot be undone.",
                               parent=self.winfo_toplevel()):
            del self.vault[idx]
            self._save_vault(); self._render()


# ══════════════════════════════════════════════════════════════════════════════
# Root Window
# ══════════════════════════════════════════════════════════════════════════════
def _launch_rdp(host, port, username, password, workspace=""):
    """
    Launch an RDP or AVD session.

    AVD (workspace URL provided):
      - Tries ms-avd: URI to open Windows App directly
      - Falls back to opening the workspace URL in the default browser
      - User authenticates via Azure AD in the client — Marai just launches it

    Standard RDP (no workspace URL):
      - Windows: writes credentials to Credential Manager, launches mstsc.exe,
        cleans up credentials after 10 seconds
      - Linux: launches xfreerdp if available
    """
    import subprocess

    # ── AVD path ──────────────────────────────────────────────────────────────
    if workspace:
        if sys.platform == "win32":
            try:
                # Try Windows App (ms-rd:) URI first — modern AVD client
                # Falls back to Remote Desktop app (ms-avd:) URI
                # Both open the correct AVD workspace if the app is installed
                import urllib.parse
                encoded_ws = urllib.parse.quote(workspace, safe="")
                uri = f"ms-avd:connect?workspaceId={encoded_ws}"
                result = subprocess.run(
                    ["cmd", "/c", "start", "", uri],
                    capture_output=True, timeout=5
                )
                return True, None
            except Exception:
                pass
        # Fallback for all platforms — open workspace URL in browser
        try:
            webbrowser.open(workspace)
            return True, None
        except Exception as e:
            return False, f"Could not open workspace URL: {e}"

    # ── Standard RDP path ────────────────────────────────────────────────────
    target = f"{host}:{port}" if port and str(port) != "3389" else host

    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            CRED_TYPE_GENERIC    = 1
            CRED_PERSIST_SESSION = 1

            class CREDENTIAL(ctypes.Structure):
                _fields_ = [
                    ("Flags",              wintypes.DWORD),
                    ("Type",               wintypes.DWORD),
                    ("TargetName",         wintypes.LPWSTR),
                    ("Comment",            wintypes.LPWSTR),
                    ("LastWritten",        ctypes.c_int64),
                    ("CredentialBlobSize", wintypes.DWORD),
                    ("CredentialBlob",     ctypes.POINTER(ctypes.c_byte)),
                    ("Persist",            wintypes.DWORD),
                    ("AttributeCount",     wintypes.DWORD),
                    ("Attributes",         ctypes.c_void_p),
                    ("TargetAlias",        wintypes.LPWSTR),
                    ("UserName",           wintypes.LPWSTR),
                ]

            advapi  = ctypes.windll.advapi32
            pw_bytes = (password + "\x00").encode("utf-16-le")
            blob     = (ctypes.c_byte * len(pw_bytes))(*pw_bytes)

            cred                    = CREDENTIAL()
            cred.Flags              = 0
            cred.Type               = CRED_TYPE_GENERIC
            cred.TargetName         = f"TERMSRV/{target}"
            cred.Comment            = "Added by Marai — auto removed after launch"
            cred.CredentialBlobSize = len(pw_bytes)
            cred.CredentialBlob     = blob
            cred.Persist            = CRED_PERSIST_SESSION
            cred.UserName           = username

            advapi.CredWriteW(ctypes.byref(cred), 0)
            subprocess.Popen(["mstsc.exe", f"/v:{target}"])

            def _cleanup():
                import time; time.sleep(10)
                try:
                    advapi.CredDeleteW(f"TERMSRV/{target}", CRED_TYPE_GENERIC, 0)
                except Exception:
                    pass
            threading.Thread(target=_cleanup, daemon=True).start()
            return True, None

        except Exception as e:
            return False, str(e)

    else:
        # Linux — try xfreerdp
        try:
            cmd = ["xfreerdp", f"/v:{target}", f"/u:{username}",
                   f"/p:{password}", "/cert:ignore", "+clipboard"]
            subprocess.Popen(cmd)
            return True, None
        except FileNotFoundError:
            return False, "xfreerdp not found. Install it with: sudo apt install freerdp2-x11"
        except Exception as e:
            return False, str(e)


def _restart_app():
    """Restart the application process — works for both .py and .exe."""
    import sys, os
    try:
        if getattr(sys, "frozen", False):
            # Running as PyInstaller exe
            os.execv(sys.executable, [sys.executable])
        else:
            # Running as .py script
            os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception:
        # execv not available (some platforms) — just quit and let user relaunch
        sys.exit(0)


def _centre_on_parent(win, parent, w, h):
    """Centre a dialog over its parent window — works on any monitor."""
    try:
        parent.update_idletasks()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        x  = px + (pw - w) // 2
        y  = py + (ph - h) // 2
    except Exception:
        x  = (win.winfo_screenwidth()  - w) // 2
        y  = (win.winfo_screenheight() - h) // 2
    win.geometry(f"{w}x{h}+{x}+{y}")


def _apply_dwm_to_widget(widget):
    """
    Apply dark DWM title bar. Must be called after the window is mapped.
    Uses alpha=0 trick: hide briefly so DWM can apply without showing white flash.
    """
    try:
        import ctypes
        GA_ROOT = 2
        inner   = widget.winfo_id()
        hwnd    = ctypes.windll.user32.GetAncestor(inner, GA_ROOT)
        if not hwnd:
            hwnd = inner
        _apply_dwm_dark_titlebar(hwnd)
    except Exception:
        pass


def _apply_dwm_dark_titlebar(hwnd):
    """
    Uses the Windows DWM API to colour the native title bar dark.
    Works on Windows 11 build 22000+ and Windows 10 build 19041+.
    Silently skipped on older Windows or non-Windows platforms.
    """
    try:
        import ctypes
        # Dark mode title bar (Windows 10 20H1+)
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE,
            ctypes.byref(ctypes.c_int(1)), ctypes.sizeof(ctypes.c_int))
    except Exception:
        pass

    try:
        import ctypes
        # Title bar background colour (Windows 11 build 22000+)
        DWMWA_CAPTION_COLOR = 35
        # Convert BG colour #0e0e16 to COLORREF (BGR format)
        r, g, b = 0x0e, 0x0e, 0x16
        colorref = ctypes.c_int(r | (g << 8) | (b << 16))
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_CAPTION_COLOR,
            ctypes.byref(colorref), ctypes.sizeof(colorref))
    except Exception:
        pass

    try:
        import ctypes
        # Title bar text colour (Windows 11 build 22000+)
        DWMWA_TEXT_COLOR = 36
        # Use our TEXT colour #e4e4f0
        r, g, b = 0xe4, 0xe4, 0xf0
        colorref = ctypes.c_int(r | (g << 8) | (b << 16))
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_TEXT_COLOR,
            ctypes.byref(colorref), ctypes.sizeof(colorref))
    except Exception:
        pass


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MARAi")
        self.configure(bg=BG)
        self.wm_attributes("-alpha", 0)   # hide until DWM is applied
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w = max(1000, min(int(sw * 0.75), 1400))
        h = max(640,  min(int(w  * 0.6),  sh - 80))
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
        self.resizable(True, True)
        self.minsize(820, 520)
        self._set_icon()
        self._show_lock()
        # Force window to be fully created before DWM call
        self.update()
        _apply_dwm_to_widget(self)
        self.wm_attributes("-alpha", 1)   # show with dark title bar already applied

    def _apply_theme(self):
        _apply_dwm_to_widget(self)

    def _set_icon(self):
        import sys
        base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        ico  = os.path.join(base, "marai.ico")
        if os.path.exists(ico):
            try:
                self.iconbitmap(ico)
            except Exception:
                pass
        self._ico_path = ico if os.path.exists(ico) else None

        # Set AppUserModelID so Windows taskbar uses the correct ICO
        # without this, the taskbar icon is taken from the exe header only
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "ManPlate.MARAi.PasswordManager")
        except Exception:
            pass

    def _clear(self):
        for w in self.winfo_children():
            w.destroy()
        self.configure(bg=BG)

    def _show_vault(self, key):
        self._clear()
        VaultApp(self, key=key, on_lock=self._show_lock)
        self.after(30, self._apply_theme)

    def _show_lock(self):
        self._clear()
        LockScreen(self, on_unlock=self._show_vault)
        self.after(30, self._apply_theme)


if __name__ == "__main__":
    if not CRYPTO_OK:
        import sys
        print("ERROR: run:  pip install cryptography pyperclip")
        sys.exit(1)
    App().mainloop()
