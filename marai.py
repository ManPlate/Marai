#!/usr/bin/env python3
"""
Marai - Offline Desktop Password Manager
Requires: pip install cryptography pyperclip Pillow
Optional: pip install argon2-cffi (stronger key derivation)
"""

import tkinter as tk
from tkinter import messagebox, ttk
import json, os, base64, secrets, string, threading, urllib.request
import webbrowser, subprocess, ctypes, sys, datetime, csv, io, shutil
import time as _time

# == Version ================================================================
VERSION = "3.2.0"
CHANGELOG = [
    ("3.2.0", "Brand logos at 64px with disk cache, domain guessing from entry name, "
              "custom icon upload, 80+ brand domains mapped"),
    ("3.1.0", "Premium UI refresh, CSV import/export, vault backup, "
              "category-specific entry forms, 8 themes, lock timer fix"),
    ("3.0.0", "Work/Personal vault categories, Light/Dark theme, view modes, Import & Export"),
    ("2.5.0", "Secure Notes - store crypto passphrases, recovery codes and any sensitive text"),
    ("2.4.2", "Auto-copy password when launching URL or RDP session"),
    ("2.4.1", "Portable USB mode - zero setup on any machine"),
    ("2.4.0", "Category filters, URL launch, search all fields, custom vault folder"),
    ("2.3.0", "RDP session launch from Server entries"),
    ("2.2.0", "Favourite entries and password age indicator"),
    ("2.1.0", "Upgraded to Argon2id key derivation - silent migration on login"),
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

# == Update Checker =========================================================
GITHUB_USER    = "ManPlate"
GITHUB_REPO    = "Marai"
VERSION_URL    = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/main/version.json"
RELEASES_URL   = f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}/releases"

def check_for_update(callback):
    def _check():
        try:
            req = urllib.request.Request(VERSION_URL, headers={"User-Agent": f"Marai/{VERSION}"})
            with urllib.request.urlopen(req, timeout=5) as r:
                data = json.loads(r.read().decode())
                latest = data.get("version", "")
                if latest and latest != VERSION:
                    def parse(v): return tuple(int(x) for x in v.split("."))
                    if parse(latest) > parse(VERSION):
                        callback(latest)
        except Exception:
            pass
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

# == Brand Icon System ======================================================
# Tier 1: Fetch high-res logos from Google (128px), cache to disk, display at 64px
# Tier 2: Guess domain from entry name for entries without URLs
# Tier 3: Manual icon upload stored with entry
# Tier 4: Emoji fallback
_ICON_CACHE     = {}       # domain -> {"128": PhotoImage, "64": PhotoImage, "40": PhotoImage}
_ICON_PENDING   = {}       # domain -> [callback, callback, ...] — multiple cards can wait
_ICON_DIR       = None     # set after CONFIG_DIR is defined

# Common brand name -> domain mapping for entries without URLs
_BRAND_DOMAINS = {
    # Banks — International
    "chase": "chase.com", "wells fargo": "wellsfargo.com",
    "bank of america": "bankofamerica.com", "bofa": "bankofamerica.com",
    "citibank": "citibank.com", "citi": "citibank.com",
    "hsbc": "hsbc.com", "barclays": "barclays.co.uk",
    "anz": "anz.com.au", "commbank": "commbank.com.au",
    "revolut": "revolut.com", "wise": "wise.com", "n26": "n26.com",
    "monzo": "monzo.com", "starling": "starlingbank.com",
    "deutsche bank": "db.com", "ubs": "ubs.com",
    "credit suisse": "credit-suisse.com", "bnp paribas": "bnpparibas.com",
    "ing": "ing.com", "santander": "santander.com",
    "td bank": "td.com", "rbc": "rbc.com", "scotiabank": "scotiabank.com",
    "capital one": "capitalone.com", "ally": "ally.com",
    "goldman sachs": "goldmansachs.com", "morgan stanley": "morganstanley.com",
    "jp morgan": "jpmorgan.com", "jpmorgan": "jpmorgan.com",
    "american express": "americanexpress.com", "amex": "americanexpress.com",
    # Banks — India
    "sbi": "bank.sbi", "state bank": "bank.sbi", "state bank of india": "bank.sbi",
    "hdfc": "hdfcbank.com", "hdfc bank": "hdfcbank.com",
    "icici": "icicibank.com", "icici bank": "icicibank.com",
    "axis": "axisbank.com", "axis bank": "axisbank.com",
    "kotak": "kotak.com", "kotak mahindra": "kotak.com",
    "yes bank": "yesbank.in", "idbi": "idbibank.in",
    "pnb": "pnbindia.in", "punjab national bank": "pnbindia.in",
    "bob": "bankofbaroda.in", "bank of baroda": "bankofbaroda.in",
    "canara bank": "canarabank.com", "union bank": "unionbankofindia.co.in",
    "indian bank": "indianbank.in", "iob": "iob.in",
    "federal bank": "federalbank.co.in", "south indian bank": "southindianbank.com",
    "bandhan bank": "bandhanbank.com", "idfc": "idfcfirstbank.com",
    "idfc first": "idfcfirstbank.com", "rbl": "rblbank.com",
    "paytm": "paytm.com", "phonepe": "phonepe.com", "gpay": "pay.google.com",
    "google pay": "pay.google.com", "bhim": "bhimupi.org.in",
    "cred": "cred.club", "groww": "groww.in", "zerodha": "zerodha.com",
    "upstox": "upstox.com", "angel one": "angelone.in",
    # Banks — Other regions
    "dbs": "dbs.com", "ocbc": "ocbc.com", "maybank": "maybank.com",
    "kasikorn": "kasikornbank.com", "bdo": "bdo.com.ph",
    "nab": "nab.com.au", "westpac": "westpac.com.au",
    # Fintech & Payments
    "paypal": "paypal.com", "stripe": "stripe.com", "venmo": "venmo.com",
    "coinbase": "coinbase.com", "binance": "binance.com", "kraken": "kraken.com",
    "razorpay": "razorpay.com", "cashfree": "cashfree.com",
    "square": "squareup.com", "zelle": "zellepay.com",
    # Tech & Cloud
    "google": "google.com", "gmail": "gmail.com", "microsoft": "microsoft.com",
    "outlook": "outlook.com", "office 365": "office.com", "office365": "office.com",
    "azure": "azure.microsoft.com", "o365": "office.com",
    "apple": "apple.com", "icloud": "icloud.com", "amazon": "amazon.com",
    "aws": "aws.amazon.com", "facebook": "facebook.com", "meta": "meta.com",
    "twitter": "twitter.com", "x": "x.com", "linkedin": "linkedin.com",
    "github": "github.com", "gitlab": "gitlab.com", "bitbucket": "bitbucket.org",
    "slack": "slack.com", "discord": "discord.com", "zoom": "zoom.us",
    "teams": "teams.microsoft.com", "dropbox": "dropbox.com", "onedrive": "onedrive.com",
    "google drive": "drive.google.com", "notion": "notion.so", "figma": "figma.com",
    "adobe": "adobe.com", "canva": "canva.com", "trello": "trello.com",
    "jira": "atlassian.com", "asana": "asana.com", "monday": "monday.com",
    "salesforce": "salesforce.com", "hubspot": "hubspot.com", "zendesk": "zendesk.com",
    "shopify": "shopify.com", "wordpress": "wordpress.com",
    "servicenow": "servicenow.com", "oracle": "oracle.com", "sap": "sap.com",
    "vmware": "vmware.com", "cisco": "cisco.com", "fortinet": "fortinet.com",
    "palo alto": "paloaltonetworks.com", "crowdstrike": "crowdstrike.com",
    "okta": "okta.com", "auth0": "auth0.com", "1password": "1password.com",
    "lastpass": "lastpass.com", "bitwarden": "bitwarden.com",
    "datadog": "datadoghq.com", "splunk": "splunk.com",
    "confluence": "atlassian.com", "bitbucket": "bitbucket.org",
    # Hosting & Dev
    "cloudflare": "cloudflare.com", "digitalocean": "digitalocean.com",
    "heroku": "heroku.com", "vercel": "vercel.com", "netlify": "netlify.com",
    "godaddy": "godaddy.com", "namecheap": "namecheap.com",
    "docker": "docker.com", "npm": "npmjs.com", "pypi": "pypi.org",
    "linode": "linode.com", "vultr": "vultr.com", "hetzner": "hetzner.com",
    # Entertainment
    "netflix": "netflix.com", "spotify": "spotify.com", "youtube": "youtube.com",
    "twitch": "twitch.tv", "disney+": "disneyplus.com", "disney plus": "disneyplus.com",
    "hulu": "hulu.com", "hbo": "hbomax.com", "hbo max": "hbomax.com",
    "prime video": "primevideo.com", "amazon prime": "primevideo.com",
    "hotstar": "hotstar.com", "jiocinema": "jiocinema.com",
    "sonyliv": "sonyliv.com", "zee5": "zee5.com",
    "reddit": "reddit.com", "instagram": "instagram.com", "tiktok": "tiktok.com",
    "pinterest": "pinterest.com", "snapchat": "snapchat.com",
    # Communication
    "whatsapp": "whatsapp.com", "telegram": "telegram.org", "signal": "signal.org",
    "skype": "skype.com", "viber": "viber.com",
    # Gaming
    "steam": "store.steampowered.com", "epic games": "epicgames.com",
    "playstation": "playstation.com", "xbox": "xbox.com", "nintendo": "nintendo.com",
    "riot games": "riotgames.com", "blizzard": "blizzard.com",
    # Shopping
    "ebay": "ebay.com", "walmart": "walmart.com", "target": "target.com",
    "bestbuy": "bestbuy.com", "aliexpress": "aliexpress.com", "etsy": "etsy.com",
    "flipkart": "flipkart.com", "myntra": "myntra.com", "ajio": "ajio.com",
    "swiggy": "swiggy.com", "zomato": "zomato.com",
    # Insurance & Gov
    "lic": "licindia.in", "policybazaar": "policybazaar.com",
    "aadhaar": "uidai.gov.in", "digilocker": "digilocker.gov.in",
    "irctc": "irctc.co.in",
}

def _domain_from_url(url):
    if not url: return None
    try:
        import urllib.parse
        u = url if "://" in url else "https://" + url
        return urllib.parse.urlparse(u).hostname or None
    except Exception:
        return None

def _guess_domain(entry):
    """Find the best domain for icon lookup. Name brand match > URL > host > heuristic."""
    name = entry.get("name", "").strip().lower()
    cat = _entry_cat(entry)
    # 1. From name via brand dictionary (best quality — clean primary domains)
    if name in _BRAND_DOMAINS:
        return _BRAND_DOMAINS[name]
    # Also check bank_name field for Bank Account / Credit Card categories
    extra_names = []
    if cat in ("Bank Account", "Credit Card"):
        bn = entry.get("bank_name", "").strip().lower()
        if bn: extra_names.append(bn)
    for check_name in [name] + extra_names:
        for brand, domain in _BRAND_DOMAINS.items():
            if brand in check_name or check_name in brand:
                return domain
        # Try individual words from the name (handles "SBI Savings Account" → matches "sbi")
        words = check_name.split()
        for word in words:
            if len(word) >= 2 and word in _BRAND_DOMAINS:
                return _BRAND_DOMAINS[word]
    # 2. From URL
    d = _domain_from_url(entry.get("url", ""))
    if d: return d
    # 3. From host field
    h = entry.get("host", "").strip()
    if h and "." in h: return h
    # 4. Heuristic: try name.com
    slug = name.replace(" ", "").replace("-", "")
    if slug and len(slug) >= 3 and slug.isalnum():
        return f"{slug}.com"
    return None

def _icon_disk_path(domain):
    """Path to cached icon file on disk."""
    safe = domain.replace("/", "_").replace(":", "_").replace("\\", "_")
    return os.path.join(_ICON_DIR, f"{safe}.png")

def _load_icon_from_disk(domain):
    """Load a cached icon from disk. Returns raw PNG bytes or None."""
    path = _icon_disk_path(domain)
    if os.path.exists(path):
        try:
            with open(path, "rb") as f:
                return f.read()
        except Exception:
            pass
    return None

def _save_icon_to_disk(domain, png_data):
    """Save PNG bytes to disk cache."""
    try:
        with open(_icon_disk_path(domain), "wb") as f:
            f.write(png_data)
    except Exception:
        pass

# Try to import Pillow for high-quality image resizing
try:
    from PIL import Image as _PILImage, ImageTk as _PILImageTk
    _PIL_OK = True
except ImportError:
    _PIL_OK = False

def _remove_icon_bg(img):
    """Remove white/light grey uniform backgrounds from icons. Preserves colored backgrounds."""
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    w, h = img.size
    if w < 4 or h < 4: return img
    pixels = img.load()
    m = 2
    corners = [pixels[m,m], pixels[w-1-m,m], pixels[m,h-1-m], pixels[w-1-m,h-1-m]]
    def _similar(c1, c2, tol=30):
        return all(abs(a-b) <= tol for a,b in zip(c1[:3], c2[:3]))
    if not all(_similar(corners[0], c) for c in corners[1:]):
        return img  # corners differ, not a uniform background
    bg = corners[0][:3]
    # Skip if already transparent
    if len(corners[0]) >= 4 and corners[0][3] < 10:
        return img
    # Only remove WHITE or near-white backgrounds (luminance > 210)
    # Colored backgrounds (blue, green, red etc) are intentional brand design
    lum = bg[0] * 0.299 + bg[1] * 0.587 + bg[2] * 0.114
    if lum < 210:
        return img  # colored background — keep it
    # Replace white/light background pixels with transparency
    data = img.getdata()
    new_data = []
    for px in data:
        if _similar(px, bg + (255,), tol=35):
            new_data.append((px[0], px[1], px[2], 0))
        else:
            new_data.append(px)
    img.putdata(new_data)
    return img

def _resize_icon_pil(png_data, target_size):
    """Resize PNG data to target_size using Pillow with LANCZOS. Returns PhotoImage or None."""
    try:
        img = _PILImage.open(io.BytesIO(png_data))
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        # Remove uniform background (white squares etc)
        img = _remove_icon_bg(img)
        # Fit within target while preserving aspect ratio
        img.thumbnail((target_size, target_size), _PILImage.LANCZOS)
        # Center on a square transparent canvas
        canvas = _PILImage.new("RGBA", (target_size, target_size), (0, 0, 0, 0))
        x = (target_size - img.width) // 2
        y = (target_size - img.height) // 2
        canvas.paste(img, (x, y), img)
        return _PILImageTk.PhotoImage(canvas)
    except Exception:
        return None

