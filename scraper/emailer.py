"""Daily e-mail digest (HTML + plain text) sent through SMTP (Gmail by default).

Environment variables (set as GitHub Actions secrets):
    SMTP_USER       sender address
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
SEARCH = json.loads((ROOT / "config" / "search.json").read_text(encoding="utf-8"))
WORK = SEARCH["workplace"].get("short", "work")

FEATURE_LABELS = {
    "furnished": "Furnished", "balcony": "Balcony", "terrace": "Terrace", "garden": "Garden", "lift": "Lift",
    "parking": "Parking", "cellar": "Cellar", "own_laundry": "Own washing machine", "dishwasher": "Dishwasher",
    "view": "View", "lake": "Lake", "quiet": "Quiet", "renovated": "Renovated", "new_build": "New build",
    "near_transport": "Near public transport", "pets": "Pets ok",
}
WARNING_LABELS = {"reserved": "already reserved", "temporary": "temporary / sublet", "shared_flat": "shared flat", "students_only": "students only",
                  "seniors_only": "seniors only", "subsidized": "subsidised (conditions)", "swap": "flat swap"}


def load_filters():
    if FILTERS.exists():
        return json.loads(FILTERS.read_text(encoding="utf-8"))
    return {}


def _get(f, *keys):
    for k in keys:
        if f.get(k) not in (None, ""):
            return f[k]
    return None


def commute_ok(p, f):
    car_max, pt_max = _get(f, "max_car_min"), _get(f, "max_pt_min")
    if car_max is None and pt_max is None:
        return True
    car, pt = p.get("car_min"), p.get("pt_min")
    car_ok = car_max is None or (car is not None and car <= car_max)
    pt_ok = pt_max is None or (pt is not None and pt <= pt_max)
    mode = f.get("commute_mode") or "either"
    if mode == "car":
        return car_ok
    if mode == "pt":
        return pt_ok
    if mode == "both":
        return car_ok and pt_ok
    return (car_max is not None and car_ok) or (pt_max is not None and pt_ok)  # either


def matches(p, f):
    """Same semantics as the web app's 'Copy as e-mail filter' (docs/app.js -> emailFilterJson)."""
    def rng(val, lo, hi, allow_missing=True):
        if val is None:
            return allow_missing
        if lo is not None and val < lo:
            return False
        if hi is not None and val > hi:
            return False
        return True

    miss = f.get("include_missing_values", True)
    if not rng(p.get("price"), _get(f, "rent_min", "price_min"), _get(f, "rent_max", "price_max"), miss):
        return False
    if not rng(p.get("rooms"), f.get("rooms_min"), f.get("rooms_max"), miss):
        return False
    if not rng(p.get("living_area"), f.get("area_min"), f.get("area_max"), miss):
        return False
    if not rng(p.get("price_per_m2"), None, _get(f, "rent_per_m2_max", "price_per_m2_max"), True):
        return False
    if not commute_ok(p, f):
        return False
    if f.get("cantons") and p.get("canton") not in f["cantons"]:
        return False
    places = f.get("localities") or f.get("municipalities") or []
    if places and p.get("municipality") not in places and str(p.get("zip")) not in places:
        return False
    if f.get("types") and (p.get("property_type") or "apartment") not in f["types"]:
        return False
    if (p.get("property_type") or "apartment") in f.get("exclude_types", []):
        return False
    feats = p.get("features") or {}
    if f.get("furnished") == "yes" and not feats.get("furnished"):
        return False
    if f.get("furnished") == "no" and feats.get("furnished"):
        return False
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
    if f.get("include_keywords_any") and not any(kw.lower() in text for kw in f["include_keywords_any"]):
        return False
    return True


def chf(v):
    return "rent on request" if not v else "CHF " + f"{int(round(v)):,}".replace(",", "’")


