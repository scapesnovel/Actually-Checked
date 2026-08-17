#!/usr/bin/env python3
"""
ONE-TIME SETUP (run on YOUR computer, takes 2 minutes):
Gets the long-lived YouTube OAuth refresh token that the bot uses forever.

1) pip install google-auth-oauthlib
2) Download your OAuth client JSON from Google Cloud Console
   (APIs & Services -> Credentials -> your OAuth 2.0 Client -> Download JSON)
   Save it next to this script as client_secret.json
3) python get_refresh_token.py
4) A browser opens -> log in with the CHANNEL's Google account -> allow.
5) Copy the printed CLIENT_ID / CLIENT_SECRET / REFRESH_TOKEN into
   GitHub repo Settings -> Secrets and variables -> Actions.
"""
import json

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube",
          "https://www.googleapis.com/auth/youtube.force-ssl"]

flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")

cfg = json.load(open("client_secret.json"))["installed"]
print("\n=== ADD THESE AS GITHUB ACTIONS SECRETS ===")
print(f"YT_CLIENT_ID={cfg['client_id']}")
print(f"YT_CLIENT_SECRET={cfg['client_secret']}")
print(f"YT_REFRESH_TOKEN={creds.refresh_token}")
print("===========================================")