def _make_icon_sizes(png_data):
    """Create PhotoImage at multiple display sizes from source PNG data.
    Uses Pillow (LANCZOS) if available, falls back to tkinter subsample."""
    if _PIL_OK:
        try:
            i64 = _resize_icon_pil(png_data, 64)
            i40 = _resize_icon_pil(png_data, 40)
            if i64 or i40:
                return {"64": i64, "40": i40}
        except Exception:
            pass
    # Fallback: tkinter subsample (lower quality, no aspect ratio fix)
    try:
        import base64 as _b64
        full = tk.PhotoImage(data=_b64.b64encode(png_data).decode())
        w, h = full.width(), full.height()
        if w < 16 or h < 16:
            return None
        result = {"full": full}
        if w >= 96:
            result["64"] = full.subsample(max(1, w // 64))
        else:
            result["64"] = full
        if w >= 64:
            result["40"] = full.subsample(max(1, w // 40))
        else:
            result["40"] = full
        return result
    except Exception:
        return None

def _load_custom_icon(entry):
    """Load a custom icon stored as base64 in the entry. Returns PhotoImage dict or None."""
    b64 = entry.get("custom_icon_b64", "")
    if not b64:
        return None
    try:
        import base64 as _b64
        png_data = _b64.b64decode(b64)
        return _make_icon_sizes(png_data)
    except Exception:
        return None

def _fetch_brand_icon(domain, callback):
    """Fetch icon in background thread. Tries multiple sources. Multiple callbacks per domain."""
    if domain in _ICON_PENDING:
        _ICON_PENDING[domain].append(callback)
        return
    _ICON_PENDING[domain] = [callback]

    def _try_fetch(url):
        """Fetch icon from URL. Returns bytes or None."""
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Marai/3.2"})
            with urllib.request.urlopen(req, timeout=5) as r:
                data = r.read()
            if data and len(data) > 100:
                return data
        except Exception: pass
        return None

    def _worker():
        icons = None
        cached_data = _load_icon_from_disk(domain)
        if cached_data and len(cached_data) > 100:
            icons = _make_icon_sizes(cached_data)
        if not icons:
            # Delete stale/bad cache file if it exists
            try: os.remove(_icon_disk_path(domain))
            except: pass
            png_data = None
            # Source 1: Google Favicons at 256px
            png_data = _try_fetch(f"https://www.google.com/s2/favicons?domain={domain}&sz=256")
            # Source 2: DuckDuckGo icons
            if not png_data:
                png_data = _try_fetch(f"https://icons.duckduckgo.com/ip3/{domain}.ico")
            # Source 3: Direct favicon from the site
            if not png_data:
                png_data = _try_fetch(f"https://{domain}/favicon.ico")
            if png_data:
                _save_icon_to_disk(domain, png_data)
                icons = _make_icon_sizes(png_data)
        _ICON_CACHE[domain] = icons
        callbacks = _ICON_PENDING.pop(domain, [])
        for cb in callbacks:
            cb(domain, icons)

    threading.Thread(target=_worker, daemon=True).start()

def _get_icon(entry, size="64", on_ready=None):
    """Get a brand icon for an entry at the given size.
    Returns PhotoImage or None. Kicks off async fetch if not cached.
    size: '64' for large cards, '40' for compact views."""
    # 1. Custom icon
    custom = _load_custom_icon(entry)
    if custom and size in custom:
        return custom[size]
    # 2. Domain-based lookup
    domain = _guess_domain(entry)
    if not domain:
        return None
    # Check memory cache
    if domain in _ICON_CACHE:
        icons = _ICON_CACHE[domain]
        if icons and size in icons:
            return icons[size]
        return None
    # Try disk cache synchronously (fast)
    disk_data = _load_icon_from_disk(domain)
    if disk_data:
        icons = _make_icon_sizes(disk_data)
        _ICON_CACHE[domain] = icons
        if icons and size in icons:
            return icons[size]
        return None
    # Async fetch — registers callback even if another fetch for same domain is in progress
    if on_ready:
        _fetch_brand_icon(domain, on_ready)
    return None

# == Paths ==================================================================
CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".marai")
os.makedirs(CONFIG_DIR, exist_ok=True)

# Now that CONFIG_DIR exists, set up icon cache directory
_ICON_DIR = os.path.join(CONFIG_DIR, "icons")
os.makedirs(_ICON_DIR, exist_ok=True)

def _exe_dir():
    if getattr(sys, "_MEIPASS", None):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def _portable_config_file():
    return os.path.join(_exe_dir(), "config.json")

def _local_config_file():
    return os.path.join(CONFIG_DIR, "config.json")

def _active_config_file():
    portable = _portable_config_file()
    exe_dir  = _exe_dir()
    if os.path.exists(portable): return portable
    if (os.path.exists(os.path.join(exe_dir, "vault.enc")) or
            os.path.exists(os.path.join(exe_dir, "meta.json"))):
        return portable
    return _local_config_file()

def _load_config():
    cfg_file = _active_config_file()
    defaults = {"vault_dir": os.path.dirname(cfg_file)
                if cfg_file == _portable_config_file() else CONFIG_DIR}
    try:
        if os.path.exists(cfg_file):
            with open(cfg_file, encoding="utf-8") as f:
                data = json.load(f)
            defaults.update(data)
    except Exception: pass
    return defaults

def _save_config(data):
    cfg_file = _active_config_file()
    try:
        with open(cfg_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        try:
            with open(_local_config_file(), "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception: pass

def _get_vault_dir():
    return _load_config().get("vault_dir", CONFIG_DIR)

def _get_vault_theme(vault_dir):
    """Get saved theme for a specific vault. Falls back to global theme."""
    cfg = _load_config()
    vt = cfg.get("vault_themes", {})
    return vt.get(os.path.normpath(vault_dir), cfg.get("theme", "Dark"))

def _save_vault_theme(vault_dir, theme_name):
    """Save theme choice for a specific vault."""
    cfg = _load_config()
    vt = cfg.get("vault_themes", {})
    vt[os.path.normpath(vault_dir)] = theme_name
    cfg["vault_themes"] = vt
    _save_config(cfg)

def _get_zoom_level():
    return _load_config().get("zoom", 100)

def _save_zoom_level(z):
    cfg = _load_config(); cfg["zoom"] = z; _save_config(cfg)

def _get_saved_vault_tabs():
    """Get list of extra vault directories from config."""
    return _load_config().get("vault_tabs", [])

def _save_vault_tabs(dirs):
    """Save list of extra vault directories to config."""
    cfg = _load_config()
    cfg["vault_tabs"] = [os.path.normpath(d) for d in dirs]
    _save_config(cfg)

def _set_vault_dir(path):
    cfg = _load_config(); cfg["vault_dir"] = path
    _save_config(cfg); _refresh_paths(path)

def _refresh_paths(vault_dir=None):
    global APP_DIR, VAULT_FILE, META_FILE
    APP_DIR    = vault_dir or _get_vault_dir()
    VAULT_FILE = os.path.join(APP_DIR, "vault.enc")
    META_FILE  = os.path.join(APP_DIR, "meta.json")
    os.makedirs(APP_DIR, exist_ok=True)

APP_DIR    = CONFIG_DIR
VAULT_FILE = os.path.join(APP_DIR, "vault.enc")
META_FILE  = os.path.join(APP_DIR, "meta.json")
_refresh_paths()

# == Migration ==============================================================
def migrate_from_vaultkey():
    old_dir = os.path.join(os.path.expanduser("~"), ".vaultkey")
    if not os.path.exists(old_dir): return
    if os.path.exists(os.path.join(CONFIG_DIR, "meta.json")): return
    try:
        for fname in ["vault.enc", "meta.json"]:
            src = os.path.join(old_dir, fname)
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(CONFIG_DIR, fname))
        open(os.path.join(CONFIG_DIR, ".needs_token_patch"), "w").close()
    except Exception: pass

migrate_from_vaultkey()

def patch_verify_token_if_needed(key):
    flag = os.path.join(CONFIG_DIR, ".needs_token_patch")
    if not os.path.exists(flag): return
    try:
        new_verify = encrypt_data(key, "MARAI_OK")
        with open(META_FILE, encoding="utf-8") as f:
            meta = json.load(f)
        meta["verify"] = base64.b64encode(new_verify).decode()
        with open(META_FILE, "w", encoding="utf-8") as f:
            json.dump(meta, f)
        os.remove(flag)
    except Exception: pass

# == Crypto =================================================================
ARGON2_TIME_COST   = 3
ARGON2_MEMORY_COST = 65536
ARGON2_PARALLELISM = 4
ARGON2_HASH_LEN    = 32
KDF_VERSION        = "argon2id"

def derive_key_argon2id(password, salt):
    return hash_secret_raw(
        secret=password.encode(), salt=salt,
        time_cost=ARGON2_TIME_COST, memory_cost=ARGON2_MEMORY_COST,
        parallelism=ARGON2_PARALLELISM, hash_len=ARGON2_HASH_LEN, type=Type.ID)

def derive_key_pbkdf2(password, salt):
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=390000)
    return kdf.derive(password.encode())

def derive_key(password, salt, kdf=None):
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

def load_meta(meta_file=None):
    mf = meta_file or META_FILE
    if os.path.exists(mf):
        with open(mf, encoding="utf-8") as f:
            return json.load(f)
    return None

def save_meta(salt_b64, verify_b64, kdf=KDF_VERSION, meta_file=None):
    mf = meta_file or META_FILE
    with open(mf, "w", encoding="utf-8") as f:
        json.dump({"salt": salt_b64, "verify": verify_b64, "kdf": kdf}, f)

def vault_exists(meta_file=None, vault_file=None):
    mf = meta_file or META_FILE
    vf = vault_file or VAULT_FILE
    return os.path.exists(mf) and os.path.exists(vf)

# == Theme Palettes =========================================================
# == Theme Palettes =========================================================
_DARK_PALETTE = {
    "BG": "#08081a", "SURFACE": "#10102a", "SURFACE2": "#181838",
    "SURFACE3": "#202048", "BORDER": "#282855", "CARD_BORDER": "#303068",
    "ACCENT": "#7c5cfc", "GREEN": "#4ecca3", "RED": "#fc5c7d",
    "TEXT": "#e8e8f4", "MUTED": "#6e6e96",
    "TITLEBAR_BG": "#06060f", "BTN_CLOSE_HOV": "#c0392b", "TITLEBAR_H": 36,
    "_dwm_r": 0x08, "_dwm_g": 0x08, "_dwm_b": 0x1a, "_dwm_dark": 1,
    "_name": "Dark",
}

_ALL_PALETTES = {
    "Dark": _DARK_PALETTE,
    "Emerald": {
        "BG": "#081a10", "SURFACE": "#0e2818", "SURFACE2": "#163822",
        "SURFACE3": "#1e4830", "BORDER": "#28583a", "CARD_BORDER": "#306848",
        "ACCENT": "#50d890", "GREEN": "#40c878", "RED": "#f06060",
        "TEXT": "#e0f4e8", "MUTED": "#60a078",
        "TITLEBAR_BG": "#06120c", "BTN_CLOSE_HOV": "#c0392b", "TITLEBAR_H": 36,
        "_dwm_r": 0x08, "_dwm_g": 0x1a, "_dwm_b": 0x10, "_dwm_dark": 1,
        "_name": "Emerald",
    },
    "Ocean": {
        "BG": "#0a1620", "SURFACE": "#101e2c", "SURFACE2": "#182838",
        "SURFACE3": "#203244", "BORDER": "#2a4058", "CARD_BORDER": "#345068",
        "ACCENT": "#20a0d0", "GREEN": "#40c8a0", "RED": "#f06070",
        "TEXT": "#e0eef8", "MUTED": "#6090b0",
        "TITLEBAR_BG": "#081018", "BTN_CLOSE_HOV": "#c0392b", "TITLEBAR_H": 36,
        "_dwm_r": 0x0a, "_dwm_g": 0x16, "_dwm_b": 0x20, "_dwm_dark": 1,
        "_name": "Ocean",
    },
    "Mocha": {
        "BG": "#1a1410", "SURFACE": "#221c16", "SURFACE2": "#2e2620",
        "SURFACE3": "#3a3028", "BORDER": "#4a3e32", "CARD_BORDER": "#5a4e40",
        "ACCENT": "#d0884a", "GREEN": "#60b880", "RED": "#e06050",
        "TEXT": "#f0e8e0", "MUTED": "#908070",
        "TITLEBAR_BG": "#12100c", "BTN_CLOSE_HOV": "#c0392b", "TITLEBAR_H": 36,
        "_dwm_r": 0x1a, "_dwm_g": 0x14, "_dwm_b": 0x10, "_dwm_dark": 1,
        "_name": "Mocha",
    },
    "Neon": {
        "BG": "#0a0a0e", "SURFACE": "#121216", "SURFACE2": "#1a1a20",
        "SURFACE3": "#22222a", "BORDER": "#2e2e3a", "CARD_BORDER": "#383848",
        "ACCENT": "#ff2e88", "GREEN": "#00ffa0", "RED": "#ff4060",
        "TEXT": "#f0f0ff", "MUTED": "#707090",
        "TITLEBAR_BG": "#060608", "BTN_CLOSE_HOV": "#ff2e88", "TITLEBAR_H": 36,
        "_dwm_r": 0x0a, "_dwm_g": 0x0a, "_dwm_b": 0x0e, "_dwm_dark": 1,
        "_name": "Neon",
    },
    "Ferrari": {
        "BG": "#f7f2f2", "SURFACE": "#ffffff", "SURFACE2": "#f0e9e9",
        "SURFACE3": "#e5d8d8", "BORDER": "#d2c6c6", "CARD_BORDER": "#c4b8b8",
        "ACCENT": "#C00000", "GREEN": "#2a7a54", "RED": "#cb4154",
        "TEXT": "#231818", "MUTED": "#6f5c5c",
        "TITLEBAR_BG": "#e5d8d8", "BTN_CLOSE_HOV": "#C00000", "TITLEBAR_H": 36,
        "_dwm_r": 0xe5, "_dwm_g": 0xd8, "_dwm_b": 0xd8, "_dwm_dark": 0,
        "_name": "Ferrari",
    },
    "Sage Green": {
        "BG": "#edf3ee", "SURFACE": "#f8fdf8", "SURFACE2": "#e4ede5",
        "SURFACE3": "#d8e8da", "BORDER": "#b8d0bb", "CARD_BORDER": "#a8c4ac",
        "ACCENT": "#2d7a4a", "GREEN": "#1a6e3a", "RED": "#c0392b",
        "TEXT": "#182018", "MUTED": "#5a7460",
        "TITLEBAR_BG": "#d8e8da", "BTN_CLOSE_HOV": "#c0392b", "TITLEBAR_H": 36,
        "_dwm_r": 0xd8, "_dwm_g": 0xe8, "_dwm_b": 0xda, "_dwm_dark": 0,
        "_name": "Sage Green",
    },
    "Rose": {
        "BG": "#f8eef2", "SURFACE": "#fff8fb", "SURFACE2": "#f2e4eb",
        "SURFACE3": "#ead4df", "BORDER": "#d8b8cb", "CARD_BORDER": "#ccaabf",
        "ACCENT": "#a03060", "GREEN": "#2d7a4a", "RED": "#b01040",
        "TEXT": "#280f1a", "MUTED": "#7a5068",
        "TITLEBAR_BG": "#ead4df", "BTN_CLOSE_HOV": "#b01040", "TITLEBAR_H": 36,
        "_dwm_r": 0xea, "_dwm_g": 0xd4, "_dwm_b": 0xdf, "_dwm_dark": 0,
        "_name": "Rose",
    },
    "Amber": {
        "BG": "#faf6ee", "SURFACE": "#fffcf5", "SURFACE2": "#f5eedc",
        "SURFACE3": "#ece0c8", "BORDER": "#d8c8a0", "CARD_BORDER": "#c8b888",
        "ACCENT": "#c87800", "GREEN": "#2a7848", "RED": "#c83838",
        "TEXT": "#2a2010", "MUTED": "#887050",
        "TITLEBAR_BG": "#ece0c8", "BTN_CLOSE_HOV": "#c0392b", "TITLEBAR_H": 36,
        "_dwm_r": 0xec, "_dwm_g": 0xe0, "_dwm_b": 0xc8, "_dwm_dark": 0,
        "_name": "Amber",
    },
    "Mint": {
        "BG": "#eefaf8", "SURFACE": "#f5fffd", "SURFACE2": "#e0f4f0",
        "SURFACE3": "#d0ebe6", "BORDER": "#a8d8ce", "CARD_BORDER": "#90c8bc",
        "ACCENT": "#0098a0", "GREEN": "#18886a", "RED": "#c04050",
        "TEXT": "#0c2020", "MUTED": "#508888",
        "TITLEBAR_BG": "#d0ebe6", "BTN_CLOSE_HOV": "#c0392b", "TITLEBAR_H": 36,
        "_dwm_r": 0xd0, "_dwm_g": 0xeb, "_dwm_b": 0xe6, "_dwm_dark": 0,
        "_name": "Mint",
    },
}


def _apply_palette(palette):
    g = globals()
    for k, v in palette.items():
        if not k.startswith("_"):
            g[k] = v

def _get_saved_theme():
    return _load_config().get("theme", "Dark")

def _save_theme(name):
    cfg = _load_config(); cfg["theme"] = name; _save_config(cfg)

def _get_saved_view_mode():
    return _load_config().get("view_mode", "small")

def _save_view_mode(mode):
    cfg = _load_config(); cfg["view_mode"] = mode; _save_config(cfg)

# Apply theme on startup
_CURRENT_THEME = _get_saved_theme()
if _CURRENT_THEME not in _ALL_PALETTES:
    _CURRENT_THEME = "Dark"
_apply_palette(_ALL_PALETTES[_CURRENT_THEME])

# Colour globals
BG = BG if "BG" in dir() else "#0a0a14"
SURFACE = SURFACE if "SURFACE" in dir() else "#111120"
SURFACE2 = SURFACE2 if "SURFACE2" in dir() else "#1a1a2e"
SURFACE3 = SURFACE3 if "SURFACE3" in dir() else "#22223a"
BORDER = BORDER if "BORDER" in dir() else "#2a2a44"
CARD_BORDER = CARD_BORDER if "CARD_BORDER" in dir() else "#33335a"
ACCENT = ACCENT if "ACCENT" in dir() else "#7c5cfc"
GREEN = GREEN if "GREEN" in dir() else "#4ecca3"
RED = RED if "RED" in dir() else "#fc5c7d"
TEXT = TEXT if "TEXT" in dir() else "#e8e8f4"
MUTED = MUTED if "MUTED" in dir() else "#6e6e96"
TITLEBAR_BG = TITLEBAR_BG if "TITLEBAR_BG" in dir() else "#08080e"
BTN_CLOSE_HOV = BTN_CLOSE_HOV if "BTN_CLOSE_HOV" in dir() else "#c0392b"
TITLEBAR_H = TITLEBAR_H if "TITLEBAR_H" in dir() else 36

FNT_TITLE  = ("Segoe UI", 22, "bold")
FNT_HEAD   = ("Segoe UI", 12, "bold")
FNT_BODY   = ("Segoe UI", 11)
FNT_MONO   = ("Consolas", 11)
FNT_SM     = ("Segoe UI", 9)
FNT_BTN    = ("Segoe UI", 10, "bold")

# == Category Definitions ===================================================
CATEGORY_DEFS = {
    "Password":            {"emoji": "\U0001f511", "color": "#9f7eff", "bg": "#1a1035"},
    "Bank Account":        {"emoji": "\U0001f3e6", "color": "#4ecca3", "bg": "#082820"},
    "Credit Card":         {"emoji": "\U0001f4b3", "color": "#f5c518", "bg": "#2a2000"},
    "Email Account":       {"emoji": "\U0001f4e7", "color": "#61dafb", "bg": "#041828"},
    "Secure Note":         {"emoji": "\U0001f4dd", "color": "#ffb347", "bg": "#281800"},
    "Domain Credential":   {"emoji": "\U0001f3e2", "color": "#56b8ff", "bg": "#0a1e38"},
    "Server / RDP":        {"emoji": "\U0001f5a5", "color": "#60d0a0", "bg": "#0e2a20"},
    "SSH Key":             {"emoji": "\U0001f510", "color": "#c4b0ff", "bg": "#1a1040"},
    "Identity":            {"emoji": "\U0001faaa", "color": "#ff9a7a", "bg": "#2e150a"},
    "Wi-Fi Password":      {"emoji": "\U0001f4e1", "color": "#7c9eff", "bg": "#0f1835"},
    "Software License":    {"emoji": "\U0001f4bf", "color": "#b0d0ff", "bg": "#101828"},
    "Other":               {"emoji": "\U0001f5c2", "color": "#9090b0", "bg": "#1a1a28"},
}
CATEGORIES  = list(CATEGORY_DEFS.keys())
CAT_EMOJI   = {k: v["emoji"] for k, v in CATEGORY_DEFS.items()}
CAT_COLORS  = {k: (v["color"], v["bg"]) for k, v in CATEGORY_DEFS.items()}
TYPE_COLORS = CAT_COLORS
TYPE_EMOJI  = CAT_EMOJI
ENTRY_TYPES = CATEGORIES

CONTEXT_COLORS = {"Work": ("#7c9eff", "#0f1a35"), "Personal": ("#ff9a7a", "#2e150a")}
CONTEXT_EMOJI  = {"Work": "\U0001f4bc", "Personal": "\U0001f3e0"}
CONTEXTS       = list(CONTEXT_COLORS.keys())

_LEGACY_CAT_MAP = {
    "Login": "Password", "Note": "Secure Note", "Server": "Server / RDP",
    "Work": "Password", "Email": "Email Account", "Social": "Password",
    "Finance": "Bank Account", "Dev": "Password", "Other": "Other",
}

def _entry_cat(entry):
    cat = entry.get("category") or entry.get("type") or "Password"
    return _LEGACY_CAT_MAP.get(cat, cat if cat in CATEGORY_DEFS else "Password")

_entry_type    = _entry_cat
_entry_context = lambda e: e.get("context", "Personal")
_entry_subcat  = lambda e: e.get("subcat", "")

def _password_age(entry):
    ts = entry.get("updated_at")
    if not ts: return "Age unknown", MUTED
    try:
        updated = datetime.datetime.fromisoformat(ts)
        days = (datetime.datetime.now() - updated).days
        if days < 30:   return f"Updated {days}d ago", GREEN
        elif days < 90: return f"Updated {days}d ago", "#ffb347"
        else:           return f"Updated {days}d ago  \u26a0", RED
    except Exception:
        return "Age unknown", MUTED

def _entry_subtitle(entry):
    """Generate a descriptive subtitle for card display.
    Keeps the title clean for brand logo matching while showing connection details."""
    cat = _entry_cat(entry)
    parts = []
    if cat == "Server / RDP":
        # User-defined connection label: "Production", "Dev", "UAT", etc.
        label = entry.get("label", "").strip()
        if label:
            parts.append(label)
        else:
            # Fallback: show AVD or host if no label set
            ws = entry.get("workspace", "").strip()
            host = entry.get("host", "").strip()
            if ws: parts.append("AVD")
            elif host: parts.append(host)
    elif cat == "Domain Credential":
        domain = entry.get("domain", "").strip()
        user = entry.get("user", "").strip()
        if domain: parts.append(domain)
        if user: parts.append(user)
    elif cat == "Email Account":
        parts.append(entry.get("user", ""))
    elif cat == "Bank Account":
        parts.append(entry.get("bank_name", ""))
    elif cat == "Credit Card":
        cn = entry.get("card_number", "").strip()
        if len(cn) >= 4:
            parts.append(f"\u2022\u2022\u2022\u2022 {cn[-4:]}")
        ct = entry.get("card_type", "")
        if ct: parts.append(ct)
    return "  \u00b7  ".join(p for p in parts if p)

def _is_light_theme():
    """Check if current theme is light by examining BG luminance."""
    try:
        bg = BG.lstrip("#")
        r,g,b = int(bg[0:2],16), int(bg[2:4],16), int(bg[4:6],16)
        return (r*0.299 + g*0.587 + b*0.114) > 128
    except: return False

def _cat_colors(cat):
    """Return (fg_color, bg_color) for a category, adjusted for theme brightness."""
    d = CATEGORY_DEFS.get(cat, CATEGORY_DEFS["Other"])
    if _is_light_theme():
        # Darken the category color for readability on light backgrounds
        c = d["color"]
        r,g,b = int(c[1:3],16), int(c[3:5],16), int(c[5:7],16)
        # Make 30% darker for better contrast
        r,g,b = max(0,int(r*0.65)), max(0,int(g*0.65)), max(0,int(b*0.65))
        fg = f"#{r:02x}{g:02x}{b:02x}"
        # Light tint background
        bg = SURFACE2
        return fg, bg
    return d["color"], d["bg"]

# == Theme cycling ==========================================================
def _next_theme_name():
    idx = THEME_NAMES.index(_CURRENT_THEME) if _CURRENT_THEME in THEME_NAMES else 0
    return THEME_NAMES[(idx + 1) % len(THEME_NAMES)]

def _apply_theme_by_name(name):
    """Apply a specific theme by name."""
    global _CURRENT_THEME
    if name not in _ALL_PALETTES: return
    _CURRENT_THEME = name
    _apply_palette(_ALL_PALETTES[name])
    _save_theme(name)

def _cycle_theme_global():
    global _CURRENT_THEME
    _CURRENT_THEME = _next_theme_name()
    _apply_palette(_ALL_PALETTES[_CURRENT_THEME])
    _save_theme(_CURRENT_THEME)
    return _CURRENT_THEME

def _show_theme_picker(parent, on_apply):
    """Show a centered theme picker dialog with color preview cards."""
    root = parent.winfo_toplevel()
    picker = tk.Toplevel(root)
    picker.transient(root)
    picker.title("Choose Theme")
    picker.configure(bg=SURFACE)
    picker.resizable(False, False)
    picker.grab_set()
    try:
        _ico = getattr(root, "_ico_path", None)
        if _ico: picker.iconbitmap(_ico)
    except: pass
    _centre_on_parent(picker, root, 580, 480)

    pad = tk.Frame(picker, bg=SURFACE, padx=20, pady=16)
    pad.pack(fill="both", expand=True)

    tk.Label(pad, text="\U0001f3a8  Choose Theme", font=("Segoe UI",13,"bold"),
             fg=TEXT, bg=SURFACE).pack(anchor="w", pady=(0,12))

    # Dark themes section
    tk.Label(pad, text="DARK", font=("Segoe UI",8,"bold"),
             fg=MUTED, bg=SURFACE).pack(anchor="w", pady=(0,4))
    dark_grid = tk.Frame(pad, bg=SURFACE)
    dark_grid.pack(fill="x", pady=(0,12))

    # Light themes section
    tk.Label(pad, text="LIGHT", font=("Segoe UI",8,"bold"),
             fg=MUTED, bg=SURFACE).pack(anchor="w", pady=(0,4))
    light_grid = tk.Frame(pad, bg=SURFACE)
    light_grid.pack(fill="x", pady=(0,8))

    dark_themes = [(n,p) for n,p in _ALL_PALETTES.items() if p.get("_dwm_dark",1)]
    light_themes = [(n,p) for n,p in _ALL_PALETTES.items() if not p.get("_dwm_dark",1)]
    COLS_PER_ROW = 5

    def _build_swatch(parent_frame, name, palette, row, col):
        is_active = (name == _CURRENT_THEME)
        # Fixed-size outer cell prevents layout shift
        cell = tk.Frame(parent_frame, bg=SURFACE, width=100, height=80)
        cell.grid(row=row, column=col, padx=3, pady=3, sticky="nsew")
        cell.pack_propagate(False)
        parent_frame.grid_columnconfigure(col, weight=1, uniform="theme_swatch")

        card = tk.Frame(cell,
                        bg=palette["ACCENT"] if is_active else palette["BORDER"],
                        highlightbackground=palette["ACCENT"] if is_active else palette["BORDER"],
                        highlightthickness=2,
                        cursor="hand2")
        card.pack(fill="both", expand=True)

        inner = tk.Frame(card, bg=palette["BG"], cursor="hand2")
        inner.pack(fill="both", expand=True)

        # Color preview bar
        bar = tk.Frame(inner, bg=palette["BG"], height=28, cursor="hand2")
        bar.pack(fill="x")
        bar.pack_propagate(False)
        for color in [palette["BG"], palette["SURFACE"], palette["SURFACE2"], palette["ACCENT"]]:
            tk.Frame(bar, bg=color, width=28, cursor="hand2").pack(side="left", fill="y", padx=0)
        tk.Frame(inner, bg=palette["ACCENT"], height=3, cursor="hand2").pack(fill="x")

        # Name label
        nm = tk.Label(inner, text=name, font=("Segoe UI",9,"bold" if is_active else "normal"),
                      fg=palette["TEXT"], bg=palette["SURFACE"],
                      padx=8, pady=6, anchor="center", cursor="hand2")
        nm.pack(fill="both", expand=True)
        if is_active:
            tk.Label(inner, text="\u2713 Active", font=("Segoe UI",7),
                     fg=palette["ACCENT"], bg=palette["SURFACE"],
                     cursor="hand2").pack()

        def _pick(n=name):
            picker.grab_release(); picker.destroy()
            on_apply(n)
        # Bind click to EVERY widget in the swatch recursively
        def _bind_all_clicks(widget):
            widget.bind("<Button-1>", lambda e, n=name: _pick(n))
            for child in widget.winfo_children():
                _bind_all_clicks(child)
        _bind_all_clicks(cell)

        # Hover: change border color on the card (cell handles Enter/Leave for full area)
        def _enter(e, c=card, p=palette):
            c.config(bg=p["ACCENT"], highlightbackground=p["ACCENT"])
        def _leave(e, c=card, p=palette, a=is_active):
            c.config(bg=p["ACCENT"] if a else p["BORDER"],
                     highlightbackground=p["ACCENT"] if a else p["BORDER"])
        cell.bind("<Enter>", _enter); cell.bind("<Leave>", _leave)

    for i, (name, palette) in enumerate(dark_themes):
        r, c = divmod(i, COLS_PER_ROW)
        _build_swatch(dark_grid, name, palette, r, c)
    for i, (name, palette) in enumerate(light_themes):
        r, c = divmod(i, COLS_PER_ROW)
        _build_swatch(light_grid, name, palette, r, c)

    # Close button
    mk_btn(pad, "Cancel", lambda: [picker.grab_release(), picker.destroy()],
           bg=SURFACE2, fg=MUTED, w=10).pack(pady=(8,0))

    picker.after(50, lambda: _apply_dwm_to_widget(picker))

# == UI Helpers =============================================================
class Tooltip:
    def __init__(self, widget, text):
        self.widget = widget; self.text = text; self.tip = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)

    def _show(self, e=None):
        x = self.widget.winfo_rootx() + self.widget.winfo_width() // 2
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self.tip = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        border = tk.Frame(tw, bg=ACCENT, padx=1, pady=1)
        border.pack()
        tk.Label(border, text=self.text, font=("Segoe UI", 9),
                 bg=SURFACE2, fg=TEXT, relief="flat", padx=10, pady=5).pack()

    def _hide(self, e=None):
        if self.tip: self.tip.destroy(); self.tip = None

def _lighten(hex_color, amount=30):
    r,g,b = int(hex_color[1:3],16), int(hex_color[3:5],16), int(hex_color[5:7],16)
    return f"#{min(255,r+amount):02x}{min(255,g+amount):02x}{min(255,b+amount):02x}"

def _darken(hex_color, amount=20):
    r,g,b = int(hex_color[1:3],16), int(hex_color[3:5],16), int(hex_color[5:7],16)
    return f"#{max(0,r-amount):02x}{max(0,g-amount):02x}{max(0,b-amount):02x}"

def mk_btn(parent, text, cmd, bg=None, fg="white", w=16, tooltip=None):
    bg = bg or ACCENT
    b = tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg,
                  font=FNT_BTN, relief="flat", cursor="hand2",
                  activebackground=_lighten(bg), activeforeground=fg,
                  padx=16, pady=9, width=w, bd=0, highlightthickness=0)
    b.bind("<Enter>", lambda e: b.config(bg=_lighten(bg)))
    b.bind("<Leave>", lambda e: b.config(bg=bg))
    if tooltip: Tooltip(b, tooltip)
    return b

def mk_entry(parent, var, show=None, mono=False, w=30):
    return tk.Entry(parent, textvariable=var,
                    font=FNT_MONO if mono else FNT_BODY,
                    bg=SURFACE2, fg=TEXT, insertbackground=TEXT,
                    relief="flat", show=show or "", width=w,
                    highlightthickness=1, highlightbackground=BORDER,
                    highlightcolor=ACCENT)

def mk_scrollbar(parent, **kw):
    style = ttk.Style(); style.theme_use("clam")
    style.configure("Dark.Vertical.TScrollbar",
                    background=SURFACE2, troughcolor=SURFACE,
                    bordercolor=SURFACE, arrowcolor=MUTED,
                    darkcolor=SURFACE2, lightcolor=SURFACE2)
    style.map("Dark.Vertical.TScrollbar", background=[("active", ACCENT)])
    return ttk.Scrollbar(parent, style="Dark.Vertical.TScrollbar", **kw)

# == Scroll Router ==========================================================

# == Secure Clipboard ======================================================
def _clipboard_copy_secure(value, widget=None, clear_after=30):
    """Copy value to clipboard excluding from Windows clipboard history.
    clear_after: seconds before auto-clear (0 to disable)."""
    copied = False
    if sys.platform == "win32":
        try:
            u32 = ctypes.windll.user32
            k32 = ctypes.windll.kernel32
            k32.GlobalAlloc.restype = ctypes.c_void_p
            k32.GlobalLock.restype = ctypes.c_void_p
            k32.GlobalLock.argtypes = [ctypes.c_void_p]
            k32.GlobalUnlock.argtypes = [ctypes.c_void_p]
            u32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
            CF_EXCLUDE = u32.RegisterClipboardFormatW(
                "ExcludeClipboardContentFromMonitorProcessing")
            GMEM_MOVEABLE = 0x0002
            enc = (value + "\0").encode("utf-16-le")
            h_text = k32.GlobalAlloc(GMEM_MOVEABLE, len(enc))
            if h_text:
                p = k32.GlobalLock(h_text)
                if p:
                    ctypes.memmove(p, enc, len(enc))
                    k32.GlobalUnlock(h_text)
                    h_ex = k32.GlobalAlloc(GMEM_MOVEABLE, 1)
                    if h_ex:
                        px = k32.GlobalLock(h_ex)
                        if px:
                            ctypes.memset(px, 0, 1)
                            k32.GlobalUnlock(h_ex)
                        if u32.OpenClipboard(0):
                            u32.EmptyClipboard()
                            u32.SetClipboardData(13, h_text)
                            u32.SetClipboardData(CF_EXCLUDE, h_ex)
                            u32.CloseClipboard()
                            copied = True
        except Exception:
            pass
    if not copied:
        if CLIPBOARD_OK:
            pyperclip.copy(value)
        else:
            try:
                r = widget or tk._default_root
                if r: r.clipboard_clear(); r.clipboard_append(value)
            except: pass
    # Auto-clear clipboard
    if clear_after > 0:
        ms = clear_after * 1000
        def _clear():
            try:
                if sys.platform == "win32":
                    if ctypes.windll.user32.OpenClipboard(0):
                        ctypes.windll.user32.EmptyClipboard()
                        ctypes.windll.user32.CloseClipboard()
                elif CLIPBOARD_OK:
                    pyperclip.copy("")
            except: pass
        if widget:
            widget.after(ms, _clear)
        else:
            threading.Timer(clear_after, _clear).start()

# == Scroll Router (continued) ==============================================
# Tracks which scrollable canvas the mouse is currently over.
# A single bind_all routes mousewheel events to the active canvas.
_active_scroll_canvas = [None]   # mutable container so closures can update it
_scroll_router_installed = [False]

def _install_scroll_router(root):
    """Install once on the root window. Routes mousewheel to active canvas."""
    if _scroll_router_installed[0]: return
    def _route_scroll(e):
        c = _active_scroll_canvas[0]
        if c and c.winfo_exists():
            # Only scroll if content overflows the visible area
            bbox = c.bbox("all")
            if bbox:
                content_height = bbox[3] - bbox[1]
                visible_height = c.winfo_height()
                if content_height > visible_height:
                    c.yview_scroll(int(-1*(e.delta/120)), "units")
    root.bind_all("<MouseWheel>", _route_scroll)
    _scroll_router_installed[0] = True

def _make_scrollable(canvas):
    """Register a canvas with the scroll router via Enter/Leave."""
    canvas.bind("<Enter>", lambda e: _active_scroll_canvas.__setitem__(0, canvas))
    canvas.bind("<Leave>", lambda e: _active_scroll_canvas.__setitem__(0, None)
                if _active_scroll_canvas[0] is canvas else None)

# == Lock Screen ============================================================
def _draw_concentric_logo(canvas, cx, cy, size, bg):
    import math
    def pts(rx, ry, n, rot):
        p = []
        for i in range(n):
            a = math.radians(rot + i * 360 / n)
            p.extend([cx + rx * math.cos(a), cy + ry * math.sin(a)])
        return p
    s = size / 60
    canvas.create_polygon(pts(52*s,48*s,7,12), fill="", outline="#2a1f5e", width=1)
    canvas.create_polygon(pts(46*s,42*s,7,22), fill="", outline="#3d2d8a", width=1)
    canvas.create_polygon(pts(39*s,36*s,7,5),  fill="", outline="#5438b0", width=max(1,2*s))
    canvas.create_polygon(pts(31*s,29*s,7,18), fill="", outline=ACCENT,    width=max(1,2*s))
    canvas.create_polygon(pts(22*s,21*s,7,8),  fill="", outline="#9d7fff", width=max(1,2*s))
    canvas.create_polygon(pts(13*s,13*s,7,20), fill="#1e1040", outline="#c4b0ff", width=max(1,1.5*s))
    canvas.create_oval(cx-9*s, cy-9*s, cx+9*s, cy+9*s, fill="#c4b0ff", outline="")
    canvas.create_oval(cx-5*s, cy-5*s, cx+5*s, cy+5*s, fill="#ffffff",  outline="")


class LockScreen(tk.Frame):
    """Lock screen - stores its own vault/meta paths to avoid global path bugs."""

    def __init__(self, master, on_unlock, vault_file=None, meta_file=None):
        super().__init__(master, bg=BG)
        self.on_unlock   = on_unlock
        self.vault_file  = vault_file or VAULT_FILE
        self.meta_file   = meta_file  or META_FILE
        self.pack(fill="both", expand=True)
        self._build()

    def _build(self):
        # About button - top right
        about_btn = tk.Button(self, text="\u2139  About",
                              font=("Segoe UI", 10), bg=SURFACE2, fg=TEXT,
                              relief="flat", cursor="hand2", bd=0,
                              padx=14, pady=8,
                              command=lambda: VaultApp._show_about_static(self.winfo_toplevel()))
        about_btn.place(relx=1.0, rely=0.0, anchor="ne", x=-16, y=16)
        about_btn.bind("<Enter>", lambda e: about_btn.config(bg=ACCENT, fg="white"))
        about_btn.bind("<Leave>", lambda e: about_btn.config(bg=SURFACE2, fg=TEXT))

        # Theme picker - top left
        def _on_theme_pick(name):
            _apply_theme_by_name(name)
            # Save for this vault
            vault_dir = os.path.dirname(self.vault_file)
            _save_vault_theme(vault_dir, name)
            app = self.winfo_toplevel()
            # Update vault entry if accessible
            if hasattr(app, "_vaults") and hasattr(app, "_active_tab"):
                idx = app._active_tab
                if 0 <= idx < len(app._vaults):
                    app._vaults[idx]["theme"] = name
            for w in self.master.winfo_children(): w.destroy()
            app.configure(bg=BG)
            if hasattr(app, "_apply_theme"):
                app._apply_theme()
            LockScreen(self.master, on_unlock=self.on_unlock,
                       vault_file=self.vault_file, meta_file=self.meta_file)
            app.after(30, lambda: _apply_dwm_to_widget(app))

        th_btn = tk.Button(self, text=f"\U0001f3a8  {_CURRENT_THEME}",
                           font=("Segoe UI", 9), bg=SURFACE2, fg=MUTED,
                           relief="flat", cursor="hand2", bd=0,
                           padx=12, pady=6,
                           command=lambda: _show_theme_picker(th_btn, _on_theme_pick))
        th_btn.place(relx=0.0, rely=0.0, anchor="nw", x=16, y=16)
        th_btn.bind("<Enter>", lambda e: th_btn.config(fg=TEXT))
        th_btn.bind("<Leave>", lambda e: th_btn.config(fg=MUTED))

        # Center card
        center = tk.Frame(self, bg=BG)
        center.place(relx=0.5, rely=0.5, anchor="center")

        icon_size = 120
        c = tk.Canvas(center, width=icon_size, height=icon_size,
                      bg=BG, highlightthickness=0)
        c.pack(pady=(0, 10))
        _draw_concentric_logo(c, icon_size/2, icon_size/2, icon_size/2, BG)

        tk.Label(center, text="M  A  R  A  i",
                 font=("Segoe UI", 26, "bold"), fg=ACCENT, bg=BG).pack()
        tk.Label(center, text="Your offline password vault, hidden by design.",
                 font=("Segoe UI", 10, "italic"), fg=MUTED, bg=BG).pack(pady=(4, 24))

        card = tk.Frame(center, bg=SURFACE, padx=40, pady=32,
                        highlightbackground=BORDER, highlightthickness=1)
        card.pack()

        if not vault_exists(self.meta_file, self.vault_file):
            self._build_setup(card)
        else:
            self._build_login(card)

    def _build_login(self, card):
        self._attempts = 0; self._locked_out = False
        tk.Label(card, text="MASTER PASSWORD", font=FNT_SM,
                 fg=MUTED, bg=SURFACE).pack(anchor="w")
        self.pw_var = tk.StringVar()
        self._pw_entry = mk_entry(card, self.pw_var, show="\u25cf", mono=True, w=32)
        self._pw_entry.pack(fill="x", ipady=10, pady=(4,0))
        self._pw_entry.bind("<Return>", lambda _: self._do_login())
        self._pw_entry.focus_set()
        self.err_lbl = tk.Label(card, text="", font=FNT_SM, fg=RED, bg=SURFACE)
        self.err_lbl.pack(pady=(8,0))
        tk.Frame(card, bg=SURFACE, height=12).pack()
        self._unlock_btn = mk_btn(card, "Unlock Vault", self._do_login, bg=ACCENT, fg="white", w=24)
        self._unlock_btn.pack(fill="x")

    def _do_login(self):
        if self._locked_out: return
        pw = self.pw_var.get()
        meta = load_meta(self.meta_file)
        if not meta:
            self.err_lbl.config(text="No vault found."); return
        salt     = base64.b64decode(meta["salt"])
        kdf_used = meta.get("kdf", "pbkdf2")
        try:
            key    = derive_key(pw, salt, kdf=kdf_used)
            verify = base64.b64decode(meta["verify"])
            decrypted = decrypt_data(key, verify)
            if decrypted not in ("MARAI_OK", "VAULTKEY_OK"):
                raise ValueError
            self._attempts = 0
            patch_verify_token_if_needed(key)
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
                    text=f"Incorrect password. {remaining} attempt{'s' if remaining!=1 else ''} remaining.",
                    fg=RED)
            self.pw_var.set("")

    def _upgrade_kdf(self, password, old_key):
        try:
            with open(self.vault_file, "rb") as f: raw = f.read()
            vault_json = decrypt_data(old_key, raw)
            new_salt = secrets.token_bytes(16)
            new_key  = derive_key(password, new_salt, kdf="argon2id")
            with open(self.vault_file, "wb") as f:
                f.write(encrypt_data(new_key, vault_json))
            save_meta(base64.b64encode(new_salt).decode(),
                      base64.b64encode(encrypt_data(new_key, "MARAI_OK")).decode(),
                      kdf="argon2id", meta_file=self.meta_file)
        except Exception: pass

    def _countdown(self, secs):
        if secs > 0:
            self.err_lbl.config(text=f"Too many attempts. Wait {secs}s.", fg="#ffb347")
            self.after(1000, lambda: self._countdown(secs - 1))
        else:
            self._locked_out = False; self._attempts = 0
            self._unlock_btn.config(state="normal")
            self._pw_entry.config(state="normal")
            self.err_lbl.config(text="You may try again.", fg=GREEN)
            self._pw_entry.focus_set()

    def _build_setup(self, card):
        tk.Label(card, text="Welcome! Set up your vault.",
                 font=FNT_BODY, fg=TEXT, bg=SURFACE).pack(pady=(0,16))
        loc_frame = tk.Frame(card, bg=SURFACE)
        loc_frame.pack(fill="x", pady=(0,14))
        tk.Label(loc_frame, text="VAULT LOCATION", font=FNT_SM,
                 fg=MUTED, bg=SURFACE).pack(anchor="w")
        loc_row = tk.Frame(loc_frame, bg=SURFACE)
        loc_row.pack(fill="x", pady=(4,0))
        self._loc_var = tk.StringVar(value=_get_vault_dir())
        tk.Label(loc_row, textvariable=self._loc_var, font=("Segoe UI",8),
                 fg=MUTED, bg=SURFACE2, anchor="w", padx=8, pady=6
                 ).pack(side="left", fill="x", expand=True)
        def _pick():
            from tkinter import filedialog
            d = filedialog.askdirectory(title="Choose vault folder",
                initialdir=_get_vault_dir(), parent=self.winfo_toplevel())
            if d: _set_vault_dir(d); self._loc_var.set(d)
        mk_btn(loc_row, "\U0001f4c2 Browse", _pick, bg=SURFACE2, fg=TEXT, w=10
               ).pack(side="left", padx=(6,0))
        tk.Label(loc_frame, text="Default: user folder. Change to USB for portable use.",
                 font=("Segoe UI",8), fg=MUTED, bg=SURFACE, wraplength=300, justify="left"
                 ).pack(anchor="w", pady=(4,0))
        tk.Frame(card, bg=BORDER, height=1).pack(fill="x", pady=(0,14))
        tk.Label(card, text="MASTER PASSWORD", font=FNT_SM, fg=MUTED, bg=SURFACE).pack(anchor="w")
        self.pw_var = tk.StringVar()
        mk_entry(card, self.pw_var, show="\u25cf", mono=True, w=32).pack(fill="x", ipady=10, pady=(4,14))
        tk.Label(card, text="CONFIRM PASSWORD", font=FNT_SM, fg=MUTED, bg=SURFACE).pack(anchor="w")
        self.conf_var = tk.StringVar()
        e2 = mk_entry(card, self.conf_var, show="\u25cf", mono=True, w=32)
        e2.pack(fill="x", ipady=10, pady=(4,0))
        e2.bind("<Return>", lambda _: self._do_setup())
        self.err_lbl = tk.Label(card, text="", font=FNT_SM, fg=RED, bg=SURFACE)
        self.err_lbl.pack(pady=(8,0))
        tk.Frame(card, bg=SURFACE, height=12).pack()
        mk_btn(card, "Create Vault", self._do_setup, w=24).pack(fill="x")
        tk.Label(card, text="This password encrypts all data.\nThere is no recovery if forgotten.",
                 font=FNT_SM, fg=MUTED, bg=SURFACE, justify="center").pack(pady=(12,0))

    def _do_setup(self):
        pw = self.pw_var.get(); cf = self.conf_var.get()
        if not pw: self.err_lbl.config(text="Password cannot be empty."); return
        if pw != cf: self.err_lbl.config(text="Passwords do not match."); return
        salt = secrets.token_bytes(16)
        key  = derive_key(pw, salt, kdf="argon2id" if ARGON2_OK else "pbkdf2")
        verify_ct = encrypt_data(key, "MARAI_OK")
        save_meta(base64.b64encode(salt).decode(),
                  base64.b64encode(verify_ct).decode(),
                  kdf="argon2id" if ARGON2_OK else "pbkdf2",
                  meta_file=self.meta_file)
        with open(self.vault_file, "wb") as f:
            f.write(encrypt_data(key, json.dumps([])))
        self.on_unlock(key)


