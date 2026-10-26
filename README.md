# Little Garage Mahal — TV welcome screen

Live at **https://littlegaragemahal.github.io/welcome/** (shown full-screen on the Fire Stick).

## Day to day
Edit the Google Sheet. Changes appear on the TV within about a minute.

- `guest_name` — **first name only** (this is a public web page)
- `guest_checkin` — that guest's check-in date; the name only shows during that stay
- `welcome_note` — optional, keep it generic
- `announcement` — optional gold banner

## How it works
- `index.html` — the screen. Reads the Sheet (link set in `SHEET_CSV_URL`) and `stay.json`.
- `.github/workflows/publish.yml` — publishes the site on every change and every 3 hours,
  refreshing stay dates from the Airbnb calendar (secret `AIRBNB_ICAL`).
- `stay.json` is built fresh each run and never committed, so no booking history is kept here.

## Settings this repo needs
- **Settings → Pages → Source: GitHub Actions**
- **Settings → Secrets and variables → Actions → `AIRBNB_ICAL`** = Airbnb calendar export link