def rent_html(p):
    if not p.get("price"):
        return "rent on request"
    detail = ""
    if p.get("rent_net") and p.get("charges"):
        detail = f" <span style='font-size:12px;color:#6b7280;font-weight:normal'>({chf(p['rent_net'])} + {int(p['charges'])} charges)</span>"
    return f"{chf(p['price'])}<span style='font-size:13px'> / month</span>{detail}"


def commute_text(p):
    parts = []
    approx = "" if p.get("commute_exact") else "≈"
    if p.get("car_min") is not None:
        parts.append(f"🚗 {approx}{round(p['car_min'])} min" + (f" ({p['car_km']:g} km)" if p.get("car_km") else ""))
    if p.get("pt_min") is not None:
        ch = p.get("pt_changes")
        parts.append(f"🚆 {'' if p.get('pt_exact') else '≈'}{p['pt_min']} min" + (f", {ch} change{'s' if ch != 1 else ''}" if ch else ", direct"))
    return (" · ".join(parts) + f" to {WORK}") if parts else ""


def _card_html(p, extra=""):
    img = (p.get("images") or [None])[0]
    facts = []
    if p.get("property_type") == "studio":
        facts.append("Studio")
    elif p.get("property_type") == "room":
        facts.append("Room")
    if p.get("rooms") and p.get("property_type") not in ("studio", "room"):
        facts.append(f"{p['rooms']:g} rooms")
    if p.get("living_area"):
        facts.append(f"{p['living_area']} m²")
    if p.get("floor") is not None:
        facts.append("ground floor" if p["floor"] == 0 else f"floor {p['floor']}")
    if p.get("available_from"):
        facts.append(f"available {p['available_from']}")
    feats = [FEATURE_LABELS[k] for k in FEATURE_LABELS if (p.get("features") or {}).get(k)]
    warns = [WARNING_LABELS[k] for k in WARNING_LABELS if (p.get("features") or {}).get(k)]
    loc = ", ".join(x for x in [p.get("street"), " ".join(x for x in (p.get("zip"), p.get("municipality")) if x)] if x)
    links = " · ".join(f'<a href="{html.escape(l["url"])}" style="color:#1d4ed8">{html.escape(l["label"])}</a>'
                       for l in (p.get("links") or [])[:5])
    img_html = (f'<td width="150" valign="top" style="padding-right:12px"><a href="{html.escape(p["url"])}">'
                f'<img src="{html.escape(img)}" width="150" height="100" style="border-radius:6px;display:block;width:150px;height:100px;object-fit:cover" alt=""></a></td>'
                if img else "")
    return f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #e5e7eb;border-radius:8px;margin:0 0 12px 0;padding:10px">
<tr>{img_html}<td valign="top" style="font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#111827">
<div style="font-size:16px;font-weight:bold;margin-bottom:4px"><a href="{html.escape(p['url'])}" style="color:#111827;text-decoration:none">{html.escape(p.get('title') or 'Flat')}</a></div>
<div style="font-size:17px;font-weight:bold;color:#047857">{rent_html(p)} {extra}</div>
<div style="color:#1e3a8a;margin:4px 0;font-weight:bold">{html.escape(commute_text(p))}</div>
<div style="color:#374151;margin:2px 0">{' · '.join(facts)}</div>
<div style="color:#6b7280">📍 {html.escape(loc)}</div>
<div style="color:#6b7280;font-size:12px;margin-top:4px">{' · '.join(feats)}</div>
{f'<div style="color:#b45309;font-size:12px">⚠ {" · ".join(warns)}</div>' if warns else ''}
<div style="font-size:12px;margin-top:6px">{links}</div>
</td></tr></table>"""


def build(state, new_ids, price_changes, run_day):
    f = load_filters()
    app_url = os.environ.get("APP_URL", "").rstrip("/")
    props = {p["id"]: p for p in state["properties"]}
    new = [props[i] for i in new_ids if i in props and props[i].get("active")]
    new_match = sorted((p for p in new if matches(p, f)), key=lambda p: (p.get("price") or 99999))
    new_other = [p for p in new if not matches(p, f)]
    drops = [(props[i], old, newp) for i, old, newp in price_changes if i in props and newp < old and matches(props[i], f)]
    first_run = not state.get("runs") or len(state["runs"]) <= 1
    active = [p for p in state["properties"] if p.get("active")]
    active_match = [p for p in active if matches(p, f)]

    parts = [f"""<div style="font-family:Arial,Helvetica,sans-serif;max-width:720px;margin:auto;color:#111827">