# == Password Generator =====================================================
def generate_password(length=16, upper=True, lower=True, digits=True, symbols=True):
    pool = ""; required = []
    if upper: pool += string.ascii_uppercase; required.append(secrets.choice(string.ascii_uppercase))
    if lower: pool += string.ascii_lowercase; required.append(secrets.choice(string.ascii_lowercase))
    if digits: pool += string.digits; required.append(secrets.choice(string.digits))
    if symbols:
        sym = "!@#$%^&*()_+-=[]{}|;:,.<>?"
        pool += sym; required.append(secrets.choice(sym))
    if not pool: pool = string.ascii_letters + string.digits
    remaining = [secrets.choice(pool) for _ in range(length - len(required))]
    pw_list = required + remaining
    secrets.SystemRandom().shuffle(pw_list)
    return "".join(pw_list)

def password_strength(pw):
    score = 0
    if len(pw) >= 8:  score += 1
    if len(pw) >= 12: score += 1
    if len(pw) >= 16: score += 1
    if any(c.isupper() for c in pw): score += 1
    if any(c.islower() for c in pw): score += 1
    if any(c.isdigit() for c in pw): score += 1
    if any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in pw): score += 1
    if score <= 2:   return "Weak",   "#fc5c7d", score/7
    if score <= 4:   return "Fair",   "#ffb347", score/7
    if score <= 5:   return "Good",   "#61dafb", score/7
    return             "Strong", "#4ecca3", score/7

