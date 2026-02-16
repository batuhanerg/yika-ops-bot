"""Diagnostic: Read Site Viewer layout and compare Implementation Details headers."""

from __future__ import annotations

import json
import os

from dotenv import load_dotenv
load_dotenv()

import gspread
from google.oauth2.service_account import Credentials

creds_json = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
scopes = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_info(creds_json, scopes=scopes)
gc = gspread.authorize(creds)
spreadsheet = gc.open_by_key(os.environ["GOOGLE_SHEET_ID"])

viewer_ws = spreadsheet.worksheet("Site Viewer")
impl_ws = spreadsheet.worksheet("Implementation Details")

# Read all Site Viewer values
all_values = viewer_ws.get_all_values()

# Print every non-empty row with its content
print("=== SITE VIEWER LAYOUT ===")
for i, row in enumerate(all_values):
    content = [f"{j}:{cell}" for j, cell in enumerate(row) if cell.strip()]
    if content:
        print(f"  Row {i+1}: {content}")

print("\n=== IMPLEMENTATION DETAILS HEADERS (row 2) ===")
impl_headers = impl_ws.row_values(2)
for i, h in enumerate(impl_headers):
    col_letter = chr(ord("A") + i) if i < 26 else chr(ord("A") + i // 26 - 1) + chr(ord("A") + i % 26)
    print(f"  {col_letter}: {h}")

print(f"\n  Total columns: {len(impl_headers)}")
