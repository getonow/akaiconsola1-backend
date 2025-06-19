from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import gspread
from google.oauth2.service_account import Credentials
import os
import json

app = FastAPI()

# Google Sheets setup
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
SPREADSHEET_ID = '1gSaOWf_KyZPEzjvnYrUm2KxRzUe9-UqrMBdtKQOmn3U'

creds = Credentials.from_service_account_info(
    json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]), scopes=SCOPES
)
client = gspread.authorize(creds)
sheet = client.open_by_key(SPREADSHEET_ID).sheet1  # Use .sheet1 or specify by name

class PartRequest(BaseModel):
    part_number: str

@app.post("/api/benchmark1")
def get_part_info(request: PartRequest):
    records = sheet.get_all_records()
    for row in records:
        # Adjust the key below to match the exact column name in your sheet
        if str(row.get("Part Number", "")).strip() == request.part_number.strip():
            return {"status": "found", "data": row}
    raise HTTPException(status_code=404, detail="Part not found")