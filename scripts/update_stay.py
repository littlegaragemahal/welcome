"""Read the Airbnb calendar export and write stay.json for the welcome screen.

Usage: python scripts/update_stay.py <output path>

Only check-in/checkout dates for the current stay and the next few days are
written. No guest names, phone digits or reservation codes ever leave the
private calendar link, which is stored as the AIRBNB_ICAL repository secret.
The file is published with the site but never committed, so no history of
past stays builds up in the repository.
"""
import json
import os
import re
import sys
import urllib.request
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

LOOKAHEAD_DAYS = 3
TZ = ZoneInfo("America/Chicago")


def unfold(text):
    lines = []
    for raw in text.replace("\r\n", "\n").split("\n"):
        if raw.startswith((" ", "\t")) and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw)
    return lines


def to_date(value):
    value = value.strip()[:8]
    return date(int(value[:4]), int(value[4:6]), int(value[6:8]))


def read_stays(url):
    req = urllib.request.Request(url, headers={"User-Agent": "lgm-welcome-screen"})
    with urllib.request.urlopen(req, timeout=30) as res:
        text = res.read().decode("utf-8", "replace")
    if "BEGIN:VCALENDAR" not in text:
        raise ValueError("that link didn't return a calendar")

    today = datetime.now(TZ).date()
    horizon = today + timedelta(days=LOOKAHEAD_DAYS)
    stays, event = [], None
    for line in unfold(text):
        if line == "BEGIN:VEVENT":
            event = {}
        elif line == "END:VEVENT" and event is not None:
            # Airbnb marks real bookings "Reserved"; host blocks say "Not available".
            if "reserved" in event.get("SUMMARY", "").lower() and "DTSTART" in event and "DTEND" in event:
                start, end = to_date(event["DTSTART"]), to_date(event["DTEND"])
                if end >= today and start <= horizon:
                    stays.append({"start": start.isoformat(), "end": end.isoformat()})
            event = None
        elif event is not None and ":" in line:
            key, value = line.split(":", 1)
            event[key.split(";", 1)[0].upper()] = value
    return sorted(stays, key=lambda s: s["start"])


def parse_day(text, today):
    """2026-10-29, 10/29/2026, 10/29/26 or 10/29 (year guessed)."""
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if m:
        return date(int(m[1]), int(m[2]), int(m[3]))
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?", text)
    if not m:
        return None
    if m[3]:
        year = int(m[3]) + (2000 if len(m[3]) == 2 else 0)
        return date(year, int(m[1]), int(m[2]))
    d = date(today.year, int(m[1]), int(m[2]))
    return d.replace(year=today.year + 1) if (today - d).days > 60 else d


def extra_stays(text):
    """Stays typed into the EXTRA_STAYS repository variable, one per line:
        10/29 to 11/1 Marla, Marlo & Rachel
    Two dates (check-in, then checkout) and an optional first-name greeting.
    A line whose dates match an Airbnb booking just adds the name to it."""
    today = datetime.now(TZ).date()
    horizon = today + timedelta(days=LOOKAHEAD_DAYS)
    stays = []
    for line in (text or "").splitlines():
        matches = list(re.finditer(r"\d{4}-\d{1,2}-\d{1,2}|\d{1,2}/\d{1,2}(?:/\d{2,4})?", line))
        if len(matches) < 2:
            continue
        found = [m.group(0) for m in matches[:2]]
        name = re.sub(r"^[\s\-–—:,.]+", "", line[matches[1].end():]).strip()[:60]
        start, end = parse_day(found[0], today), parse_day(found[1], today)
        if not start or not end:
            continue
        if end < start:  # e.g. 12/30 to 1/2
            end = end.replace(year=end.year + 1)
        if end >= today and start <= horizon:
            stay = {"start": start.isoformat(), "end": end.isoformat()}
            if name:
                stay["name"] = name
            stays.append(stay)
    return stays


def live_stays():
    """If Airbnb is unreachable, reuse what the live site already shows."""
    url = os.environ.get("LIVE_STAY_URL", "").strip()
    if not url:
        return []
    try:
        with urllib.request.urlopen(url, timeout=20) as res:
            return json.load(res).get("stays", [])
    except Exception:
        return []


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "stay.json"
    url = os.environ.get("AIRBNB_ICAL", "").strip()
    stays = []
    if not url:
        # Still publish the site; the screen falls back to dates typed in the Sheet.
        print("::warning::AIRBNB_ICAL secret is not set — publishing without calendar dates.")
    else:
        try:
            stays = read_stays(url)
        except Exception as e:  # never block a publish over the calendar
            print(f"::warning::Couldn't read the Airbnb calendar ({e}) — keeping the dates already live.")
            stays = live_stays()
    for extra in extra_stays(os.environ.get("EXTRA_STAYS", "")):
        same = [s for s in stays if s["start"] == extra["start"] and s["end"] == extra["end"]]
        if same:
            if extra.get("name"):
                same[0]["name"] = extra["name"]
        else:
            stays.append(extra)
    stays.sort(key=lambda s: s["start"])
    with open(out, "w") as f:
        json.dump({"stays": stays}, f, indent=2)
        f.write("\n")
    print("stays:", stays)


if __name__ == "__main__":
    main()
