"""Daily e-mail digest (HTML + plain text) sent through SMTP (Gmail by default).

Environment variables (set as GitHub Actions secrets):
    SMTP_USER       sender address, e.g. basel.apartment.alerts@gmail.com
    SMTP_PASSWORD   Gmail *App Password* (16 chars) of that account
    EMAIL_TO        comma separated recipients
    APP_URL         public URL of the web app (GitHub Pages)
    SMTP_HOST / SMTP_PORT   optional, default smtp.gmail.com:465
Without SMTP credentials the mail is written to out/email_preview.html instead.
"""
import html
import json
import os
import re
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILTERS = ROOT / "config" / "email_filters.json"

FEATURE_LABELS = {
    "balcony": "Balcony", "terrace": "Terrace", "garden": "Garden", "lift": "Elevator", "parking": "Parking",
    "new_build": "New build", "attic": "Attic", "maisonette": "Maisonette", "view": "View",
    "minergie": "Minergie/eco", "renovated": "Renovated", "quiet": "Quiet", "fireplace": "Fireplace",
    "leasehold": "⚠ Leasehold (Baurecht)", "investment_rented": "⚠ rented out", "auction": "⚠ auction",
    "reserved": "⚠ reserved",
}


def load_filters():
    if FILTERS.exists():
        return json.loads(FILTERS.read_text(encoding="utf-8"))
    return {}


def matches(p, f):
    """Same semantics as the web app's filter (docs/app.js -> matchesEmailFilter)."""
    def rng(val, lo, hi, allow_missing=True):
        if val is None:
            return allow_missing
        if lo is not None and val < lo:
            return False
        if hi is not None and val > hi:
            return False
        return True

    miss = f.get("include_missing_values", True)
    if not rng(p.get("price"), f.get("price_min"), f.get("price_max"), miss):
        return False
    if not rng(p.get("rooms"), f.get("rooms_min"), f.get("rooms_max"), miss):
        return False
    if not rng(p.get("living_area"), f.get("area_min"), f.get("area_max"), miss):
        return False
    if not rng(p.get("price_per_m2"), None, f.get("price_per_m2_max"), True):
        return False
    if not rng(p.get("year_built"), f.get("year_built_min"), None, True):
        return False
    if f.get("cantons") and p.get("canton") not in f["cantons"]:
        if not (p.get("canton") == "?" and f.get("include_unknown_location", True)):
            return False
    if f.get("districts") and p.get("district") not in f["districts"] and p.get("canton") != "?":
        return False
    if f.get("municipalities") and p.get("municipality") not in f["municipalities"] and p.get("canton") != "?":
        return False
    feats = p.get("features") or {}
    for k in f.get("require_features", []):
        if not feats.get(k):
            return False
    for k in f.get("exclude_features", []):
        if feats.get(k):
            return False
    text = f"{p.get('title', '')} {p.get('description', '')}".lower()
    for kw in f.get("exclude_keywords", []):
        if kw.lower() in text:
            return False
    if f.get("include_keywords_any"):
        if not any(kw.lower() in text for kw in f["include_keywords_any"]):
            return False
    if p.get("property_type") in f.get("exclude_types", []):
        return False
    return True


def chf(v):
    return "Price on request" if not v else "CHF " + f"{int(v):,}".replace(",", "’")


def _card_html(p, extra=""):
    img = (p.get("images") or [None])[0]
    facts = []
    if p.get("rooms"):
        facts.append(f"{p['rooms']:g} rooms")
    if p.get("living_area"):
        facts.append(f"{p['living_area']} m²")
    if p.get("price_per_m2"):
        facts.append(f"{chf(p['price_per_m2'])}/m²")
    if p.get("floor") is not None:
        facts.append("ground floor" if p["floor"] == 0 else f"floor {p['floor']}")
    if p.get("year_built"):
        facts.append(f"built {p['year_built']}")
    feats = [FEATURE_LABELS[k] for k in FEATURE_LABELS if (p.get("features") or {}).get(k)]
    loc = " ".join(x for x in [p.get("street"), p.get("zip"), p.get("municipality")] if x)
    price = "see ad" if p.get("numbers_hidden") else chf(p.get("price"))
    links = " · ".join(f'<a href="{html.escape(l["url"])}" style="color:#1d4ed8">{html.escape(l["label"])}</a>'
                       for l in (p.get("links") or [])[:5])
    img_html = (f'<td width="150" valign="top" style="padding-right:12px"><a href="{html.escape(p["url"])}">'
                f'<img src="{html.escape(img)}" width="150" height="100" style="border-radius:6px;display:block;width:150px;height:100px;object-fit:cover" alt=""></a></td>'
                if img else "")
    return f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #e5e7eb;border-radius:8px;margin:0 0 12px 0;padding:10px">
<tr>{img_html}<td valign="top" style="font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#111827">
<div style="font-size:16px;font-weight:bold;margin-bottom:4px"><a href="{html.escape(p['url'])}" style="color:#111827;text-decoration:none">{html.escape(p.get('title') or 'Apartment')}</a></div>
<div style="font-size:17px;font-weight:bold;color:#047857">{price} {extra}</div>
<div style="color:#374151;margin:4px 0">{' · '.join(facts)}</div>
<div style="color:#6b7280">{html.escape(loc)} {('(' + p['canton'] + ')') if p.get('canton') and p['canton'] != '?' else ''}</div>
<div style="color:#6b7280;font-size:12px;margin-top:4px">{' · '.join(feats)}</div>
<div style="font-size:12px;margin-top:6px">{links}</div>
</td></tr></table>"""


def build(state, new_ids, price_changes, run_day):
    f = load_filters()
    app_url = os.environ.get("APP_URL", "").rstrip("/")
    props = {p["id"]: p for p in state["properties"]}
    new = [props[i] for i in new_ids if i in props]
    new_match = [p for p in new if matches(p, f)]
    new_other = [p for p in new if not matches(p, f)]
    drops = [(props[i], old, newp) for i, old, newp in price_changes if i in props and newp < old and matches(props[i], f)]
    first_run = not state.get("runs") or len(state["runs"]) <= 1
    active = [p for p in state["properties"] if p.get("active")]
    active_match = [p for p in active if matches(p, f)]

    parts = [f"""<div style="font-family:Arial,Helvetica,sans-serif;max-width:720px;margin:auto;color:#111827">