<h2 style="margin-bottom:4px">🔑 Studio search near {html.escape(SEARCH['workplace']['name'])} – {run_day}</h2>
<p style="color:#4b5563;margin-top:0">{len(new_match)} new matching flats · {len(drops)} rent reductions ·
{len(active_match)} of {len(active)} flats for rent in the area match your criteria
{f' · <a href="{app_url}">Open the app</a>' if app_url else ''}</p>"""]
    if first_run:
        parts.append(f"""<p style="background:#eff6ff;padding:10px;border-radius:6px">First run: all {len(active)}
flats currently for rent within {SEARCH.get('max_car_minutes', 25)} min by car of {html.escape(WORK)} have been collected.
From now on this e-mail only contains <b>new</b> flats and rent reductions. Below: the cheapest matching flats today.</p>""")
        new_match = sorted(active_match, key=lambda p: (p.get("price") or 99999))[:25]
    if new_match:
        parts.append(f"<h3>✨ {'Cheapest matching flats' if first_run else 'New flats'} ({len(new_match)})</h3>")
        parts += [_card_html(p) for p in new_match[:60]]
    elif not first_run:
        parts.append("<p>No new flats matching your criteria today.</p>")
    if drops:
        parts.append(f"<h3>📉 Rent reductions ({len(drops)})</h3>")
        parts += [_card_html(p, f'<span style="color:#b91c1c;font-size:13px"><s>{chf(old)}</s> −{round((old - newp) / old * 100)}%</span>')
                  for p, old, newp in drops[:30]]
    if new_other:
        parts.append(f"""<p style="color:#6b7280">Plus {len(new_other)} more new flats outside your filters
{f'(<a href="{app_url}#new">see them in the app</a>)' if app_url else ''}.</p>""")
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
<p style="font-size:12px;color:#6b7280">+ {web_ok} property-manager websites checked without problems.
Homegate, ImmoScout24 and anibis block automated searches: their ads mostly arrive via Comparis / RealAdvisor;
for full coverage create their own e-mail alerts (links in the app under Sources).<br>
To change the criteria of this e-mail: in the app set the filters, “Copy as e-mail filter”, paste into config/email_filters.json.</p></div>""")
    html_body = "\n".join(parts)

    lines = [f"Studio search near {SEARCH['workplace']['name']} – {run_day}",
             f"{len(new_match)} new matching flats, {len(drops)} rent reductions", ""]
    for p in new_match[:60]:
        lines.append(f"- {p.get('title')} | {chf(p.get('price'))}/month | {p.get('rooms') or '?'} rooms | "
                     f"{p.get('living_area') or '?'} m² | {p.get('zip') or ''} {p.get('municipality') or ''} | "
                     f"{commute_text(p)}\n  {p['url']}")
    for p, old, newp in drops[:30]:
        lines.append(f"- RENT ↓ {p.get('title')} | {chf(old)} -> {chf(newp)}\n  {p['url']}")
    if app_url:
        lines += ["", f"App: {app_url}"]
    if first_run:
        subject = f"🔑 Studio search started – {len(active_match)} matching flats near {WORK}"
    else:
        subject = f"🔑 {len(new_match)} new flat{'s' if len(new_match) != 1 else ''} near {WORK}" + \
                  (f", {len(drops)} rent cuts" if drops else "") + f" – {run_day}"
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
    msg["From"] = f"Studio Finder Neuchâtel <{user}>"
    msg["To"] = ", ".join(to)
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "465"))
    with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context()) as s:
        s.login(user, pw)
        s.send_message(msg)
    print(f"[email] sent to {len(to)} recipient(s)")
