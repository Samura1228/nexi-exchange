import os
import json
import logging
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

from config import SPREADSHEET_ID
CREDENTIALS_FILE = "credentials.json"

# Initialize Google Sheets client
gc = None
sheet = None

try:
    if not SPREADSHEET_ID:
        raise ValueError("SPREADSHEET_ID is not set in the environment variables.")

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    google_credentials_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    if google_credentials_json:
        creds_info = json.loads(google_credentials_json)
        credentials = Credentials.from_service_account_info(creds_info, scopes=scopes)
    elif os.path.exists(CREDENTIALS_FILE):
        credentials = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
    else:
        raise FileNotFoundError(f"Neither GOOGLE_CREDENTIALS_JSON env var nor {CREDENTIALS_FILE} found.")

    gc = gspread.authorize(credentials)
    sheet = gc.open_by_key(SPREADSHEET_ID).sheet1
    logging.info("Google Sheets integration initialized successfully.")
except Exception as e:
    logging.warning(f"Google Sheets integration disabled: {e}")

def log_action(user_id, username, action_type, details):
    """
    Logs an action to the Google Sheet.
    """
    if not sheet:
        return

    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row = [timestamp, str(user_id), username or "", action_type, details]
        sheet.append_row(row)
    except Exception as e:
        logging.error(f"Failed to log action to Google Sheets: {e}")