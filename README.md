# Studio Finder · Neuchâtel

Finds **flats and studios to rent** within **25 minutes by car** of Philip Morris International (The Cube,
Quai Jeanrenaud 3, Neuchâtel-Serrières) – 88 places in the cantons of Neuchâtel, Bern, Vaud and Fribourg – and
e-mails you every morning with new flats and rent reductions. Every flat shows its **commute to work by car and by
public transport**, because that matters as much as the rent.

* **Web app** (`docs/`, GitHub Pages): list / map / table, filters by commute (car and/or public transport),
  rent, type (studio …), size, furnished, place, features and warnings (sublet, flat-share, students-only …),
  sort by best value or total monthly cost (rent + commute), a "Places & prices" view with a rent-vs-commute
  chart, favorites, notes, saved searches, share links.
* **Search job** (`scraper/`, GitHub Actions, 06:15 with e-mail and 17:15 refresh): reads all sources, merges the
  same flat advertised on several sites, tracks rent changes and removed ads, computes commute times, sends the
  e-mail.

## Sources

| Kind | Sources |
|---|---|
| Portals | Flatfox (API), immobilier.ch, Newhome (API), petitesannonces.ch (private landlords) |
| Aggregators | Comparis, RealAdvisor – they also carry the ads of Homegate, ImmoScout24 and many agencies |
| Property managers (régies) | CPCN, Charles-Berset, Gérance Métropole, GHB, RVK, GPC, Jouval, BZ Immobilier, Fidimmobil, Optigestion, Duboux |
| Check manually / own alerts | Homegate, ImmoScout24, anibis, tutti, Naef, City of Neuchâtel … (listed in the app under **Sources**) |

Sites that block automated access are **not** circumvented: the search stops for that site and reports it in the
e-mail's source status. Their ads mostly arrive through the aggregators; for complete coverage create a free e-mail
alert directly on Homegate / ImmoScout24 / anibis.

Add any further property-manager page in `config/sources.json` (`sites`: name + URL, optionally a `link_pattern`).

## Commute times

* **Car**: OpenStreetMap road network via the OSRM routing service (free-flow – add a few minutes at rush hour).
* **Public transport**: search.ch timetable, best connection arriving around 08:00 on a working day, door to door.
* Flats with a published address get exact times (cached in `docs/data/commute_cache.json`); otherwise the time from
  the centre of the village/town is shown with "≈".
* The area is built by `python -m scraper.tools.build_localities` from `config/search.json` (workplace and maximum
  driving time) – change the workplace there to search around another place.

## The daily e-mail

Set your filters in the app, click **✉️ Copy as e-mail filter (JSON)**, open `config/email_filters.json` on GitHub
(pencil icon), paste, *Commit changes*. Example – studios up to CHF 900 within 20 minutes by car:

```json
{ "rent_max": 900, "types": ["studio"], "max_car_min": 20, "commute_mode": "car" }
```

Secrets used by the workflow: `SMTP_USER`, `SMTP_PASSWORD` (Gmail app password), `EMAIL_TO`; variable `APP_URL`.

## Running locally

```bash
pip install -r requirements.txt
python -m scraper.run --no-email          # scrape, writes docs/data/*.json
python -m http.server -d docs 8000        # open http://localhost:8000
```

Without SMTP variables the e-mail is written to `out/email_preview.html`.
