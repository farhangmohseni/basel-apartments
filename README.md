# Basel Apartment Finder

Finds apartments **for sale** in Basel-Stadt and Basel-Landschaft (89 municipalities), merges the same flat
advertised on several sites, and e-mails you every morning with new ads and price cuts.

* **Web app** (`docs/`): list / map / table views, ~40 filters, favorites, notes, saved searches,
  share-links, affordability calculator, market overview per municipality. Hosted for free on GitHub Pages.
* **Daily job** (`scraper/`, GitHub Actions): scrapes all sources, keeps price history, detects removed ads,
  sends the e-mail digest.

## Sources

| Kind | Sources |
|---|---|
| Aggregators (cover Homegate, ImmoScout24, Flatfox, Properstar, broker feeds) | RealAdvisor, Comparis |
| Portals | Newhome (cantonal banks' portal, API), Flatfox (API), Homegate / ImmoScout24 (through alle-immobilien.ch – links only), Engel & Völkers, Neubauprojekte.ch, immobilier.ch, Acheteur.ch (Neho), Raiffeisen Immomakler |
| Classifieds (private sellers) | tutti.ch / anibis / ricardo |
| Local brokers | LIBA & Partner, Suter Immobilien, Immoline, Immobilien-Team Schweizer, MN Immobilien, Woodtli, Livendo, Immoanker, ImmoMensch, Homevisit, Blauenstein, Avenaris, Immo Family, CK Solutions, Futuro, … |
| Check manually (block bots / JavaScript only) | listed in the app under **Sources → Check manually** |

All sources are listed in `config/sources.json`: `portals` are the built-in scrapers (set `"enabled": false`
to switch one off), `sites` are broker pages watched by the generic monitor – add any further broker page
there (name + URL; optionally a `link_pattern`).

## One-time setup (≈ 15 minutes)

### 1. A Gmail account that sends the e-mails
1. Create a new Gmail account, e.g. `basel.apartment.alerts@gmail.com`.
2. Turn on **2-Step Verification**: <https://myaccount.google.com/security>.
3. Create an **App password**: <https://myaccount.google.com/apppasswords> → name it "apartment finder" →
   copy the 16-character password.

### 2. GitHub repository
1. Create a free account on <https://github.com> and a **new public repository** (e.g. `basel-apartments`).
   (GitHub Pages is free for public repos. The listings are public ads anyway; your e-mail addresses
   and password stay private in encrypted *secrets*.)
2. Push this folder:
   ```bash
   git remote add origin https://github.com/<you>/basel-apartments.git
   git push -u origin main
   ```
3. **Settings → Secrets and variables → Actions → New repository secret**:
   * `SMTP_USER` = the bot Gmail address
   * `SMTP_PASSWORD` = the 16-character app password
   * `EMAIL_TO` = `you@gmail.com, wife@example.com`
4. Same page, tab **Variables** → `APP_URL` = `https://<you>.github.io/basel-apartments/`
5. **Settings → Pages** → Source: *Deploy from a branch* → Branch `main`, folder `/docs` → Save.
6. **Actions** tab → enable workflows → *Daily apartment search* → **Run workflow** (first run ≈ 15 min).

The job then runs every day at 06:15 (Swiss time) and the e-mail arrives shortly after.

## Changing what the e-mail contains

Open the app, set the filters, click **✉️ Copy as e-mail filter (JSON)** and paste the result into
`config/email_filters.json` on GitHub (pencil icon → *Commit changes*). Example:

```json
{ "price_max": 1200000, "rooms_min": 3.5, "area_min": 85, "cantons": ["BS", "BL"],
  "municipalities": ["Basel", "Riehen", "Binningen", "Bottmingen"],
  "require_features": ["balcony"], "exclude_features": ["leasehold", "auction"] }
```

## Running locally (optional)

```bash
pip install -r requirements.txt
python -m scraper.run --no-email          # scrape, writes docs/data/*.json
python -m http.server -d docs 8000        # open http://localhost:8000
```

Without SMTP variables the e-mail is written to `out/email_preview.html`.

## Notes

* Comparis, Homegate and ImmoScout24 use bot protection. The scraper stays polite (randomised delays, request
  caps); if a source is blocked on a given day the e-mail shows it in *Source status* and the others still run.
* Homegate/ImmoScout24 ads found via alle-immobilien.ch show “see ad” instead of numbers, because that site
  serves distorted numbers to automated visitors. When the same flat is also on an aggregator, the real
  numbers are taken from there.
* Favorites, notes and hidden ads are stored in your browser. Use *Favorites → Export / Import* to sync them
  between your phone and your partner’s.
* Affordability uses the usual Swiss bank rules (20 % equity, 5 % imputed rate + 1 % maintenance +
  amortisation ≤ ⅓ of gross income). It is an estimate, not financial advice.