<h2 style="margin-bottom:4px">🏠 Basel apartment search – {run_day}</h2>
<p style="color:#4b5563;margin-top:0">{len(new_match)} new matching ads · {len(drops)} price reductions ·
{len(active_match)} of {len(active)} active ads in BS/BL match your criteria
{f' · <a href="{app_url}">Open the app</a>' if app_url else ''}</p>"""]
    if first_run:
        parts.append(f"""<p style="background:#eff6ff;padding:10px;border-radius:6px">First run: all {len(active)}
current ads have been collected. From tomorrow on this e-mail only contains <b>new</b> ads and price reductions.
Below are the most recent matching ads.</p>""")
        new_match = sorted(active_match, key=lambda p: ((p.get("published") or "")[:10], bool(p.get("images")),
                                                        bool(p.get("price"))), reverse=True)[:25]
    if new_match:
        parts.append(f"<h3>✨ New ads ({len(new_match)})</h3>")
        parts += [_card_html(p) for p in new_match[:60]]
    elif not first_run:
        parts.append("<p>No new ads matching your criteria today.</p>")
    if drops:
        parts.append(f"<h3>📉 Price reductions ({len(drops)})</h3>")
        parts += [_card_html(p, f'<span style="color:#b91c1c;font-size:13px"><s>{chf(old)}</s> −{round((old - newp) / old * 100)}%</span>')
                  for p, old, newp in drops[:30]]
    if new_other:
        parts.append(f"""<p style="color:#6b7280">Plus {len(new_other)} more new ads outside your filters
{f'(<a href="{app_url}#new">see them in the app</a>)' if app_url else ''}.</p>""")
    # source health
    rows = []
    for key, s in sorted((state.get("sources") or {}).items(), key=lambda kv: (kv[1].get("kind") != "portal", kv[0])):
        ok = s.get("status") == "ok"
        if s.get("kind") != "portal" and ok:
            continue
        color = "#047857" if ok else "#b45309"
        rows.append(f'<tr><td style="padding:2px 8px">{html.escape(s.get("label", key))}</td>'
                    f'<td style="padding:2px 8px;color:{color}">{html.escape(s.get("status", ""))}</td>'
                    f'<td style="padding:2px 8px;text-align:right">{s.get("count", 0)}</td></tr>')
    web_ok = sum(1 for s in (state.get("sources") or {}).values() if s.get("kind") != "portal" and s.get("status") == "ok")
    parts.append(f"""<h4 style="margin-top:24px;color:#6b7280">Source status</h4>
<table style="font-size:12px;color:#374151;border-collapse:collapse">{''.join(rows)}</table>
<p style="font-size:12px;color:#6b7280">+ {web_ok} broker / developer websites monitored without problems.
To change the criteria: in the app use “Copy as e-mail filter” and paste it into config/email_filters.json.</p></div>""")
    html_body = "\n".join(parts)

    lines = [f"Basel apartment search – {run_day}", f"{len(new_match)} new matching ads, {len(drops)} price reductions", ""]
    for p in new_match[:60]:
        lines.append(f"- {p.get('title')} | {chf(p.get('price'))} | {p.get('rooms') or '?'} rooms | "
                     f"{p.get('living_area') or '?'} m² | {p.get('zip') or ''} {p.get('municipality') or ''}\n  {p['url']}")
    for p, old, newp in drops[:30]:
        lines.append(f"- PRICE ↓ {p.get('title')} | {chf(old)} -> {chf(newp)}\n  {p['url']}")
    if app_url:
        lines += ["", f"App: {app_url}"]
    subject = (f"🏠 {len(new_match)} new apartments" + (f", {len(drops)} price cuts" if drops else "")
               + f" – Basel {run_day}") if not first_run else f"🏠 Basel apartment search started – {len(active_match)} matching ads"
    return subject, html_body, "\n".join(lines)


def send_daily(state, new_ids, price_changes, run_day):
    subject, html_body, text_body = build(state, new_ids, price_changes, run_day)
    user, pw = os.environ.get("SMTP_USER"), os.environ.get("SMTP_PASSWORD")
    to = [a.strip() for a in re.split(r"[,;\s]+", os.environ.get("EMAIL_TO", "")) if a.strip()]
    if not (user and pw and to):
        out = ROOT / "out"
        out.mkdir(exist_ok=True)
        (out / "email_preview.html").write_text(f'<meta charset="utf-8"><h3>{html.escape(subject)}</h3>{html_body}',
                                                encoding="utf-8")
        print(f"[email] SMTP not configured -> preview written to {out / 'email_preview.html'}")
        return
    if os.environ.get("SKIP_EMPTY_EMAIL") == "1" and not new_ids and not price_changes:
        print("[email] nothing new, skipped")
        return
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"Basel Apartment Finder <{user}>"
    msg["To"] = ", ".join(to)
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "465"))
    with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context()) as s:
        s.login(user, pw)
        s.send_message(msg)
    print(f"[email] sent to {len(to)} recipient(s)")