class GeneratorDialog(tk.Toplevel):
    def __init__(self, master, on_use=None):
        super().__init__(master)
        self.transient(master.winfo_toplevel())
        self.on_use = on_use
        self.title("Password Generator"); self.configure(bg=SURFACE)
        self.resizable(False, False); self.grab_set()
        try:
            _ico = getattr(master.winfo_toplevel(), "_ico_path", None)
            if _ico: self.iconbitmap(_ico)
        except Exception: pass
        _centre_on_parent(self, master, 500, 480)
        self._build(); self._generate()
        self.after(50, lambda: _apply_dwm_to_widget(self))

    def _build(self):
        pad = tk.Frame(self, bg=SURFACE, padx=30, pady=24)
        pad.pack(fill="both", expand=True)
        tk.Label(pad, text="\u2699\ufe0f  Password Generator", font=FNT_HEAD,
                 fg=TEXT, bg=SURFACE).pack(anchor="w", pady=(0,20))
        pw_frame = tk.Frame(pad, bg=SURFACE2, highlightbackground=BORDER, highlightthickness=1)
        pw_frame.pack(fill="x", pady=(0,6))
        self.v_pw = tk.StringVar()
        self.pw_lbl = tk.Entry(pw_frame, textvariable=self.v_pw,
                               font=("Consolas",13,"bold"), bg=SURFACE2, fg=GREEN,
                               insertbackground=GREEN, relief="flat",
                               justify="center", state="readonly")
        self.pw_lbl.pack(fill="x", ipady=14, padx=10)
        self.str_lbl = tk.Label(pad, text="", font=FNT_SM, fg=MUTED, bg=SURFACE)
        self.str_lbl.pack(anchor="w")
        bar_bg = tk.Frame(pad, bg=SURFACE2, height=6); bar_bg.pack(fill="x", pady=(2,16))
        bar_bg.pack_propagate(False)
        self.str_bar = tk.Frame(bar_bg, bg=ACCENT, height=6)
        self.str_bar.place(x=0, y=0, relheight=1, relwidth=0)
        tk.Frame(pad, bg=BORDER, height=1).pack(fill="x", pady=(0,14))
        tk.Label(pad, text="LENGTH", font=FNT_SM, fg=MUTED, bg=SURFACE).pack(anchor="w")
        len_row = tk.Frame(pad, bg=SURFACE); len_row.pack(fill="x", pady=(4,14))
        self.v_len = tk.IntVar(value=16)
        self.len_lbl = tk.Label(len_row, text="16", font=("Consolas",12,"bold"),
                                fg=ACCENT, bg=SURFACE, width=3)
        self.len_lbl.pack(side="right")
        tk.Scale(len_row, from_=8, to=48, orient="horizontal", variable=self.v_len,
                 bg=SURFACE, fg=TEXT, troughcolor=SURFACE2, activebackground=ACCENT,
                 highlightthickness=0, showvalue=False, relief="flat",
                 command=self._on_len).pack(side="left", fill="x", expand=True)
        tk.Frame(pad, bg=BORDER, height=1).pack(fill="x", pady=(0,14))
        tk.Label(pad, text="INCLUDE", font=FNT_SM, fg=MUTED, bg=SURFACE).pack(anchor="w", pady=(0,8))
        self.v_upper = tk.BooleanVar(value=True); self.v_lower = tk.BooleanVar(value=True)
        self.v_digits = tk.BooleanVar(value=True); self.v_symbols = tk.BooleanVar(value=True)
        opt_grid = tk.Frame(pad, bg=SURFACE); opt_grid.pack(fill="x", pady=(0,16))
        for i, (lbl, var) in enumerate([("A-Z  Uppercase", self.v_upper),
                ("a-z  Lowercase", self.v_lower), ("0-9  Numbers", self.v_digits),
                ("!@#  Symbols", self.v_symbols)]):
            r,c = divmod(i, 2)
            tk.Checkbutton(opt_grid, text=lbl, variable=var, font=FNT_SM, bg=SURFACE,
                           fg=TEXT, selectcolor=SURFACE2, activebackground=SURFACE,
                           activeforeground=TEXT, relief="flat", cursor="hand2",
                           command=self._generate).grid(row=r, column=c, sticky="w", padx=(0,20), pady=3)
        tk.Frame(pad, bg=BORDER, height=1).pack(fill="x", pady=(0,14))
        btn_row = tk.Frame(pad, bg=SURFACE); btn_row.pack(fill="x")
        mk_btn(btn_row, "\U0001f504 Regenerate", self._generate, bg=SURFACE2, fg=TEXT, w=14).pack(side="left")
        mk_btn(btn_row, "\U0001f4cb Copy", self._copy, bg=SURFACE2, fg=TEXT, w=10).pack(side="left", padx=(8,0))
        if self.on_use:
            mk_btn(btn_row, "Use Password", self._use, w=16).pack(side="right")
        else:
            mk_btn(btn_row, "Close", self.destroy, bg=SURFACE2, fg=MUTED, w=10).pack(side="right")

    def _on_len(self, val): self.len_lbl.config(text=str(val)); self._generate()
    def _generate(self):
        pw = generate_password(self.v_len.get(), self.v_upper.get(), self.v_lower.get(),
                               self.v_digits.get(), self.v_symbols.get())
        self.v_pw.set(pw); self._update_strength(pw)
    def _update_strength(self, pw):
        label, color, ratio = password_strength(pw)
        self.str_lbl.config(text=f"Strength: {label}", fg=color)
        self.str_bar.place(relwidth=ratio); self.str_bar.config(bg=color)
    def _copy(self):
        pw = self.v_pw.get()
        _clipboard_copy_secure(pw, self)
        self.str_lbl.config(text="\u2705  Copied to clipboard!", fg=GREEN)
        self.after(1500, lambda: self._update_strength(self.v_pw.get()))
    def _use(self):
        if self.on_use: self.on_use(self.v_pw.get())
        self.destroy()


# == Category-specific field definitions ====================================
_CATEGORY_FIELDS = {
    "Password": [
        ("TITLE", "name", {}),
        ("USERNAME / EMAIL", "user", {}),
        ("PASSWORD", "password", {"show": "\u25cf", "mono": True, "gen": True}),
        ("URL (optional)", "url", {}),
        ("NOTES", "notes", {}),
    ],
    "Bank Account": [
        ("LABEL", "name", {}),
        ("BANK NAME", "bank_name", {}),
        ("ACCOUNT HOLDER", "user", {}),
        ("ACCOUNT NUMBER", "account_number", {"mono": True}),
        ("IFSC CODE", "ifsc", {"mono": True}),
        ("CUSTOMER ID", "customer_id", {"mono": True}),
        ("PROFILE PASSWORD", "password", {"show": "\u25cf", "mono": True, "gen": True}),
        ("APP PIN", "app_pin", {"show": "\u25cf", "mono": True}),
        ("ONLINE BANKING URL", "url", {}),
        ("NOTES", "notes", {}),
    ],
    "Credit Card": [
        ("TITLE", "name", {}),
        ("CARDHOLDER NAME", "user", {}),
        ("CARD NUMBER", "card_number", {"mono": True}),
        ("EXPIRY (MM/YY)", "expiry", {"mono": True}),
        ("CVV", "password", {"show": "\u25cf", "mono": True}),
        ("PIN", "pin", {"show": "\u25cf", "mono": True}),
        ("ISSUING BANK", "bank_name", {}),
        ("CARD TYPE", "card_type", {"default": "Visa"}),
        ("BILLING ADDRESS", "address", {}),
        ("NOTES", "notes", {}),
    ],
    "Email Account": [
        ("TITLE", "name", {}),
        ("EMAIL ADDRESS", "user", {}),
        ("PASSWORD", "password", {"show": "\u25cf", "mono": True, "gen": True}),
        ("PROVIDER", "provider", {"default": "Gmail"}),
        ("IMAP SERVER", "imap", {}),
        ("SMTP SERVER", "smtp", {}),
        ("RECOVERY EMAIL", "recovery_email", {}),
        ("RECOVERY PHONE", "recovery_phone", {}),
        ("URL", "url", {}),
        ("NOTES", "notes", {}),
    ],
    "Secure Note": [
        ("TITLE", "name", {}),
        ("NOTE CONTENT", "body", {"multiline": True}),
    ],
    "Domain Credential": [
        ("TITLE", "name", {}),
        ("LABEL", "label", {}),
        ("DOMAIN", "domain", {}),
        ("USERNAME", "user", {}),
        ("PASSWORD", "password", {"show": "\u25cf", "mono": True, "gen": True}),
        ("NOTES", "notes", {}),
    ],
    "Server / RDP": [
        ("TITLE", "name", {}),
        ("CONNECTION LABEL", "label", {}),
        ("LINKED CREDENTIAL", "credential_ref", {"type": "credential_ref"}),
        ("USERNAME (if no linked credential)", "user", {}),
        ("PASSWORD (if no linked credential)", "password", {"show": "\u25cf", "mono": True, "gen": True}),
        ("HOST / IP ADDRESS", "host", {}),
        ("PORT", "port", {"default": "3389", "width": 8}),
        ("AVD WORKSPACE URL", "workspace", {}),
        ("NOTES", "notes", {}),
    ],
    "SSH Key": [
        ("TITLE", "name", {}),
        ("USERNAME", "user", {}),
        ("HOST / IP", "host", {}),
        ("PORT", "port", {"default": "22", "width": 8}),
        ("PASSPHRASE", "password", {"show": "\u25cf", "mono": True}),
        ("PRIVATE KEY", "private_key", {"multiline": True}),
        ("PUBLIC KEY", "public_key", {"multiline": True}),
        ("NOTES", "notes", {}),
    ],
    "Identity": [
        ("TITLE", "name", {}),
        ("FULL NAME", "user", {}),
        ("DATE OF BIRTH", "dob", {}),
        ("ID TYPE", "id_type", {"default": "Passport"}),
        ("ID NUMBER", "id_number", {"mono": True}),
        ("ISSUING AUTHORITY", "issuer", {}),
        ("ISSUE DATE", "issue_date", {}),
        ("EXPIRY DATE", "expiry", {}),
        ("ADDRESS", "address", {}),
        ("PHONE", "phone", {}),
        ("NOTES", "notes", {}),
    ],
    "Wi-Fi Password": [
        ("TITLE", "name", {}),
        ("NETWORK NAME (SSID)", "user", {}),
        ("PASSWORD", "password", {"show": "\u25cf", "mono": True, "gen": True}),
        ("SECURITY TYPE", "security", {"default": "WPA2"}),
        ("ROUTER IP", "host", {}),
        ("ROUTER ADMIN USER", "admin_user", {}),
        ("ROUTER ADMIN PASS", "admin_pass", {"show": "\u25cf", "mono": True}),
        ("NOTES", "notes", {}),
    ],
    "Software License": [
        ("TITLE", "name", {}),
        ("SOFTWARE NAME", "user", {}),
        ("LICENSE KEY", "password", {"mono": True}),
        ("VERSION", "version", {}),
        ("LICENSED TO", "licensed_to", {}),
        ("EMAIL", "email", {}),
        ("PURCHASE DATE", "purchase_date", {}),
        ("EXPIRY DATE", "expiry", {}),
        ("URL", "url", {}),
        ("NOTES", "notes", {}),
    ],
    "Other": [
        ("TITLE", "name", {}),
        ("USERNAME / EMAIL", "user", {}),
        ("PASSWORD", "password", {"show": "\u25cf", "mono": True, "gen": True}),
        ("URL (optional)", "url", {}),
        ("NOTES", "notes", {}),
    ],
}


