#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Nyhetsovervåking: Nødvarsel.no
Overvåker RSS-feeden for AKTIVE nødvarsler og sender breaking alerts til Slack.
Laget for å kjøre som en cron-jobb på en Raspberry Pi.
"""

import json
import logging
import os
import sys
from dotenv import load_dotenv
import feedparser
import requests

# Laster miljøvariabler fra .env umiddelbart etter import
load_dotenv()

# --- KONFIGURASJON ---
RSS_URL = "https://www.nodvarsel.no/rss/rss-aktive-nodvarsler/"
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

if not SLACK_WEBHOOK_URL:
    raise ValueError("Kritisk feil: SLACK_WEBHOOK_URL er ikke konfigurert i .env-filen.")

# Filsti for å huske hvilke varsler som allerede er pushet (unngå duplikater)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SEEN_FILE = os.path.join(BASE_DIR, "seen_nodvarsler.json")

# Sett opp logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def load_seen():
    """Laster inn ID-er for varsler vi allerede har sendt til Slack"""
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []


def save_seen(seen_list):
    """Lagrer ID-er for sendte varsler. Tar vare på de siste 50."""
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(seen_list[-50:], f)


def send_to_slack(entry):
    """Bygger en synlig og tydelig Slack-melding (Slack Blocks) for redaksjonen"""
    title = entry.get("title", "Nytt Nødvarsel")
    link = entry.get("link", "https://www.nodvarsel.no")
    description = entry.get("description", "Ingen ytterligere detaljer oppgitt.")
    published = entry.get("published", "Ukjent tidspunkt")

    payload = {
        "text": f"🚨 NYTT NØDVARSEL: {title}",
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🚨 AKTIVT NØDVARSEL",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{title}*\n\n{description}\n\n*Tidspunkt:* {published}"
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Les mer på Nødvarsel.no"
                        },
                        "url": link,
                        "style": "danger"
                    }
                ]
            }
        ]
    }

    try:
        resp = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=10)
        resp.raise_for_status()
        logging.info(f"Varslet Slack vellykket om: {title}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Klarte ikke å sende til Slack. Feil: {e}")


def main():
    logging.info("Sjekker Nødvarsel.no for nye aktive varsler...")
    feed = feedparser.parse(RSS_URL)
    
    if feed.bozo and not feed.entries:
        logging.error(f"Feil ved parsing av RSS-feed: {feed.bozo_exception}")
        sys.exit(1)

    seen = load_seen()
    new_alerts_sent = False

    for entry in feed.entries:
        alert_id = entry.get("id", entry.get("link"))

        if alert_id not in seen:
            logging.info(f"Nytt varsel oppdaget: {entry.get('title')}")
            send_to_slack(entry)
            seen.append(alert_id)
            new_alerts_sent = True

    if new_alerts_sent:
        save_seen(seen)
        logging.info("Listen over publiserte varsler ble oppdatert.")
    else:
        logging.info("Ingen nye aktive nødvarsler funnet.")


if __name__ == "__main__":
    main()