# == Entry Dialog with dynamic category forms ===============================
class EntryDialog(tk.Toplevel):
    def __init__(self, master, on_save, entry=None, vault=None):
        super().__init__(master)
        self.transient(master.winfo_toplevel())
        self.on_save = on_save; self.entry = entry
        self._vault = vault or []
        self.title("Edit Entry" if entry else "New Entry")
        self.configure(bg=SURFACE); self.resizable(True, True); self.grab_set()
        try:
            _ico = getattr(master.winfo_toplevel(), "_ico_path", None)
            if _ico: self.iconbitmap(_ico)
        except Exception: pass
        _centre_on_parent(self, master, 540, 720)
        self.minsize(440, 500)
        self._field_vars = {}; self._field_texts = {}; self._pw_entries = {}
        self._build()
        self.after(50, lambda: _apply_dwm_to_widget(self))

    def _build(self):
        canvas = tk.Canvas(self, bg=SURFACE, highlightthickness=0)
        sb = ttk.Scrollbar(self, orient="vertical", command=canvas.yview,
                           style="Dark.Vertical.TScrollbar")
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y"); canvas.pack(side="left", fill="both", expand=True)
        pad = tk.Frame(canvas, bg=SURFACE, padx=30, pady=24)
        win_id = canvas.create_window((0,0), window=pad, anchor="nw")
        pad.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win_id, width=e.width))
        _install_scroll_router(self.winfo_toplevel())
        _make_scrollable(canvas)

        tk.Label(pad, text="\u270f\ufe0f  Edit Entry" if self.entry else "\U0001f5dd\ufe0f  New Entry",
                 font=FNT_HEAD, fg=TEXT, bg=SURFACE).pack(anchor="w", pady=(0,18))
        g = self.entry or {}
        self.v_type = tk.StringVar(value=_entry_cat(g) if g else "Password")
        self.v_context = tk.StringVar(value=_entry_context(g) if g else "Work")

        # Category grid
        tk.Label(pad, text="CATEGORY", font=FNT_SM, fg=MUTED, bg=SURFACE).pack(anchor="w")
        cat_grid = tk.Frame(pad, bg=SURFACE); cat_grid.pack(fill="x", pady=(4,14))
        self._cat_btns = {}
        for ci, cat_name in enumerate(CATEGORIES):
            r,c = divmod(ci, 4)
            d = CATEGORY_DEFS[cat_name]
            cat_fg, _ = _cat_colors(cat_name)
            btn = tk.Button(cat_grid, text=f"{d['emoji']}  {cat_name}",
                            font=("Segoe UI",9), bg=SURFACE2, fg=cat_fg,
                            relief="flat", cursor="hand2", bd=0, padx=8, pady=6,
                            command=lambda n=cat_name: self._select_cat(n))
            btn.grid(row=r, column=c, padx=3, pady=3, sticky="ew")
            cat_grid.grid_columnconfigure(c, weight=1)
            self._cat_btns[cat_name] = btn
        self._update_cat_btns()

        # Context — large toggle buttons
        tk.Label(pad, text="CONTEXT", font=FNT_SM, fg=MUTED, bg=SURFACE).pack(anchor="w")
        ctx_f = tk.Frame(pad, bg=SURFACE); ctx_f.pack(anchor="w", fill="x", pady=(4,14))
        self._ctx_toggle_btns = {}
        for ctx in CONTEXTS:
            fg_c, bg_ = CONTEXT_COLORS[ctx]
            b = tk.Button(ctx_f, text=f"  {CONTEXT_EMOJI[ctx]}  {ctx}  ",
                          font=("Segoe UI",11), bg=SURFACE2, fg=fg_c,
                          relief="flat", cursor="hand2", bd=0,
                          padx=20, pady=10,
                          command=lambda c=ctx: self._pick_context(c))
            b.pack(side="left", padx=(0,10))
            self._ctx_toggle_btns[ctx] = b
        self._update_ctx_toggle()

        # Custom icon picker
        tk.Label(pad, text="ICON", font=FNT_SM, fg=MUTED, bg=SURFACE).pack(anchor="w")
        self._icon_row = tk.Frame(pad, bg=SURFACE); self._icon_row.pack(fill="x", pady=(4,14))
        g = self.entry or {}
        self._custom_icon_b64 = g.get("custom_icon_b64", "")
        self._rebuild_icon_row()

        tk.Frame(pad, bg=BORDER, height=1).pack(fill="x", pady=(0,14))

        # Dynamic fields
        self._fields_frame = tk.Frame(pad, bg=SURFACE)
        self._fields_frame.pack(fill="x")
        self._build_fields_for_category()

        tk.Frame(pad, bg=SURFACE, height=8).pack()
        btn_row = tk.Frame(pad, bg=SURFACE); btn_row.pack(fill="x", pady=(6,0))
        mk_btn(btn_row, "Cancel", self.destroy, bg=SURFACE2, fg=MUTED, w=12).pack(side="left")
        mk_btn(btn_row, "Save Entry", self._save, w=16).pack(side="right")

    def _select_cat(self, name):
        self.v_type.set(name); self._update_cat_btns()
        self._build_fields_for_category()

    def _update_cat_btns(self):
        cur = self.v_type.get()
        for name, btn in self._cat_btns.items():
            fg_c, _ = _cat_colors(name)
            btn.config(bg=ACCENT if name==cur else SURFACE2,
                       fg="white" if name==cur else fg_c)

    def _pick_context(self, ctx):
        self.v_context.set(ctx)
        self._update_ctx_toggle()

    def _update_ctx_toggle(self):
        cur = self.v_context.get()
        for ctx, btn in self._ctx_toggle_btns.items():
            fg_c, _ = CONTEXT_COLORS[ctx]
            if ctx == cur:
                btn.config(bg=fg_c, fg="white")
            else:
                btn.config(bg=SURFACE2, fg=fg_c)

    def _rebuild_icon_row(self):
        """Rebuild the icon picker row to reflect current state."""
        for w in self._icon_row.winfo_children(): w.destroy()
        preview = tk.Label(self._icon_row, text="\U0001f5bc", font=("Segoe UI",16),
                           bg=SURFACE2, fg=MUTED, padx=12, pady=8)
        preview.pack(side="left")
        if self._custom_icon_b64:
            try:
                import base64 as _b64
                png_data = _b64.b64decode(self._custom_icon_b64)
                if _PIL_OK:
                    img = _resize_icon_pil(png_data, 40)
                    if img:
                        preview.config(image=img, text="")
                        preview._img = img
                else:
                    full = tk.PhotoImage(data=self._custom_icon_b64)
                    w = full.width()
                    small = full.subsample(max(1, w // 40)) if w > 48 else full
                    preview.config(image=small, text="")
                    preview._img = small; preview._full = full
            except Exception:
                preview.config(text="\u26a0", image="")
        tk.Button(self._icon_row, text="\U0001f4c2  Choose Icon", font=FNT_SM,
                  bg=SURFACE2, fg=TEXT, relief="flat", cursor="hand2", bd=0,
                  padx=10, pady=6,
                  command=self._pick_icon).pack(side="left", padx=(8,0))
        if self._custom_icon_b64:
            tk.Button(self._icon_row, text="\u2715 Clear", font=FNT_SM,
                      bg=SURFACE2, fg=RED, relief="flat", cursor="hand2", bd=0,
                      padx=8, pady=6,
                      command=self._clear_icon).pack(side="left", padx=(6,0))
        tk.Label(self._icon_row, text="Auto-detected from URL or name if not set",
                 font=("Segoe UI",8), fg=MUTED, bg=SURFACE).pack(side="left", padx=(10,0))

    def _pick_icon(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="Choose Icon Image",
            filetypes=[("Images", "*.png *.gif"), ("PNG", "*.png"), ("GIF", "*.gif")],
            parent=self)
        if not path: return
        try:
            with open(path, "rb") as f:
                data = f.read()
            import base64 as _b64
            self._custom_icon_b64 = _b64.b64encode(data).decode()
            self._rebuild_icon_row()
        except Exception as e:
            messagebox.showerror("Error", f"Could not load image:\n{e}", parent=self)

    def _clear_icon(self):
        self._custom_icon_b64 = ""
        self._rebuild_icon_row()

    def _build_fields_for_category(self):
        for w in self._fields_frame.winfo_children(): w.destroy()
        self._field_vars.clear(); self._field_texts.clear(); self._pw_entries.clear()
        cat = self.v_type.get()
        fields = _CATEGORY_FIELDS.get(cat, _CATEGORY_FIELDS["Password"])
        g = self.entry or {}

        for label, key, opts in fields:
            tk.Label(self._fields_frame, text=label, font=FNT_SM,
                     fg=MUTED, bg=SURFACE).pack(anchor="w", pady=(4,0))

            if opts.get("multiline"):
                txt = tk.Text(self._fields_frame, font=FNT_BODY, bg=SURFACE2, fg=TEXT,
                              insertbackground=TEXT, relief="flat", wrap="word", height=8,
                              padx=10, pady=8, highlightbackground=BORDER, highlightthickness=1)
                txt.pack(fill="x", pady=(4,10))
                if g.get(key): txt.insert("1.0", g[key])
                self._field_texts[key] = txt
                continue

            if opts.get("type") == "credential_ref":
                # Dropdown listing all Domain Credential entries
                cred_names = ["(none - enter manually below)"]
                for v in self._vault:
                    if _entry_cat(v) == "Domain Credential" and v.get("name"):
                        domain_label = v.get("domain", "").strip()
                        user_label = v.get("user", "").strip()
                        suffix = ""
                        if domain_label and user_label:
                            suffix = f"  ({domain_label} / {user_label})"
                        elif domain_label:
                            suffix = f"  ({domain_label})"
                        elif user_label:
                            suffix = f"  ({user_label})"
                        display = f"{v['name']}" + suffix
                        cred_names.append(display)
                self._cred_name_map = {}  # display -> entry name
                for v in self._vault:
                    if _entry_cat(v) == "Domain Credential" and v.get("name"):
                        domain_label = v.get("domain", "").strip()
                        user_label = v.get("user", "").strip()
                        suffix = ""
                        if domain_label and user_label:
                            suffix = f"  ({domain_label} / {user_label})"
                        elif domain_label:
                            suffix = f"  ({domain_label})"
                        elif user_label:
                            suffix = f"  ({user_label})"
                        display = f"{v['name']}" + suffix
                        self._cred_name_map[display] = v["name"]
                current_ref = g.get(key, "")
                # Find the display name for current ref
                current_display = "(none - enter manually below)"
                for disp, nm in self._cred_name_map.items():
                    if nm == current_ref:
                        current_display = disp; break
                var = tk.StringVar(value=current_display)
                self._field_vars[key] = var
                dd_frame = tk.Frame(self._fields_frame, bg=SURFACE)
                dd_frame.pack(fill="x", pady=(4,10))
                dd = ttk.Combobox(dd_frame, textvariable=var, values=cred_names,
                                  font=FNT_BODY, state="readonly", width=40)
                dd.pack(fill="x", ipady=6)
                # Style the combobox
                style = ttk.Style()
                style.configure("Cred.TCombobox", fieldbackground=SURFACE2,
                                background=SURFACE2, foreground=TEXT)
                dd.configure(style="Cred.TCombobox")
                if current_ref:
                    tk.Label(dd_frame, text=f"\U0001f517 Linked to: {current_ref}",
                             font=("Segoe UI",8,"bold"), fg=ACCENT, bg=SURFACE).pack(anchor="w", pady=(4,0))
                elif len(cred_names) == 1:
                    tk.Label(dd_frame, text="No domain credentials saved yet. Create one first.",
                             font=("Segoe UI",8), fg=MUTED, bg=SURFACE).pack(anchor="w", pady=(4,0))
                else:
                    tk.Label(dd_frame, text="Link to a domain credential or enter credentials below.",
                             font=("Segoe UI",8), fg=MUTED, bg=SURFACE).pack(anchor="w", pady=(4,0))
                continue

            default = opts.get("default", "")
            var = tk.StringVar(value=g.get(key, default))
            self._field_vars[key] = var
            show = opts.get("show"); mono = opts.get("mono", False)
            width = opts.get("width", 38)

            if show or opts.get("gen"):
                pw_row = tk.Frame(self._fields_frame, bg=SURFACE)
                pw_row.pack(fill="x", pady=(4,4))
                ent = mk_entry(pw_row, var, show=show, mono=mono, w=width-10)
                ent.pack(side="left", fill="x", expand=True, ipady=9)
                self._pw_entries[key] = ent
                if show:
                    _shown = [False]
                    def _toggle(e=ent, s=_shown):
                        s[0] = not s[0]; e.config(show="" if s[0] else "\u25cf")
                    tk.Button(pw_row, text="\U0001f441", font=FNT_SM, bg=SURFACE2, fg=MUTED,
                              relief="flat", cursor="hand2", bd=0,
                              command=_toggle).pack(side="left", padx=(6,0), ipady=9, ipadx=6)
                if opts.get("gen"):
                    def _open_gen(v=var):
                        GeneratorDialog(self, on_use=lambda pw: v.set(pw))
                    tk.Button(pw_row, text="\u2699\ufe0f Generate", font=FNT_SM,
                              bg=ACCENT, fg="white", relief="flat", cursor="hand2",
                              bd=0, padx=8, command=_open_gen
                              ).pack(side="left", padx=(6,0), ipady=9)
                if show and key == "password":
                    str_row = tk.Frame(self._fields_frame, bg=SURFACE)
                    str_row.pack(fill="x", pady=(2,10))
                    str_lbl = tk.Label(str_row, text="", font=FNT_SM, fg=MUTED, bg=SURFACE)
                    str_lbl.pack(side="left")
                    bar_bg = tk.Frame(str_row, bg=SURFACE2, height=5, width=160)
                    bar_bg.pack(side="right"); bar_bg.pack_propagate(False)
                    str_bar = tk.Frame(bar_bg, bg=ACCENT, height=5)
                    str_bar.place(x=0, y=0, relheight=1, relwidth=0)
                    def _upd(event=None, v=var, sl=str_lbl, sb=str_bar):
                        pw = v.get()
                        if not pw: sl.config(text=""); sb.place(relwidth=0); return
                        lb, col, ratio = password_strength(pw)
                        sl.config(text=f"Strength: {lb}", fg=col)
                        sb.place(relwidth=ratio); sb.config(bg=col)
                    ent.bind("<KeyRelease>", _upd); _upd()
                else:
                    tk.Frame(self._fields_frame, bg=SURFACE, height=6).pack()
            else:
                mk_entry(self._fields_frame, var, mono=mono, w=width
                         ).pack(fill="x", ipady=9, pady=(4,10))

    def _save(self):
        cat = self.v_type.get(); ctx = self.v_context.get()
        fields = _CATEGORY_FIELDS.get(cat, _CATEGORY_FIELDS["Password"])
        result = {}
        for label, key, opts in fields:
            if key in self._field_texts:
                result[key] = self._field_texts[key].get("1.0","end-1c").strip()
            elif key in self._field_vars:
                result[key] = self._field_vars[key].get().strip()
        if not result.get("name","").strip():
            missing_label = "A label is required." if cat == "Bank Account" else "A title is required."
            messagebox.showwarning("Missing", missing_label, parent=self); return
        existing_pw = (self.entry or {}).get("password","")
        now_ts = datetime.datetime.now().isoformat(timespec="seconds")
        new_pw = result.get("password","")
        result["type"] = cat; result["context"] = ctx; result["category"] = cat
        result["subcat"] = cat
        result["updated_at"] = now_ts if (new_pw != existing_pw or not self.entry) else (self.entry or {}).get("updated_at", now_ts)
        result["favourite"] = (self.entry or {}).get("favourite", False)
        # Custom icon - set explicitly so merge loop won't re-add old value
        result["custom_icon_b64"] = self._custom_icon_b64
        # Resolve credential_ref from display name to entry name
        if "credential_ref" in result:
            display = result["credential_ref"]
            if hasattr(self, "_cred_name_map") and display in self._cred_name_map:
                result["credential_ref"] = self._cred_name_map[display]
            elif display.startswith("(none"):
                result["credential_ref"] = ""
        if self.entry:
            for k,v in self.entry.items():
                if k not in result: result[k] = v
        self.on_save(result); self.destroy()


# == Main Vault UI ==========================================================
class VaultApp(tk.Frame):
    def __init__(self, master, key, on_lock, vault_file=None, meta_file=None):
        super().__init__(master, bg=BG)
        self.key = key; self.on_lock = on_lock
        self.vault_file = vault_file or VAULT_FILE
        self.meta_file  = meta_file  or META_FILE
        self.vault = []; self.pw_visible = {}
        self._view_mode = _get_saved_view_mode()
        self._active_subcat = "All"; self._detail_idx = None
        self._auto_lock_job = None; self._AUTO_LOCK_SECS = 180
        self._last_activity = _time.time()
        self._load_vault(); self.pack(fill="both", expand=True)
        self._build_ui(); self._render()
        self._reset_auto_lock()
        root = self.winfo_toplevel()
        for ev in ("<Motion>", "<KeyPress>", "<ButtonPress>", "<MouseWheel>"):
            root.bind_all(ev, lambda e: self._on_activity(), add="+")
        check_for_update(self._on_update_found)

    def _load_vault(self):
        if not os.path.exists(self.vault_file): return
        with open(self.vault_file, "rb") as f: raw = f.read()
        self.vault = json.loads(decrypt_data(self.key, raw))
        now_ts = datetime.datetime.now().isoformat(timespec="seconds")
        changed = False
        for entry in self.vault:
            if not entry.get("updated_at"):
                entry["updated_at"] = now_ts; changed = True
        if changed: self._save_vault()

    def _save_vault(self):
        with open(self.vault_file, "wb") as f:
            f.write(encrypt_data(self.key, json.dumps(self.vault)))

    def _build_ui(self):
        # Header
        hdr = tk.Frame(self, bg=SURFACE, pady=12,
                       highlightbackground=BORDER, highlightthickness=1)
        hdr.pack(fill="x")
        left = tk.Frame(hdr, bg=SURFACE); left.pack(side="left", padx=20)
        tk.Label(left, text="MARAi", font=("Segoe UI",15,"bold"),
                 fg=ACCENT, bg=SURFACE).pack(side="left")
        tk.Label(left, text=f"v{VERSION}", font=("Consolas",9),
                 fg=MUTED, bg=SURFACE).pack(side="left", padx=(8,0), pady=(4,0))
        right = tk.Frame(hdr, bg=SURFACE); right.pack(side="right", padx=20)
        self.count_lbl = tk.Label(right, text="", font=FNT_SM, fg=MUTED, bg=SURFACE)
        self.count_lbl.pack(side="left", padx=(0,10))
        # Lock timer - updates every 1 second
        self.lock_timer_lbl = tk.Label(right, text="", font=("Consolas",9), fg=MUTED, bg=SURFACE)
        self.lock_timer_lbl.pack(side="left", padx=(0,10))
        self._update_lock_timer_display()
        mk_btn(right, "+ Add Entry", self._add_entry, w=12).pack(side="left", padx=(0,8))
        mk_btn(right, "\u2699\ufe0f Generate", self._open_generator, bg=SURFACE2, fg=TEXT, w=12
               ).pack(side="left", padx=(0,4))
        # Theme picker
        self._theme_btn = mk_btn(right, f"\U0001f3a8 {_CURRENT_THEME}", self._open_theme_picker,
                                 bg=SURFACE2, fg=MUTED, w=10, tooltip="Choose theme")
        self._theme_btn.pack(side="left", padx=(0,4))
        mk_btn(right, "\U0001f511", self._change_password, bg=SURFACE2, fg=MUTED, w=3,
               tooltip="Change Master Password").pack(side="left", padx=(0,4))
        mk_btn(right, "\u2139", self._show_about, bg=SURFACE2, fg=MUTED, w=3,
               tooltip="About MARAi").pack(side="left", padx=(0,4))
        mk_btn(right, "\U0001f512", self.on_lock, bg=SURFACE2, fg=MUTED, w=3,
               tooltip="Lock Vault").pack(side="left")

        # Update banner
        self._update_banner = tk.Frame(self, bg="#1a2a10",
                                       highlightbackground="#4ecca3", highlightthickness=1)
        self._update_lbl = tk.Label(self._update_banner, text="", font=FNT_SM,
                                    fg="#4ecca3", bg="#1a2a10")
        self._update_lbl.pack(side="left", padx=16, pady=8)
        tk.Button(self._update_banner, text="Download",
                  font=("Segoe UI",9,"bold"), bg="#4ecca3", fg="#0a0a0a",
                  relief="flat", cursor="hand2", padx=10, pady=4,
                  command=lambda: webbrowser.open(RELEASES_URL)
                  ).pack(side="right", padx=16, pady=6)
        tk.Button(self._update_banner, text="\u2715", font=FNT_SM,
                  bg="#1a2a10", fg="#4ecca3", relief="flat", cursor="hand2", bd=0,
                  command=self._dismiss_update_banner).pack(side="right", padx=(0,4))

        # Toolbar
        toolbar = tk.Frame(self, bg=BG); toolbar.pack(fill="x", padx=20, pady=(12,6))
        wrap = tk.Frame(toolbar, bg=SURFACE2, highlightbackground=BORDER, highlightthickness=1)
        wrap.pack(side="left", fill="x", expand=True)
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._render())
        tk.Label(wrap, text="\U0001f50d", font=FNT_BODY, bg=SURFACE2, fg=MUTED
                 ).pack(side="left", padx=(10,4))
        tk.Entry(wrap, textvariable=self.search_var, font=FNT_BODY,
                 bg=SURFACE2, fg=TEXT, insertbackground=TEXT,
                 relief="flat").pack(side="left", fill="x", expand=True, ipady=9)

        # Context multi-select toggles — right of search bar
        self._ctx_active = set(CONTEXTS)  # both on by default
        ctx_toggle = tk.Frame(toolbar, bg=BG); ctx_toggle.pack(side="left", padx=(10,0))
        self._ctx_toggle_buttons = {}
        for ctx in CONTEXTS:
            fg_c, _ = CONTEXT_COLORS[ctx]
            b = tk.Button(ctx_toggle, text="", font=("Segoe UI",9),
                          relief="flat", cursor="hand2", bd=0,
                          padx=10, pady=6,
                          command=lambda c=ctx: self._toggle_ctx(c))
            b.pack(side="left", padx=2)
            self._ctx_toggle_buttons[ctx] = b
        self._update_ctx_toggles()

        vm_frame = tk.Frame(toolbar, bg=BG); vm_frame.pack(side="right", padx=(10,0))
        self._vm_btns = {}
        for mode, icon, tip in [("list","\u2261","List"),("small","\u229e","Small"),
                                ("medium","\u25a6","Medium"),("large","\u25a1","Large")]:
            b = tk.Button(vm_frame, text=icon, font=("Segoe UI",11), relief="flat",
                          cursor="hand2", bd=0, padx=8, pady=5,
                          command=lambda m=mode: self._set_view_mode(m))
            b.pack(side="left", padx=2); self._vm_btns[mode] = b; Tooltip(b, tip)
        self._update_vm_btns()

        # Zoom controls
        self._zoom = _get_zoom_level()
        zoom_frame = tk.Frame(toolbar, bg=BG); zoom_frame.pack(side="right", padx=(6,0))
        tk.Button(zoom_frame, text="\u2212", font=("Segoe UI",11,"bold"), bg=SURFACE2, fg=TEXT,
                  relief="flat", cursor="hand2", bd=0, padx=6, pady=3,
                  command=lambda: self._set_zoom(-20)).pack(side="left")
        self._zoom_lbl = tk.Label(zoom_frame, text=f"{self._zoom}%", font=("Consolas",9),
                                   fg=MUTED, bg=BG, width=4)
        self._zoom_lbl.pack(side="left", padx=2)
        tk.Button(zoom_frame, text="+", font=("Segoe UI",11,"bold"), bg=SURFACE2, fg=TEXT,
                  relief="flat", cursor="hand2", bd=0, padx=6, pady=3,
                  command=lambda: self._set_zoom(20)).pack(side="left")

        ie_frame = tk.Frame(toolbar, bg=BG); ie_frame.pack(side="right", padx=(0,6))
        mk_btn(ie_frame, "\u2b06 Export", self._export_vault, bg=SURFACE2, fg=TEXT, w=9,
               tooltip="Export (JSON/CSV)").pack(side="left", padx=(0,4))
        mk_btn(ie_frame, "\u2b07 Import", self._import_vault, bg=SURFACE2, fg=TEXT, w=9,
               tooltip="Import (JSON/CSV)").pack(side="left", padx=(0,4))
        mk_btn(ie_frame, "\U0001f4be Backup", self._backup_vault, bg=SURFACE2, fg=TEXT, w=9,
               tooltip="Encrypted backup").pack(side="left")

        # Filters
        self.active_type = tk.StringVar(value="All")
        ff = tk.Frame(self, bg=BG); ff.pack(fill="x", padx=20, pady=(0,10))

        # Category row only
        type_row = tk.Frame(ff, bg=BG); type_row.pack(anchor="w")
        self._type_btns = {}
        for t in ["All"] + CATEGORIES:
            label = t if t=="All" else f"{TYPE_EMOJI.get(t,'')} {t}"
            btn = tk.Button(type_row, text=label, font=("Segoe UI",9),
                            relief="flat", cursor="hand2", bd=0, padx=10, pady=4,
                            command=lambda c=t: self._set_type_filter(c))
            btn.pack(side="left", padx=(0,4)); self._type_btns[t] = btn
        self._update_filter_btns()

        # Content area
        content = tk.Frame(self, bg=BG); content.pack(fill="both", expand=True)
        content.grid_columnconfigure(0, weight=1)
        content.grid_columnconfigure(1, weight=0)
        content.grid_rowconfigure(0, weight=1)
        cards_outer = tk.Frame(content, bg=BG)
        cards_outer.grid(row=0, column=0, sticky="nsew")
        self.canvas = tk.Canvas(cards_outer, bg=BG, highlightthickness=0)
        sb = mk_scrollbar(cards_outer, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.cards_frame = tk.Frame(self.canvas, bg=BG)
        self._cw = self.canvas.create_window((0,0), window=self.cards_frame, anchor="nw")
        self._resize_job = None; self._last_canvas_width = 0
        self.cards_frame.bind("<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", self._on_canvas_resize)
        _install_scroll_router(self.winfo_toplevel())
        _make_scrollable(self.canvas)
        self._detail_container = content; self._detail_panel = None

    # -- Filter/View helpers ------------------------------------------------
    def _set_type_filter(self, t):
        self.active_type.set(t); self._update_filter_btns(); self._render()
    def _toggle_ctx(self, ctx):
        """Toggle a context on/off. If both would be off, turn the other one on."""
        if ctx in self._ctx_active:
            if len(self._ctx_active) > 1:
                self._ctx_active.discard(ctx)
            # Don't allow empty — keep at least one
        else:
            self._ctx_active.add(ctx)
        self._update_ctx_toggles(); self._render()
    def _update_ctx_toggles(self):
        for ctx, btn in self._ctx_toggle_buttons.items():
            fg_c, _ = CONTEXT_COLORS[ctx]
            emoji = CONTEXT_EMOJI.get(ctx, '')
            if ctx in self._ctx_active:
                btn.config(text=f"\u2713 {emoji} {ctx}", bg=fg_c, fg="white",
                           font=("Segoe UI",9,"bold"))
            else:
                btn.config(text=f"    {ctx}    ", bg=BG, fg=BORDER,
                           font=("Segoe UI",9))
    def _update_filter_btns(self):
        at = self.active_type.get()
        for t, btn in self._type_btns.items():
            btn.config(bg=ACCENT if t==at else SURFACE2,
                       fg="white" if t==at else _cat_colors(t)[0] if t!="All" else MUTED)
    def _set_view_mode(self, mode):
        self._view_mode = mode; _save_view_mode(mode)
        self._close_detail()
        self._update_vm_btns(); self._render()
    def _set_zoom(self, delta):
        self._zoom = max(60, min(180, self._zoom + delta))
        _save_zoom_level(self._zoom)
        self._zoom_lbl.config(text=f"{self._zoom}%")
        self._render()
    def _zoom_scale(self, base):
        """Scale a base value by the current zoom factor."""
        return max(1, int(base * self._zoom / 100))
    def _update_vm_btns(self):
        for mode, btn in self._vm_btns.items():
            btn.config(bg=ACCENT if mode==self._view_mode else SURFACE2,
                       fg="white" if mode==self._view_mode else MUTED)
    def _open_theme_picker(self):
        def _on_pick(name):
            app = self.winfo_toplevel()
            if hasattr(app, "_active_tab") and hasattr(app, "_vaults"):
                idx = app._active_tab
                if 0 <= idx < len(app._vaults):
                    # Save theme for this vault
                    app._vaults[idx]["theme"] = name
                    _save_vault_theme(app._vaults[idx]["dir"], name)
                    _apply_theme_by_name(name)
                    # Rebuild this vault's UI
                    if app._vaults[idx].get("key"):
                        f = app._vaults[idx].get("frame")
                        if f and f.winfo_exists(): f.destroy()
                        app._show_vault_for(idx)
        _show_theme_picker(self._theme_btn, _on_pick)

    # -- Import / Export / Backup -------------------------------------------
    def _export_vault(self):
        from tkinter import filedialog
        if not self.vault:
            messagebox.showinfo("Export","Vault is empty.",parent=self.winfo_toplevel()); return
        fmt_win = tk.Toplevel(self.winfo_toplevel())
        fmt_win.transient(self.winfo_toplevel()); fmt_win.title("Export Format")
        fmt_win.configure(bg=SURFACE); fmt_win.grab_set()
        fmt_win.resizable(False, False)
        _centre_on_parent(fmt_win, self.winfo_toplevel(), 340, 180)
        # Styled content
        pad = tk.Frame(fmt_win, bg=SURFACE, padx=28, pady=24); pad.pack(fill="both", expand=True)
        tk.Label(pad, text="Export Vault", font=FNT_HEAD, fg=TEXT, bg=SURFACE).pack(pady=(0,8))
        tk.Label(pad, text="\u26a0  Exported files are NOT encrypted. Store securely.",
                 font=FNT_SM, fg="#ffb347", bg=SURFACE, wraplength=280).pack(pady=(0,16))
        br = tk.Frame(pad, bg=SURFACE); br.pack(fill="x")
        def _do(fmt): fmt_win.destroy(); self._do_export(fmt)
        mk_btn(br, "\U0001f4c4  JSON", lambda: _do("json"), bg=ACCENT, fg="white", w=14).pack(side="left", padx=(0,10))
        mk_btn(br, "\U0001f4ca  CSV", lambda: _do("csv"), bg=ACCENT, fg="white", w=14).pack(side="left")
        fmt_win.after(50, lambda: _apply_dwm_to_widget(fmt_win))

    def _do_export(self, fmt):
        from tkinter import filedialog
        ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        if fmt == "json":
            path = filedialog.asksaveasfilename(title="Export", defaultextension=".json",
                filetypes=[("JSON","*.json")], initialfile=f"marai_export_{ts}.json",
                parent=self.winfo_toplevel())
            if not path: return
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump({"format":"marai-export","version":"1.0",
                               "exported_at":datetime.datetime.now().isoformat(timespec="seconds"),
                               "entry_count":len(self.vault),"entries":self.vault}, f, indent=2, ensure_ascii=False)
                messagebox.showinfo("Done", f"\u2705 {len(self.vault)} entries exported.", parent=self.winfo_toplevel())
            except Exception as e:
                messagebox.showerror("Failed", str(e), parent=self.winfo_toplevel())
        else:
            path = filedialog.asksaveasfilename(title="Export CSV", defaultextension=".csv",
                filetypes=[("CSV","*.csv")], initialfile=f"marai_export_{ts}.csv",
                parent=self.winfo_toplevel())
            if not path: return
            try:
                all_keys = set()
                for e in self.vault: all_keys.update(e.keys())
                priority = ["name","user","password","url","category","context",
                            "host","port","notes","body","updated_at","favourite"]
                cols = [k for k in priority if k in all_keys] + sorted(all_keys - set(priority))
                with open(path, "w", newline="", encoding="utf-8") as f:
                    w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
                    w.writeheader(); w.writerows(self.vault)
                messagebox.showinfo("Done", f"\u2705 {len(self.vault)} entries exported.", parent=self.winfo_toplevel())
            except Exception as e:
                messagebox.showerror("Failed", str(e), parent=self.winfo_toplevel())

    def _import_vault(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(title="Import",
            filetypes=[("All supported","*.json *.csv"),("JSON","*.json"),("CSV","*.csv")],
            parent=self.winfo_toplevel())
        if not path: return
        entries = []
        try:
            if path.lower().endswith(".csv"):
                with open(path, encoding="utf-8") as f:
                    for row in csv.DictReader(f):
                        c = {k:v for k,v in row.items() if v}
                        if c.get("favourite"): c["favourite"] = c["favourite"].lower() in ("true","1","yes")
                        entries.append(c)
            else:
                with open(path, encoding="utf-8") as f: data = json.load(f)
                entries = data if isinstance(data,list) else data.get("entries",[]) if isinstance(data,dict) else []
        except Exception as e:
            messagebox.showerror("Failed", str(e), parent=self.winfo_toplevel()); return
        valid = [e for e in entries if isinstance(e,dict) and e.get("name")]
        if not valid:
            messagebox.showinfo("Import","No valid entries found.",parent=self.winfo_toplevel()); return
        if not messagebox.askyesno("Import",f"Import {len(valid)} entries?",parent=self.winfo_toplevel()): return
        now_ts = datetime.datetime.now().isoformat(timespec="seconds")
        for e in valid:
            e.setdefault("type",e.get("category","Password"))
            e.setdefault("category",e.get("type","Password"))
            e.setdefault("context","Personal"); e.setdefault("updated_at",now_ts)
            e.setdefault("favourite",False); self.vault.insert(0,e)
        self._save_vault(); self._render()
        messagebox.showinfo("Done",f"\u2705 {len(valid)} entries imported.",parent=self.winfo_toplevel())

    def _backup_vault(self):
        from tkinter import filedialog
        ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        dest = filedialog.askdirectory(title="Backup Location",
            initialdir=os.path.expanduser("~"), parent=self.winfo_toplevel())
        if not dest: return
        try:
            bd = os.path.join(dest, f"marai_backup_{ts}")
            os.makedirs(bd, exist_ok=True)
            if os.path.exists(self.vault_file): shutil.copy2(self.vault_file, os.path.join(bd,"vault.enc"))
            if os.path.exists(self.meta_file): shutil.copy2(self.meta_file, os.path.join(bd,"meta.json"))
            with open(os.path.join(bd,"backup_info.json"),"w",encoding="utf-8") as f:
                json.dump({"backup_date":datetime.datetime.now().isoformat(timespec="seconds"),
                           "marai_version":VERSION,"entry_count":len(self.vault)}, f, indent=2)
            messagebox.showinfo("Backup",f"\u2705 Backup saved to:\n{bd}",parent=self.winfo_toplevel())
        except Exception as e:
            messagebox.showerror("Failed",str(e),parent=self.winfo_toplevel())

    # -- Render -------------------------------------------------------------
    def _on_canvas_resize(self, event):
        self.canvas.itemconfig(self._cw, width=event.width)
        if event.width != self._last_canvas_width:
            self._last_canvas_width = event.width
            if self._resize_job: self.after_cancel(self._resize_job)
            self._resize_job = self.after(120, self._render)

    def _render(self):
        for w in self.cards_frame.winfo_children(): w.destroy()
        self.pw_visible.clear()
        # Fully reset ALL grid row/column configs to prevent ghost sizing from previous view
        for _r in range(200): self.cards_frame.grid_rowconfigure(_r, weight=0, minsize=0)
        for _c in range(6): self.cards_frame.grid_columnconfigure(_c, weight=0, minsize=0, uniform="")
        q = self.search_var.get().lower()
        ftype = self.active_type.get()
        ctx_filter = self._ctx_active
        def _m(e):
            if ftype != "All" and _entry_type(e) != ftype: return False
            if _entry_context(e) not in ctx_filter: return False
            if not q: return True
            return q in " ".join(str(v) for v in e.values() if isinstance(v,str)).lower()
        filtered = sorted([e for e in self.vault if _m(e)],
                          key=lambda e: (not e.get("favourite",False),))
        n = len(self.vault)
        self.count_lbl.config(text=f"{n} entr{'y' if n==1 else 'ies'}")
        if not filtered:
            msg = "No results found." if (q or ftype!="All" or len(ctx_filter)<len(CONTEXTS)) \
                  else "Your vault is empty.\nClick '+ Add Entry' to start."
            tk.Label(self.cards_frame, text=msg, font=FNT_BODY, fg=MUTED, bg=BG,
                     justify="center").pack(pady=80)
            return
        mode = self._view_mode; cw = self.canvas.winfo_width()
        if mode == "list":
            self.cards_frame.grid_columnconfigure(0, weight=1)
            for i, entry in enumerate(filtered):
                self._make_row(self.cards_frame, entry, self.vault.index(entry), i)
        else:
            cols = max(1, min(4, cw//240)) if mode=="small" else (1 if mode=="large" else (1 if cw<640 else 2))
            for c in range(4):
                self.cards_frame.grid_columnconfigure(c, weight=1 if c<cols else 0,
                                                      uniform="col" if c<cols else "")
            CH = self._zoom_scale(102 if mode=="small" else (174 if mode=="large" else 138))
            nr = (len(filtered)+cols-1)//cols
            for r in range(nr): self.cards_frame.grid_rowconfigure(r, weight=0, minsize=CH)
            for i, entry in enumerate(filtered):
                ri = self.vault.index(entry); r,c = divmod(i,cols)
                cell = tk.Frame(self.cards_frame, bg=BG)
                cell.grid(row=r, column=c, sticky="nsew", padx=8, pady=8)
                cell.grid_rowconfigure(0, weight=1); cell.grid_columnconfigure(0, weight=1)
                if mode=="small": self._make_card_small(cell, entry, ri)
                elif mode=="large": self._make_card(cell, entry, ri, compact=False)
                else: self._make_card(cell, entry, ri, compact=True)
        # Force layout update and scroll to top to prevent blank page
        self.cards_frame.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self.canvas.yview_moveto(0)

    # -- Detail panel -------------------------------------------------------
    def _open_detail(self, idx):
        self._detail_idx = idx; self._refresh_detail()
    def _close_detail(self):
        self._detail_idx = None
        if self._detail_panel and self._detail_panel.winfo_exists():
            self._detail_panel.grid_forget(); self._detail_panel.destroy()
            self._detail_panel = None
        for w in self._detail_container.grid_slaves(column=1): w.destroy()

    def _refresh_detail(self):
        if self._detail_idx is None: return
        if self._detail_idx >= len(self.vault): self._close_detail(); return
        if self._detail_panel and self._detail_panel.winfo_exists():
            self._detail_panel.destroy()
        entry = self.vault[self._detail_idx]
        cat = _entry_type(entry); ctx = _entry_context(entry)
        fg_c, bg_c = _cat_colors(cat)
        ctx_fg, _ = CONTEXT_COLORS.get(ctx, (MUTED, SURFACE2))
        panel = tk.Frame(self._detail_container, bg=SURFACE,
                         highlightbackground=BORDER, highlightthickness=1, width=340)
        panel.grid(row=0, column=1, sticky="nsew"); panel.grid_propagate(False)
        self._detail_panel = panel
        tk.Frame(panel, bg=fg_c, height=4).pack(fill="x")
        hdr = tk.Frame(panel, bg=SURFACE, padx=18, pady=14); hdr.pack(fill="x")
        icon_lbl = tk.Label(hdr, text=TYPE_EMOJI.get(cat,"\U0001f511"), font=("Segoe UI",32),
                            bg=bg_c, fg=fg_c, padx=12, pady=10, relief="flat")
        icon_lbl.pack(side="left")
        cached = _get_icon(entry, "64")
        if cached: icon_lbl.config(image=cached, text="", bg=SURFACE); icon_lbl._img = cached
        else:
            def _icr(d, icons, lbl=icon_lbl):
                img = icons.get("64") if icons else None
                if img and lbl.winfo_exists(): lbl.config(image=img, text="", bg=SURFACE); lbl._img = img
            _get_icon(entry, "64", on_ready=lambda d, icons: self.after(0, lambda: _icr(d, icons)))
        tf = tk.Frame(hdr, bg=SURFACE); tf.pack(side="left", padx=(12,0), fill="x", expand=True)
        tk.Label(tf, text=entry.get("name",""), font=FNT_HEAD, fg=TEXT, bg=SURFACE,
                 anchor="w", wraplength=220).pack(anchor="w")
        br = tk.Frame(tf, bg=SURFACE); br.pack(anchor="w")
        tk.Label(br, text=f"{CONTEXT_EMOJI.get(ctx,'')} {ctx}", font=FNT_SM, fg=ctx_fg, bg=SURFACE).pack(side="left")
        tk.Label(br, text=" \u00b7 ", font=FNT_SM, fg=MUTED, bg=SURFACE).pack(side="left")
        tk.Label(br, text=f"{CAT_EMOJI.get(cat,'')} {cat}", font=FNT_SM, fg=MUTED, bg=SURFACE).pack(side="left")
        sub = _entry_subtitle(entry)
        if sub:
            tk.Label(tf, text=sub, font=("Segoe UI",9), fg=ACCENT, bg=SURFACE,
                     anchor="w", wraplength=220).pack(anchor="w")
        cb = tk.Label(hdr, text="\u2715", font=("Segoe UI",11), bg=SURFACE, fg=MUTED, cursor="hand2", padx=4)
        cb.pack(side="right", anchor="n")
        cb.bind("<Button-1>", lambda e: self._close_detail())
        cb.bind("<Enter>", lambda e: cb.config(fg=RED)); cb.bind("<Leave>", lambda e: cb.config(fg=MUTED))
        tk.Frame(panel, bg=BORDER, height=1).pack(fill="x")
        bc = tk.Canvas(panel, bg=SURFACE, highlightthickness=0)
        bsb = mk_scrollbar(panel, orient="vertical", command=bc.yview)
        bc.configure(yscrollcommand=bsb.set)
        bsb.pack(side="right", fill="y"); bc.pack(side="left", fill="both", expand=True)
        _make_scrollable(bc)
        body = tk.Frame(bc, bg=SURFACE, padx=18, pady=10)
        bw = bc.create_window((0,0), window=body, anchor="nw")
        body.bind("<Configure>", lambda e: bc.configure(scrollregion=bc.bbox("all")))
        bc.bind("<Configure>", lambda e: bc.itemconfig(bw, width=e.width))
        idx = self._detail_idx
        masked_keys = {"password","pin","admin_pass"}
        cat_fields = _CATEGORY_FIELDS.get(cat, _CATEGORY_FIELDS.get("Password",[]))
        for label, key, opts in cat_fields:
            if key == "name": continue
            val = entry.get(key,"")
            if not val: continue
            is_masked = key in masked_keys or opts.get("show")

            # Special: credential_ref shows as linked badge with resolved info
            if opts.get("type") == "credential_ref" and val:
                cred_frame = tk.Frame(body, bg=SURFACE2,
                                      highlightbackground=ACCENT, highlightthickness=1)
                cred_frame.pack(fill="x", pady=4)
                tk.Label(cred_frame, text="LINKED CREDENTIAL", font=("Segoe UI",7,"bold"),
                         fg=ACCENT, bg=SURFACE2, anchor="w").pack(fill="x", padx=10, pady=(6,0))
                resolved_user, resolved_pw = self._resolve_credential(entry)
                cred_info = tk.Frame(cred_frame, bg=SURFACE2)
                cred_info.pack(fill="x", padx=10, pady=(2,6))
                tk.Label(cred_info, text=f"\U0001f517 {val}", font=("Segoe UI",10,"bold"),
                         fg=TEXT, bg=SURFACE2).pack(anchor="w")
                if resolved_user:
                    tk.Label(cred_info, text=f"User: {resolved_user}", font=FNT_SM,
                             fg=MUTED, bg=SURFACE2).pack(anchor="w")
                if resolved_pw:
                    cred_acts = tk.Frame(cred_info, bg=SURFACE2)
                    cred_acts.pack(anchor="w", pady=(4,0))
                    def _cp_cred_pw(pw=resolved_pw):
                        self._copy_secure(pw)
                    tk.Button(cred_acts, text="\U0001f4cb Copy Password", font=FNT_SM,
                              bg=SURFACE3, fg=TEXT, relief="flat", cursor="hand2",
                              bd=0, padx=8, pady=3, command=_cp_cred_pw).pack(side="left")
                continue

            if opts.get("multiline"):
                tk.Label(body, text=label.upper(), font=("Segoe UI",7,"bold"),
                         fg=MUTED, bg=SURFACE).pack(anchor="w", pady=(4,2))
                nb = tk.Frame(body, bg=SURFACE2, highlightbackground=BORDER, highlightthickness=1)
                nb.pack(fill="x")
                tk.Label(nb, text=val, font=FNT_BODY, fg=TEXT, bg=SURFACE2,
                         anchor="nw", justify="left", wraplength=280, padx=10, pady=8).pack(fill="x")
                mk_btn(body, "\U0001f4cb Copy", lambda v=val: self._copy_secure(v),
                       bg=SURFACE2, fg=TEXT, w=18).pack(anchor="w", pady=(6,0))
            else:
                self._detail_field(body, label, val, is_masked, opts.get("mono",False))
        # Server connect
        if cat == "Server / RDP" and (entry.get("host") or entry.get("workspace","")):
            lbl = "\u25b6  Connect via AVD" if entry.get("workspace","").strip() else "\u25b6  Connect via RDP"
            mk_btn(body, lbl, lambda: self._rdp_connect(idx),
                   bg="#1a5c3a", fg="#60d0a0", w=22).pack(anchor="w", pady=(8,0))
        elif entry.get("url") and cat != "Server / RDP":
            url_val = entry["url"]; pw_val = entry.get("password","")
            def _o(u=url_val, pw=pw_val):
                if not u.startswith(("http://","https://")): u = "https://"+u
                self._copy_secure(pw); webbrowser.open(u)
            mk_btn(body, "\U0001f310  Open URL", _o, bg=SURFACE2, fg=ACCENT, w=18).pack(anchor="w", pady=(8,0))
        at, ac = _password_age(entry)
        tk.Label(body, text=at, font=FNT_SM, fg=ac, bg=SURFACE, anchor="w").pack(anchor="w", pady=(8,0))
        tk.Frame(body, bg=BORDER, height=1).pack(fill="x", pady=(14,4))
        is_fav = entry.get("favourite",False)
        ar = tk.Frame(body, bg=SURFACE); ar.pack(fill="x", pady=(4,0))
        def _tf():
            self.vault[idx]["favourite"] = not self.vault[idx].get("favourite",False)
            self._save_vault(); self._render(); self._refresh_detail()
        mk_btn(ar, "\u2605 Unfav" if is_fav else "\u2606 Fav", _tf,
               bg=SURFACE2, fg="#f5c518" if is_fav else MUTED, w=12).pack(side="left")
        mk_btn(ar, "Edit", lambda: self._edit(idx), bg=ACCENT, fg="white", w=10
               ).pack(side="left", padx=(8,0))
        mk_btn(ar, "\U0001f5d1 Del", lambda: self._delete(idx), bg=SURFACE2, fg=RED, w=10
               ).pack(side="left", padx=(8,0))
        # Move buttons
        mv = tk.Frame(body, bg=SURFACE); mv.pack(fill="x", pady=(6,0))
        mk_btn(mv, "\u25b2 Move Up", lambda: self._move_entry(idx, -1),
               bg=SURFACE2, fg=MUTED, w=12).pack(side="left")
        mk_btn(mv, "\u25bc Move Down", lambda: self._move_entry(idx, 1),
               bg=SURFACE2, fg=MUTED, w=12).pack(side="left", padx=(8,0))

    def _detail_field(self, body, label, value, masked=False, monospace=False):
        grp = tk.Frame(body, bg=SURFACE2, highlightbackground=BORDER, highlightthickness=1)
        grp.pack(fill="x", pady=4)
        tk.Label(grp, text=label.upper(), font=("Segoe UI",7,"bold"),
                 fg=MUTED, bg=SURFACE2, anchor="w").pack(fill="x", padx=10, pady=(6,0))
        vr = tk.Frame(grp, bg=SURFACE2); vr.pack(fill="x", padx=10, pady=(0,6))
        dv = tk.StringVar(value="\u25cf \u25cf \u25cf \u25cf \u25cf \u25cf" if masked else value)
        _s = [False]
        tk.Label(vr, textvariable=dv, font=FNT_MONO if (masked or monospace) else FNT_BODY,
                 fg=TEXT, bg=SURFACE2, anchor="w", wraplength=240, justify="left"
                 ).pack(side="left", fill="x", expand=True)
        bf = tk.Frame(vr, bg=SURFACE2); bf.pack(side="right")
        if masked:
            def _t(v=value, d=dv, s=_s):
                s[0] = not s[0]; d.set(v if s[0] else "\u25cf \u25cf \u25cf \u25cf \u25cf \u25cf")
            tk.Button(bf, text="\U0001f441", font=FNT_SM, bg=SURFACE2, fg=MUTED,
                      relief="flat", cursor="hand2", bd=0, padx=4, command=_t).pack(side="left")
        def _cv(v=value):
            self._copy_secure(v); grp.config(highlightbackground=GREEN)
            self.after(600, lambda: grp.config(highlightbackground=BORDER) if grp.winfo_exists() else None)
        tk.Button(bf, text="\U0001f4cb", font=FNT_SM, bg=SURFACE2, fg=MUTED,
                  relief="flat", cursor="hand2", bd=0, padx=4, command=_cv).pack(side="left")

    def _bind_click_recursive(self, widget, idx):
        """Bind click-to-detail on labels and frames, but SKIP buttons so their commands work."""
        if not isinstance(widget, tk.Button):
            widget.bind("<Button-1>", lambda e, i=idx: self._open_detail(i), add="+")
        for child in widget.winfo_children():
            self._bind_click_recursive(child, idx)

    # -- List row -----------------------------------------------------------
    def _make_row(self, parent, entry, idx, row_num):
        cat = _entry_cat(entry); ctx = _entry_context(entry)
        fg_c, bg_c = _cat_colors(cat)
        is_fav = entry.get("favourite",False)
        is_act = (self._detail_idx == idx)
        rb = SURFACE3 if is_act else (SURFACE if row_num%2==0 else SURFACE2)

        row = tk.Frame(parent, bg=rb, cursor="hand2")
        row.grid(row=row_num, column=0, sticky="ew", padx=6, pady=1)
        row.bind("<Enter>", lambda e,r=row,i=idx:
                 r.config(bg=SURFACE3) if self._detail_idx!=i else None)
        row.bind("<Leave>", lambda e,r=row,i=idx:
                 r.config(bg=rb) if self._detail_idx!=i else None)

        # Color dot
        tk.Frame(row, bg=fg_c, width=3, height=3).pack(side="left", padx=(8,6), pady=10)

        # Inline icon (emoji only for speed)
        tk.Label(row, text=CAT_EMOJI.get(cat,"\U0001f511"), font=("Segoe UI Emoji",10),
                 bg=rb, fg=fg_c, cursor="hand2").pack(side="left", padx=(0,6))

        # Name
        name = entry.get("name","")
        tk.Label(row, text=name, font=("Segoe UI",10,"bold"),
                 fg=TEXT, bg=rb, anchor="w", cursor="hand2").pack(side="left", padx=(0,8))

        # Category badge
        tk.Label(row, text=cat, font=("Segoe UI",8), fg=fg_c, bg=rb).pack(side="left", padx=(0,6))

        # Subtitle
        sub = _entry_subtitle(entry)
        if sub:
            tk.Label(row, text=sub, font=("Segoe UI",8), fg=MUTED, bg=rb,
                     anchor="w", cursor="hand2").pack(side="left", padx=(0,8))

        # Fav star
        if is_fav:
            tk.Label(row, text="\u2605", font=("Segoe UI",9), fg="#f5c518",
                     bg=rb).pack(side="left")

        # Action buttons — right side
        acts = tk.Frame(row, bg=rb); acts.pack(side="right", padx=(0,8))
        def _ab(t,cmd,col=MUTED,fbg=None):
            bg_ = fbg or rb
            b = tk.Button(acts, text=t, font=("Segoe UI",8), bg=bg_, fg=col,
                          relief="flat", cursor="hand2", bd=0, padx=6, pady=2, command=cmd)
            b.bind("<Enter>", lambda e: b.config(bg=ACCENT,fg="white"))
            b.bind("<Leave>", lambda e: b.config(bg=bg_,fg=col)); return b

        if cat == "Server / RDP" and (entry.get("host") or entry.get("workspace","")):
            ws = entry.get("workspace","").strip()
            _ab("\u25b6 AVD" if ws else "\u25b6 RDP",
                lambda i=idx: self._rdp_connect(i), col="#60d0a0", fbg="#1a4030").pack(side="left",padx=2)
        elif entry.get("url"):
            uv = entry["url"]; pv = entry.get("password","")
            def _ou(u=uv,pw=pv):
                if not u.startswith(("http://","https://")): u = "https://"+u
                self._copy_secure(pw); webbrowser.open(u)
            _ab("\U0001f310", _ou, col=ACCENT).pack(side="left",padx=2)
        elif cat != "Secure Note" and entry.get("password"):
            _ab("\U0001f4cb", lambda pw=entry["password"]: self._copy_secure(pw)).pack(side="left",padx=2)
        _ab("Edit", lambda i=idx: self._edit(i), col=TEXT, fbg=SURFACE2).pack(side="left",padx=1)
        _ab("\u2715", lambda i=idx: self._delete(i), col=RED).pack(side="left",padx=1)
        _ab("\u25b2", lambda i=idx: self._move_entry(i,-1)).pack(side="left",padx=1)
        _ab("\u25bc", lambda i=idx: self._move_entry(i,1)).pack(side="left",padx=1)
        self.after_idle(lambda r=row, i=idx: self._bind_click_recursive(r,i))

    # -- Small card ---------------------------------------------------------
    def _make_card_small(self, parent, entry, idx):
        cat = _entry_cat(entry); ctx = _entry_context(entry)
        fg_c, bg_c = _cat_colors(cat)
        is_fav = entry.get("favourite",False)
        is_act = (self._detail_idx == idx)
        bdr = ACCENT if is_act else CARD_BORDER
        card = tk.Frame(parent, bg=SURFACE, highlightbackground=bdr,
                        highlightthickness=1, cursor="hand2")
        card.grid(row=0, column=0, sticky="nsew")
        card.bind("<Enter>", lambda e,c=card: c.config(highlightbackground=ACCENT))
        card.bind("<Leave>", lambda e,c=card: c.config(highlightbackground=bdr))
        tk.Frame(card, bg=fg_c, height=3).pack(fill="x")
        inner = tk.Frame(card, bg=SURFACE, padx=12, pady=10, cursor="hand2")
        inner.pack(fill="both", expand=True)
        top = tk.Frame(inner, bg=SURFACE, cursor="hand2"); top.pack(fill="x")
        ic = tk.Label(top, text=CAT_EMOJI.get(cat,"\U0001f511"), font=("Segoe UI Emoji",20),
                      bg=bg_c, fg=fg_c, padx=6, pady=4, cursor="hand2")
        ic.pack(side="left")
        cached = _get_icon(entry, "40")
        if cached: ic.config(image=cached, text="", bg=SURFACE); ic._img = cached
        else:
            def _ic(d,icons,lbl=ic):
                img = icons.get("40") if icons else None
                if img and lbl.winfo_exists(): lbl.config(image=img,text="", bg=SURFACE); lbl._img=img
            _get_icon(entry, "40", on_ready=lambda d,icons: self.after(0, lambda: _ic(d,icons)))
        name = entry.get("name","")
        tk.Label(top, text=name[:16]+("\u2026" if len(name)>16 else ""),
                 font=("Segoe UI",9,"bold"), fg=TEXT, bg=SURFACE, anchor="w",
                 wraplength=110, cursor="hand2").pack(side="left", padx=(6,0), fill="x", expand=True)
        tk.Label(inner, text=f"{CONTEXT_EMOJI.get(ctx,'')} {ctx}  \u00b7  {CAT_EMOJI.get(cat,'')} {cat}",
                 font=("Segoe UI",8), fg=MUTED, bg=SURFACE).pack(anchor="w", pady=(4,0))
        # Subtitle - connection details
        sub = _entry_subtitle(entry)
        if sub:
            tk.Label(inner, text=sub[:30]+("\u2026" if len(sub)>30 else ""),
                     font=("Segoe UI",8), fg=ACCENT, bg=SURFACE, anchor="w").pack(anchor="w")

        # Quick action row - Open/Connect instead of fields
        acts = tk.Frame(inner, bg=SURFACE); acts.pack(fill="x", pady=(6,0))
        def _mk(t,cmd,col=MUTED):
            b = tk.Button(acts, text=t, font=("Segoe UI",9), bg=SURFACE2, fg=col,
                          relief="flat", cursor="hand2", bd=0, padx=6, pady=2)
            b.bind("<Enter>", lambda e: b.config(bg=ACCENT,fg="white"))
            b.bind("<Leave>", lambda e: b.config(bg=SURFACE2,fg=col))
            b.config(command=cmd); return b
        # Left: quick action
        if cat == "Server / RDP" and (entry.get("host") or entry.get("workspace","")):
            ws = entry.get("workspace","").strip()
            clbl = "\u25b6 AVD" if ws else "\u25b6 RDP"
            cb = tk.Button(acts, text=clbl, font=("Segoe UI",9,"bold"), bg="#1a4030", fg="#60d0a0",
                           relief="flat", cursor="hand2", bd=0, padx=8, pady=2)
            cb.bind("<Enter>", lambda e,b=cb: b.config(bg="#2a6048"))
            cb.bind("<Leave>", lambda e,b=cb: b.config(bg="#1a4030"))
            cb.config(command=lambda i=idx: self._rdp_connect(i)); cb.pack(side="left")
        elif entry.get("url"):
            uv = entry["url"]; pv = entry.get("password","")
            def _ou(u=uv,pw=pv):
                if not u.startswith(("http://","https://")): u = "https://"+u
                self._copy_secure(pw); webbrowser.open(u)
            _mk("\U0001f310 Open", _ou, col=ACCENT).pack(side="left")
        elif cat != "Secure Note" and entry.get("password"):
            _mk("\U0001f4cb Copy", lambda pw=entry["password"]: self._copy_secure(pw)).pack(side="left")
        # Right: fav, edit, delete - nicer fonts
        right_acts = tk.Frame(acts, bg=SURFACE); right_acts.pack(side="right")
        def _mkr(t,cmd,col=MUTED):
            b = tk.Button(right_acts, text=t, font=("Segoe UI",9), bg=SURFACE, fg=col,
                          relief="flat", cursor="hand2", bd=0, padx=4)
            b.bind("<Enter>", lambda e: b.config(bg=ACCENT,fg="white"))
            b.bind("<Leave>", lambda e: b.config(bg=SURFACE,fg=col))
            b.config(command=cmd); return b
        s = _mkr("\u2605" if is_fav else "\u2606", None, col="#f5c518" if is_fav else MUTED)
        def _fv(i=idx):
            self.vault[i]["favourite"] = not self.vault[i].get("favourite",False)
            self._save_vault(); self._render()
        s.config(command=_fv); s.pack(side="left")
        eb = tk.Button(right_acts, text="Edit", font=("Segoe UI",8), bg=SURFACE2, fg=TEXT,
                       relief="flat", cursor="hand2", bd=0, padx=6, pady=2,
                       command=lambda i=idx: self._edit(i))
        eb.bind("<Enter>", lambda e: eb.config(bg=ACCENT,fg="white"))
        eb.bind("<Leave>", lambda e: eb.config(bg=SURFACE2,fg=TEXT))
        eb.pack(side="left", padx=(2,0))
        _mkr("\u2715", lambda i=idx: self._delete(i), col=RED).pack(side="left", padx=(2,0))
        _mkr("\u25b2", lambda i=idx: self._move_entry(i,-1)).pack(side="left", padx=(2,0))
        _mkr("\u25bc", lambda i=idx: self._move_entry(i,1)).pack(side="left", padx=(1,0))
        self.after_idle(lambda c=card, i=idx: self._bind_click_recursive(c,i))

    # -- Medium / Large card ------------------------------------------------
    def _make_card(self, parent, entry, idx, compact=True):
        cat = _entry_cat(entry); ctx = _entry_context(entry)
        fg_c, bg_c = _cat_colors(cat)
        ctx_fg, _ = CONTEXT_COLORS.get(ctx,(MUTED,SURFACE2))
        is_fav = entry.get("favourite",False)
        is_act = (self._detail_idx == idx)
        bdr = ACCENT if is_act else CARD_BORDER
        card = tk.Frame(parent, bg=SURFACE, highlightbackground=bdr,
                        highlightthickness=1, cursor="hand2")
        card.grid(row=0, column=0, sticky="nsew")
        card.bind("<Enter>", lambda e,c=card: c.config(highlightbackground=ACCENT))
        card.bind("<Leave>", lambda e,c=card: c.config(highlightbackground=bdr))
        tk.Frame(card, bg=fg_c, width=4).pack(side="left", fill="y")
        inner = tk.Frame(card, bg=SURFACE, padx=16, pady=14, cursor="hand2")
        inner.pack(side="left", fill="both", expand=True)
        hdr = tk.Frame(inner, bg=SURFACE, cursor="hand2"); hdr.pack(fill="x")
        ic = tk.Label(hdr, text=CAT_EMOJI.get(cat,"\U0001f511"), font=("Segoe UI Emoji",28),
                      bg=bg_c, fg=fg_c, padx=10, pady=8, relief="flat", cursor="hand2")
        ic.pack(side="left")
        cached = _get_icon(entry, "64")
        if cached: ic.config(image=cached, text="", bg=SURFACE); ic._img = cached
        else:
            def _ic(d,icons,lbl=ic):
                img = icons.get("64") if icons else None
                if img and lbl.winfo_exists(): lbl.config(image=img,text="", bg=SURFACE); lbl._img=img
            _get_icon(entry, "64", on_ready=lambda d,icons: self.after(0, lambda: _ic(d,icons)))
        info = tk.Frame(hdr, bg=SURFACE, cursor="hand2")
        info.pack(side="left", padx=(10,0), fill="x", expand=True)
        tk.Label(info, text=entry.get("name",""), font=FNT_HEAD, fg=TEXT, bg=SURFACE, anchor="w").pack(anchor="w")
        badges = tk.Frame(info, bg=SURFACE); badges.pack(anchor="w")
        tk.Label(badges, text=f"{CAT_EMOJI.get(cat,'')} {cat}", font=FNT_SM, fg=fg_c, bg=SURFACE).pack(side="left")
        tk.Label(badges, text=" \u00b7 ", font=FNT_SM, fg=MUTED, bg=SURFACE).pack(side="left")
        tk.Label(badges, text=f"{CONTEXT_EMOJI.get(ctx,'')} {ctx}", font=FNT_SM, fg=ctx_fg, bg=SURFACE).pack(side="left")
        # Subtitle - connection details, domain, card number, etc.
        sub = _entry_subtitle(entry)
        if sub:
            tk.Label(info, text=sub, font=("Segoe UI",9), fg=ACCENT, bg=SURFACE, anchor="w").pack(anchor="w")
        acts = tk.Frame(hdr, bg=SURFACE); acts.pack(side="right", padx=(4,0))
        def _mk(t,cmd,col=MUTED):
            b = tk.Button(acts, text=t, font=("Segoe UI",10), bg=SURFACE, fg=col,
                          relief="flat", cursor="hand2", bd=0, padx=5)
            b.bind("<Enter>", lambda e: b.config(bg=ACCENT,fg="white"))
            b.bind("<Leave>", lambda e: b.config(bg=SURFACE,fg=col))
            b.config(command=cmd); return b
        fb = _mk("\u2605" if is_fav else "\u2606", None, col="#f5c518" if is_fav else MUTED)
        fb.pack(side="left")
        def _fc(i=idx):
            self.vault[i]["favourite"] = not self.vault[i].get("favourite",False)
            self._save_vault(); self._render()
        fb.config(command=_fc)
        eb = tk.Button(acts, text="Edit", font=("Segoe UI",9), bg=ACCENT, fg="white",
                       relief="flat", cursor="hand2", bd=0, padx=8,
                       command=lambda i=idx: self._edit(i))
        eb.bind("<Enter>", lambda e: eb.config(bg=_lighten(ACCENT)))
        eb.bind("<Leave>", lambda e: eb.config(bg=ACCENT))
        eb.pack(side="left", padx=(4,0))
        _mk("\u2715 Del", lambda i=idx: self._delete(i), col=RED).pack(side="left", padx=(2,0))
        _mk("\u25b2", lambda i=idx: self._move_entry(i,-1)).pack(side="left", padx=(2,0))
        _mk("\u25bc", lambda i=idx: self._move_entry(i,1)).pack(side="left", padx=(1,0))
        tk.Frame(inner, bg=BORDER, height=1).pack(fill="x", pady=(10,8))
        if cat == "Secure Note":
            body = entry.get("body","")
            tk.Label(inner, text=(body[:160]+"\u2026" if len(body)>160 else body) or "Empty note.",
                     font=FNT_SM, fg=TEXT, bg=SURFACE, anchor="w", justify="left", wraplength=320).pack(anchor="w")
            tk.Button(inner, text="\U0001f4cb  Copy Note", font=FNT_SM, bg=SURFACE2, fg=MUTED,
                      relief="flat", cursor="hand2", bd=0, padx=8, pady=4,
                      command=lambda b=body: self._copy_secure(b)).pack(anchor="w", pady=(6,0))
        else:
            # Show linked credential badge for servers
            cred_ref = entry.get("credential_ref","").strip()
            if cat == "Server / RDP" and cred_ref:
                resolved_user, _ = self._resolve_credential(entry)
                tk.Label(inner, text=f"\U0001f517 {cred_ref}" + (f"  ({resolved_user})" if resolved_user else ""),
                         font=("Segoe UI",9), fg=ACCENT, bg=SURFACE, anchor="w").pack(anchor="w", pady=(0,4))
            else:
                if entry.get("user"): self._field(inner, "User", entry["user"], idx, False)
            if entry.get("password"): self._field(inner, "Pass", entry["password"], idx, True)
        if cat == "Server / RDP":
            h = entry.get("host",""); p = entry.get("port","3389")
            if h: self._field(inner, "Host", f"{h}:{p}" if p!="3389" else h, idx, False)
            ws = entry.get("workspace","").strip()
            tk.Button(inner, text="\u25b6  Connect via "+(("AVD" if ws else "RDP")),
                      font=FNT_SM, bg="#0e2a20", fg="#60d0a0", relief="flat", cursor="hand2",
                      bd=0, padx=10, pady=5, command=lambda i=idx: self._rdp_connect(i)
                      ).pack(anchor="w", pady=(8,0))
        elif entry.get("url"):
            uv = entry["url"]; pv = entry.get("password","")
            def _ou(u=uv,pw=pv):
                if not u.startswith(("http://","https://")): u = "https://"+u
                self._copy_secure(pw); webbrowser.open(u)
            tk.Button(inner, text="\U0001f310  Open URL", font=FNT_SM, bg=SURFACE2, fg=ACCENT,
                      relief="flat", cursor="hand2", bd=0, padx=10, pady=5, command=_ou
                      ).pack(anchor="w", pady=(8,0))
        if entry.get("notes"):
            tk.Label(inner, text=f"\U0001f4dd  {entry['notes']}", font=FNT_SM, fg=MUTED,
                     bg=SURFACE, anchor="w", wraplength=320).pack(anchor="w", pady=(6,0))
        at, ac = _password_age(entry)
        tk.Label(inner, text=at, font=FNT_SM, fg=ac, bg=SURFACE, anchor="w").pack(anchor="w", pady=(4,0))
        self.after_idle(lambda c=card, i=idx: self._bind_click_recursive(c,i))

    def _field(self, parent, label, value, idx, masked):
        row = tk.Frame(parent, bg=SURFACE2, highlightbackground=BORDER, highlightthickness=1)
        row.pack(fill="x", pady=3)
        tk.Label(row, text=label, font=("Segoe UI",8), fg=MUTED, bg=SURFACE2, width=5, anchor="w"
                 ).pack(side="left", padx=(10,6))
        key = f"{label}_{idx}"
        lbl = tk.Label(row, text="\u25cf \u25cf \u25cf \u25cf \u25cf \u25cf" if masked else value,
                       font=FNT_MONO, fg=TEXT, bg=SURFACE2, anchor="w")
        lbl.pack(side="left", fill="x", expand=True, ipady=7)
        if masked:
            self.pw_visible[key] = False
            def toggle(l=lbl,v=value,k=key):
                self.pw_visible[k] = not self.pw_visible[k]
                l.config(text=v if self.pw_visible[k] else "\u25cf \u25cf \u25cf \u25cf \u25cf \u25cf")
            tk.Button(row, text="\U0001f441", font=FNT_SM, bg=SURFACE2, fg=MUTED,
                      relief="flat", cursor="hand2", bd=0, padx=4, command=toggle
                      ).pack(side="right", padx=2)
        tk.Button(row, text="\U0001f4cb", font=FNT_SM, bg=SURFACE2, fg=MUTED,
                  relief="flat", cursor="hand2", bd=0, padx=4,
                  command=lambda v=value,r=row: self._copy(v,r)).pack(side="right", padx=2)

    def _copy(self, value, row):
        self._copy_secure(value)
        widgets = [row] + list(row.winfo_children())
        for w in widgets:
            try: w.config(bg="#0e3028")
            except: pass
        self.after(500, lambda: [w.config(bg=SURFACE2) for w in widgets if w.winfo_exists()])

    def _copy_secure(self, value, clear_after=30):
        """Copy to clipboard securely (excludes from Windows clipboard history)."""
        _clipboard_copy_secure(value, self, clear_after=clear_after)

    # -- Auto-lock, update, misc -------------------------------------------
    def _on_update_found(self, nv): self.after(0, lambda: self._show_update_banner(nv))
    def _show_update_banner(self, nv):
        self._update_lbl.config(text=f"\U0001f389  MARAi v{nv} available!  You are on v{VERSION}.")
        self._update_banner.pack(fill="x", after=self.winfo_children()[0])
    def _dismiss_update_banner(self): self._update_banner.pack_forget()
    def _on_activity(self): self._last_activity = _time.time()
    def _reset_auto_lock(self):
        self._last_activity = _time.time()
        if self._auto_lock_job: self.after_cancel(self._auto_lock_job)
        self._auto_lock_job = self.after(30_000, self._check_idle)
    def _check_idle(self):
        if _time.time() - self._last_activity >= self._AUTO_LOCK_SECS:
            self._auto_lock_trigger()
        else: self._auto_lock_job = self.after(30_000, self._check_idle)
    def _update_lock_timer_display(self):
        try:
            idle = _time.time() - getattr(self, "_last_activity", _time.time())
            remain = max(0, int(self._AUTO_LOCK_SECS - idle))
            m,s = divmod(remain, 60)
            self.lock_timer_lbl.config(text=f"\U0001f512 {m}:{s:02d}")
            self.after(1000, self._update_lock_timer_display)
        except: pass
    def _auto_lock_trigger(self):
        self.vault = []; self.key = None; self.on_lock()
    def _open_generator(self): GeneratorDialog(self.winfo_toplevel())

    def _change_password(self):
        win = tk.Toplevel(self.winfo_toplevel())
        win.transient(self.winfo_toplevel()); win.title("Change Master Password")
        win.configure(bg=SURFACE); win.resizable(False, False); win.grab_set()
        try:
            _ico = getattr(self.winfo_toplevel(), "_ico_path", None)
            if _ico: win.iconbitmap(_ico)
        except: pass
        _centre_on_parent(win, self.winfo_toplevel(), 420, 460)
        pad = tk.Frame(win, bg=SURFACE, padx=30, pady=28); pad.pack(fill="both", expand=True)
        tk.Label(pad, text="\U0001f511  Change Master Password", font=FNT_HEAD,
                 fg=TEXT, bg=SURFACE).pack(anchor="w", pady=(0,20))
        for lbl_text, var_name in [("CURRENT PASSWORD","v_c"),("NEW PASSWORD","v_n"),("CONFIRM NEW","v_cf")]:
            tk.Label(pad, text=lbl_text, font=FNT_SM, fg=MUTED, bg=SURFACE).pack(anchor="w")
            setattr(self, var_name, tk.StringVar())
            mk_entry(pad, getattr(self, var_name), show="\u25cf", mono=True, w=36
                     ).pack(fill="x", ipady=10, pady=(4,14))
        err = tk.Label(pad, text="", font=FNT_SM, fg=RED, bg=SURFACE); err.pack(pady=(4,0))
        ok = tk.Label(pad, text="", font=FNT_SM, fg=GREEN, bg=SURFACE); ok.pack()
        def do():
            cur = self.v_c.get(); np = self.v_n.get(); cf = self.v_cf.get()
            err.config(text=""); ok.config(text="")
            meta = load_meta(self.meta_file); salt = base64.b64decode(meta["salt"])
            try:
                kdf_used = meta.get("kdf","pbkdf2")
                tk_ = derive_key(cur, salt, kdf=kdf_used)
                if decrypt_data(tk_, base64.b64decode(meta["verify"])) not in ("MARAI_OK","VAULTKEY_OK"):
                    raise ValueError
            except: err.config(text="Current password is incorrect."); return
            if not np: err.config(text="New password cannot be empty."); return
            if len(np)<6: err.config(text="Must be at least 6 characters."); return
            if np != cf: err.config(text="Passwords do not match."); return
            if np == cur: err.config(text="Must differ from current."); return
            ns = secrets.token_bytes(16)
            nk = derive_key(np, ns, kdf="argon2id" if ARGON2_OK else "pbkdf2")
            save_meta(base64.b64encode(ns).decode(),
                      base64.b64encode(encrypt_data(nk,"MARAI_OK")).decode(),
                      kdf="argon2id" if ARGON2_OK else "pbkdf2", meta_file=self.meta_file)
            with open(self.vault_file,"wb") as f: f.write(encrypt_data(nk, json.dumps(self.vault)))
            self.key = nk; ok.config(text="\u2705  Password changed!")
            win.after(2000, win.destroy)
        br = tk.Frame(pad, bg=SURFACE); br.pack(fill="x", pady=(8,0))
        mk_btn(br, "Cancel", win.destroy, bg=SURFACE2, fg=MUTED, w=12).pack(side="left")
        mk_btn(br, "Change Password", do, w=18).pack(side="right")
        win.after(50, lambda: _apply_dwm_to_widget(win))

    @staticmethod
    def _show_about_static(root):
        win = tk.Toplevel(root); win.transient(root); win.title("About MARAi")
        win.configure(bg=SURFACE); win.resizable(False, False); win.grab_set()
        try:
            _ico = getattr(root, "_ico_path", None)
            if _ico: win.iconbitmap(_ico)
        except: pass
        _centre_on_parent(win, root, 520, 560)
        VaultApp._build_about_content(win, root)
        win.after(50, lambda: _apply_dwm_to_widget(win))

    @staticmethod
    def _build_about_content(win, root):
        hdr = tk.Frame(win, bg=SURFACE, padx=30, pady=20); hdr.pack(fill="x")
        ac = tk.Canvas(hdr, width=64, height=64, bg=SURFACE, highlightthickness=0); ac.pack()
        _draw_concentric_logo(ac, 32, 32, 32, SURFACE)
        tk.Label(hdr, text="M  A  R  A  i", font=("Segoe UI",18,"bold"), fg=ACCENT, bg=SURFACE).pack()
        tk.Label(hdr, text=f"Version {VERSION}", font=FNT_SM, fg=MUTED, bg=SURFACE).pack(pady=(2,0))
        tk.Frame(win, bg=BORDER, height=1).pack(fill="x", padx=30, pady=(12,0))
        tk.Label(win, text="What's New", font=("Segoe UI",10,"bold"), fg=TEXT, bg=SURFACE
                 ).pack(anchor="w", padx=30, pady=(10,4))
        sf = tk.Frame(win, bg=SURFACE, height=160); sf.pack(fill="x", padx=30)
        sf.pack_propagate(False)
        cv = tk.Canvas(sf, bg=SURFACE, highlightthickness=0)
        sb = mk_scrollbar(sf, orient="vertical", command=cv.yview)
        inner = tk.Frame(cv, bg=SURFACE)
        inner.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.create_window((0,0), window=inner, anchor="nw"); cv.configure(yscrollcommand=sb.set)
        cv.pack(side="left", fill="both", expand=True); sb.pack(side="right", fill="y")
        _install_scroll_router(win)
        _make_scrollable(cv)
        for ver, note in CHANGELOG:
            row = tk.Frame(inner, bg=SURFACE); row.pack(fill="x", pady=3)
            tk.Label(row, text=f" v{ver} ", font=("Consolas",9,"bold"),
                     bg=ACCENT if ver==VERSION else SURFACE2,
                     fg="white" if ver==VERSION else MUTED, width=8).pack(side="left")
            tk.Label(row, text=note, font=FNT_SM, fg=TEXT if ver==VERSION else MUTED,
                     bg=SURFACE, anchor="w", wraplength=340, justify="left"
                     ).pack(side="left", padx=(10,0), fill="x")
        tk.Frame(win, bg=BORDER, height=1).pack(fill="x", padx=30, pady=(12,0))
        ftr = tk.Frame(win, bg=SURFACE, padx=30, pady=14); ftr.pack(fill="x")
        tk.Label(ftr, text="Use \uff0b Vault in the tab bar to open multiple vaults.",
                 font=FNT_SM, fg=MUTED, bg=SURFACE, justify="center").pack()
        gh = f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}"
        gl = tk.Label(ftr, text=gh, font=FNT_SM, fg=ACCENT, bg=SURFACE, cursor="hand2")
        gl.pack(pady=(6,0))
        gl.bind("<Button-1>", lambda e: webbrowser.open(gh))
        gl.bind("<Enter>", lambda e: gl.config(fg=GREEN)); gl.bind("<Leave>", lambda e: gl.config(fg=ACCENT))
        mk_btn(ftr, "Close", lambda: [win.grab_release(), win.destroy()],
               bg=SURFACE2, fg=MUTED, w=10).pack(pady=(14,0))

    def _show_about(self):
        VaultApp._show_about_static(self.winfo_toplevel())

    def _add_entry(self):
        def on_save(r): self.vault.insert(0,r); self._save_vault(); self._render()
        EntryDialog(self.winfo_toplevel(), on_save, vault=self.vault)

    def _resolve_credential(self, entry):
        """Resolve linked Domain Credential for a server entry.
        Returns (username, password) from linked cred or entry's own fields."""
        cred_ref = entry.get("credential_ref", "").strip()
        if cred_ref:
            for v in self.vault:
                if _entry_cat(v) == "Domain Credential" and v.get("name") == cred_ref:
                    return v.get("user", ""), v.get("password", "")
        return entry.get("user", ""), entry.get("password", "")

    def _rdp_connect(self, idx):
        e = self.vault[idx]; h = e.get("host","").strip(); p = e.get("port","3389").strip()
        u, pw = self._resolve_credential(e)
        u = u.strip(); ws = e.get("workspace","").strip()
        if not ws and not h:
            messagebox.showwarning("Missing","No host/workspace.",parent=self.winfo_toplevel()); return
        # For AVD: copy password securely THEN launch after a brief delay
        # For standard RDP: password goes via CredWriteW, no clipboard needed
        if ws:
            # AVD needs longer clipboard time — user may need to paste password twice
            self._copy_secure(pw, clear_after=90)
            self.after(150, lambda: self._do_rdp_launch(h, p, u, pw, ws))
        else:
            ok, err = _launch_rdp(h, p, u, pw, ws)
            if not ok: messagebox.showerror("Error", str(err), parent=self.winfo_toplevel())

    def _do_rdp_launch(self, h, p, u, pw, ws):
        ok, err = _launch_rdp(h, p, u, pw, ws)
        if not ok: messagebox.showerror("Error", str(err), parent=self.winfo_toplevel())

    def _edit(self, idx):
        def on_save(r):
            self.vault[idx] = r; self._save_vault(); self._render()
            if self._detail_idx == idx: self._refresh_detail()
        EntryDialog(self.winfo_toplevel(), on_save, entry=self.vault[idx], vault=self.vault)

    def _delete(self, idx):
        if messagebox.askyesno("Delete",f"Delete '{self.vault[idx]['name']}'?",parent=self.winfo_toplevel()):
            if self._detail_idx == idx: self._close_detail()
            elif self._detail_idx is not None and self._detail_idx > idx: self._detail_idx -= 1
            del self.vault[idx]; self._save_vault(); self._render()

    def _move_entry(self, idx, direction):
        """Move entry up (-1) or down (+1) in the vault list."""
        new_idx = idx + direction
        if new_idx < 0 or new_idx >= len(self.vault): return
        self.vault[idx], self.vault[new_idx] = self.vault[new_idx], self.vault[idx]
        # Update detail panel index if it was tracking either entry
        if self._detail_idx == idx:
            self._detail_idx = new_idx
        elif self._detail_idx == new_idx:
            self._detail_idx = idx
        self._save_vault(); self._render()
        if self._detail_idx is not None:
            self._refresh_detail()


# == Helpers ================================================================
def _launch_rdp(host, port, username, password, workspace=""):
    if workspace:
        if sys.platform == "win32":
            try:
                import urllib.parse
                uri = f"ms-avd:connect?workspaceId={urllib.parse.quote(workspace, safe='')}"
                subprocess.run(["cmd","/c","start","",uri], capture_output=True, timeout=5)
                return True, None
            except: pass
        try: webbrowser.open(workspace); return True, None
        except Exception as e: return False, str(e)
    target = f"{host}:{port}" if port and str(port)!="3389" else host
    if sys.platform == "win32":
        try:
            from ctypes import wintypes
            class CRED(ctypes.Structure):
                _fields_ = [("Flags",wintypes.DWORD),("Type",wintypes.DWORD),
                    ("TargetName",wintypes.LPWSTR),("Comment",wintypes.LPWSTR),
                    ("LastWritten",ctypes.c_int64),("CredentialBlobSize",wintypes.DWORD),
                    ("CredentialBlob",ctypes.POINTER(ctypes.c_byte)),
                    ("Persist",wintypes.DWORD),("AttributeCount",wintypes.DWORD),
                    ("Attributes",ctypes.c_void_p),("TargetAlias",wintypes.LPWSTR),
                    ("UserName",wintypes.LPWSTR)]
            adv = ctypes.windll.advapi32
            pb = (password+"\x00").encode("utf-16-le"); blob = (ctypes.c_byte*len(pb))(*pb)
            cred = CRED(); cred.Flags=0; cred.Type=1
            cred.TargetName=f"TERMSRV/{target}"; cred.Comment="Added by Marai"
            cred.CredentialBlobSize=len(pb); cred.CredentialBlob=blob
            cred.Persist=1; cred.UserName=username
            adv.CredWriteW(ctypes.byref(cred), 0)
            subprocess.Popen(["mstsc.exe", f"/v:{target}"])
            def _cl():
                _time.sleep(10)
                try: adv.CredDeleteW(f"TERMSRV/{target}", 1, 0)
                except: pass
            threading.Thread(target=_cl, daemon=True).start()
            return True, None
        except Exception as e: return False, str(e)
    else:
        try:
            subprocess.Popen(["xfreerdp",f"/v:{target}",f"/u:{username}",
                              f"/p:{password}","/cert:ignore","+clipboard"])
            return True, None
        except FileNotFoundError:
            return False, "xfreerdp not found. Install: sudo apt install freerdp2-x11"
        except Exception as e: return False, str(e)

def _restart_app():
    try:
        if getattr(sys,"frozen",False): os.execv(sys.executable, [sys.executable])
        else: os.execv(sys.executable, [sys.executable]+sys.argv)
    except: sys.exit(0)

def _centre_on_parent(win, parent, w, h):
    win.withdraw()
    try:
        parent.update_idletasks(); win.update_idletasks()
        px=parent.winfo_rootx(); py=parent.winfo_rooty()
        pw_=parent.winfo_width(); ph=parent.winfo_height()
        x = px + (pw_-w)//2; y = py + (ph-h)//2
        x = max(px-pw_, min(x, px+pw_)); y = max(py-ph, min(y, py+ph))
    except:
        sw=win.winfo_screenwidth(); sh=win.winfo_screenheight()
        x=(sw-w)//2; y=(sh-h)//2
    win.geometry(f"{w}x{h}+{x}+{y}"); win.deiconify(); win.lift(); win.focus_force()

def _apply_dwm_to_widget(widget):
    try:
        GA_ROOT=2; inner=widget.winfo_id()
        hwnd = ctypes.windll.user32.GetAncestor(inner, GA_ROOT)
        if not hwnd: hwnd = inner
        _apply_dwm_dark_titlebar(hwnd)
    except: pass

def _apply_dwm_dark_titlebar(hwnd):
    palette = _ALL_PALETTES.get(_CURRENT_THEME, _DARK_PALETTE)
    try:
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 20, ctypes.byref(ctypes.c_int(palette["_dwm_dark"])),
            ctypes.sizeof(ctypes.c_int))
    except: pass
    try:
        r,g,b = palette["_dwm_r"], palette["_dwm_g"], palette["_dwm_b"]
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 35, ctypes.byref(ctypes.c_int(r|(g<<8)|(b<<16))),
            ctypes.sizeof(ctypes.c_int))
    except: pass
    try:
        tc = TEXT.lstrip("#")
        r2,g2,b2 = int(tc[0:2],16), int(tc[2:4],16), int(tc[4:6],16)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 36, ctypes.byref(ctypes.c_int(r2|(g2<<8)|(b2<<16))),
            ctypes.sizeof(ctypes.c_int))
    except: pass


# == App Root ===============================================================
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MARAi"); self.configure(bg=BG)
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w = max(1100, min(int(sw*0.80), 1500))
        h = max(680, min(int(w*0.6), sh-80))
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
        self.resizable(True, True); self.minsize(860, 540)
        self._set_icon()
        self._vaults = []; self._active_tab = -1
        self._tab_bar = tk.Frame(self, bg=SURFACE,
                                 highlightbackground=BORDER, highlightthickness=1)
        self._tab_bar.pack(fill="x", side="top")
        self._content = tk.Frame(self, bg=BG)
        self._content.pack(fill="both", expand=True)
        self._open_vault_in_tab(CONFIG_DIR, primary=True)
        # Restore previously added vault tabs
        for vd in _get_saved_vault_tabs():
            if os.path.normpath(vd) != os.path.normpath(CONFIG_DIR) and os.path.isdir(vd):
                self._open_vault_in_tab(vd)
        # Show first tab, hide others
        if len(self._vaults) > 1:
            for w in self._content.winfo_children(): w.pack_forget()
            self._active_tab = 0
            self._apply_vault_theme(0)
            f = self._vaults[0].get("frame")
            if f and f.winfo_exists(): f.pack(fill="both", expand=True)
            else: self._show_lock_for(0)
            self._rebuild_tab_bar()
        self.after(100, self._apply_theme)

    def _rebuild_tab_bar(self):
        # Update tab bar frame colors to match current theme
        self._tab_bar.config(bg=SURFACE, highlightbackground=BORDER)
        for w in self._tab_bar.winfo_children(): w.destroy()
        for i, v in enumerate(self._vaults):
            ia = (i == self._active_tab)
            tb = ACCENT if ia else SURFACE2; tf = "white" if ia else MUTED
            tab = tk.Frame(self._tab_bar, bg=tb); tab.pack(side="left", padx=(4 if i==0 else 0,0), pady=4)
            st = "\U0001f513" if v.get("key") else "\U0001f512"
            nm = v["name"][:20]+("\u2026" if len(v["name"])>20 else "")
            lbl = tk.Label(tab, text=f" {st} {nm} ", font=("Segoe UI",9,"bold" if ia else "normal"),
                           bg=tb, fg=tf, padx=8, pady=5, cursor="hand2")
            lbl.pack(side="left"); lbl.bind("<Button-1>", lambda e, idx=i: self._switch_tab(idx))
            if len(self._vaults)>1:
                xl = tk.Label(tab, text="\u2715", font=("Segoe UI",8), bg=tb,
                              fg="white" if ia else MUTED, padx=4, pady=5, cursor="hand2")
                xl.pack(side="left"); xl.bind("<Button-1>", lambda e, idx=i: self._close_tab(idx))
        ab = tk.Label(self._tab_bar, text="  \uff0b Vault  ", font=("Segoe UI",9),
                      bg=SURFACE2, fg=MUTED, padx=6, pady=5, cursor="hand2")
        ab.pack(side="left", padx=8, pady=4)
        ab.bind("<Button-1>", lambda e: self._add_vault_dialog())
        ab.bind("<Enter>", lambda e: ab.config(fg=ACCENT))
        ab.bind("<Leave>", lambda e: ab.config(fg=MUTED))

    def _switch_tab(self, idx):
        if idx == self._active_tab: return
        if 0 <= self._active_tab < len(self._vaults):
            f = self._vaults[self._active_tab].get("frame")
            if f and f.winfo_exists(): f.pack_forget()
        self._active_tab = idx; v = self._vaults[idx]
        # Apply this vault's theme
        self._apply_vault_theme(idx)
        if v.get("frame") and v["frame"].winfo_exists():
            # Rebuild the vault UI with the correct theme colors
            f = v["frame"]
            if v.get("key"):
                f.destroy()
                self._show_vault_for(idx)
            else:
                f.pack(fill="both", expand=True)
        else: self._show_lock_for(idx)
        self._rebuild_tab_bar()

    def _close_tab(self, idx):
        if len(self._vaults) <= 1: return
        v = self._vaults.pop(idx)
        # Immediately update tab bar for responsive feel
        new_active = min(self._active_tab, len(self._vaults) - 1)
        if self._active_tab > idx: new_active = self._active_tab - 1
        self._active_tab = new_active
        self._rebuild_tab_bar()
        self.update_idletasks()
        # Now destroy the frame (may be slow for large vaults)
        f = v.get("frame")
        if f and f.winfo_exists(): f.destroy()
        self._switch_tab(self._active_tab)
        self._persist_vault_tabs()

    def _open_vault_in_tab(self, vault_dir, primary=False):
        vf = os.path.join(vault_dir, "vault.enc")
        mf = os.path.join(vault_dir, "meta.json")
        name = os.path.basename(vault_dir.rstrip("/\\")) or vault_dir
        theme = _get_vault_theme(vault_dir)
        self._vaults.append({"dir": vault_dir, "key": None, "name": name,
                             "vault_file": vf, "meta_file": mf, "frame": None,
                             "theme": theme})
        self._active_tab = len(self._vaults)-1
        self._apply_vault_theme(self._active_tab)
        self._rebuild_tab_bar(); self._show_lock_for(self._active_tab)

    def _apply_vault_theme(self, idx):
        """Apply the theme associated with vault[idx]."""
        v = self._vaults[idx]
        theme_name = v.get("theme", "Dark")
        if theme_name not in _ALL_PALETTES: theme_name = "Dark"
        _apply_theme_by_name(theme_name)
        self.configure(bg=BG)
        self._content.config(bg=BG)
        self._tab_bar.config(bg=SURFACE, highlightbackground=BORDER)
        _apply_dwm_to_widget(self)

    def _show_lock_for(self, idx):
        for w in self._content.winfo_children():
            if hasattr(w, "_vault_tab_idx") and w._vault_tab_idx != idx: w.pack_forget()
        v = self._vaults[idx]; _refresh_paths(v["dir"])
        frame = tk.Frame(self._content, bg=BG); frame._vault_tab_idx = idx
        frame.pack(fill="both", expand=True); v["frame"] = frame
        def _on_unlock(key, _idx=idx, _frame=frame):
            _frame.destroy(); self._vaults[_idx]["key"] = key
            self._show_vault_for(_idx)
        LockScreen(frame, on_unlock=_on_unlock,
                   vault_file=v["vault_file"], meta_file=v["meta_file"])
        self.after(30, self._apply_theme)

    def _show_vault_for(self, idx):
        v = self._vaults[idx]
        for w in self._content.winfo_children(): w.pack_forget()
        frame = tk.Frame(self._content, bg=BG); frame._vault_tab_idx = idx
        frame.pack(fill="both", expand=True); v["frame"] = frame
        def _on_lock(_idx=idx, _frame=frame):
            _frame.destroy(); self._vaults[_idx]["key"] = None
            self._vaults[_idx]["frame"] = None
            self._show_lock_for(_idx); self._rebuild_tab_bar()
        VaultApp(frame, key=v["key"], on_lock=_on_lock,
                 vault_file=v["vault_file"], meta_file=v["meta_file"])
        self._rebuild_tab_bar(); self.after(30, self._apply_theme)

    def _add_vault_dialog(self):
        from tkinter import filedialog
        vd = filedialog.askdirectory(title="Open or Create Vault",
            initialdir=os.path.expanduser("~"), parent=self)
        if not vd: return
        for v in self._vaults:
            if os.path.normpath(v["dir"]) == os.path.normpath(vd):
                messagebox.showinfo("Already open", f"Already open:\n{vd}", parent=self); return
        self._open_vault_in_tab(vd)
        self._persist_vault_tabs()

    def _persist_vault_tabs(self):
        """Save the current list of extra vault directories to config."""
        extra = [v["dir"] for v in self._vaults
                 if os.path.normpath(v["dir"]) != os.path.normpath(CONFIG_DIR)]
        _save_vault_tabs(extra)

    def _apply_theme(self):
        self.configure(bg=BG)
        self._content.config(bg=BG)
        self._rebuild_tab_bar()
        _apply_dwm_to_widget(self)

    def _set_icon(self):
        base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        ico = os.path.join(base, "marai.ico")
        if os.path.exists(ico):
            try: self.iconbitmap(ico)
            except: pass
        self._ico_path = ico if os.path.exists(ico) else None
        try: ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ManPlate.MARAi.PasswordManager")
        except: pass


if __name__ == "__main__":
    if not CRYPTO_OK:
        print("ERROR: run:  pip install cryptography pyperclip")
        sys.exit(1)
    App().mainloop()
