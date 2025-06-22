from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
import gspread
from google.oauth2.service_account import Credentials
import os
import json
from typing import List, Dict, Any, Optional
from collections import defaultdict
import re
from datetime import datetime
import time
import requests
from bs4 import BeautifulSoup, Tag

app = FastAPI(
    title="AI-Powered Procurement Analysis API",
    description="Analyzes procurement data from Google Sheets to identify cost-saving opportunities through price trend analysis, cross-material benchmarking, and web-based supplier discovery.",
    version="3.0.0-final",
)

# --- CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://getonow.github.io", "http://localhost:5173", "https://akaiconsola1.vercel.app"],  # Allow your deployed frontends and local dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Google Sheets Setup ---
try:
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
    SPREADSHEET_ID = '1gSaOWf_KyZPEzjvnYrUm2KxRzUe9-UqrMBdtKQOmn3U'
    
    creds_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not creds_json:
        raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON environment variable not set.")

    creds = Credentials.from_service_account_info(
        json.loads(creds_json), scopes=SCOPES
    )
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SPREADSHEET_ID).sheet1
except Exception as e:
    print(f"ERROR: Could not connect to Google Sheets. {e}")
    sheet = None

# --- Pydantic Models ---
class ProcurementOpportunity(BaseModel):
    part_number: str
    current_supplier: str
    current_price_and_trend: str
    type: str
    description: str

class ProcurementAnalysis(BaseModel):
    summary: str
    opportunities: List[ProcurementOpportunity]
    analysis_timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

class AnalysisRequest(BaseModel):
    analysis_type: str = "full"

# --- Main Analysis Class ---
class ProcurementAnalyzer:
    def __init__(self, sheet_data: List[Dict[str, Any]]):
        self.data = self._clean_data(sheet_data)
        self.parts_by_material = self._group_by_material()

    def _clean_data(self, sheet_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        clean_data = []
        for row in sheet_data:
            # Use .get() with a default value to avoid KeyErrors for missing columns
            if row.get("Part Number") and row.get("suppliername"):
                clean_data.append(row)
        return clean_data

    def _group_by_material(self) -> Dict[str, list]:
        grouped = defaultdict(list)
        for part in self.data:
            material = str(part.get("material", "")).strip().lower()
            if material:
                grouped[material].append(part)
        return grouped

    def _parse_price(self, price_val: Any) -> Optional[float]:
        if price_val is None:
            return None
        try:
            price_str = str(price_val).strip()
            cleaned_str = re.sub(r'[€$£,\s]', '', price_str)
            match = re.search(r'(\d+\.\d+|\d+)', cleaned_str)
            return float(match.group(1)) if match else None
        except (ValueError, TypeError):
            return None

    def _get_date_from_col(self, col_name: str) -> Optional[tuple[int, int]]:
        MONTH_MAP = {
            'jan': 1, 'january': 1, 'feb': 2, 'february': 2, 'mar': 3, 'march': 3,
            'apr': 4, 'april': 4, 'may': 5, 'jun': 6, 'june': 6, 'jul': 7, 'july': 7,
            'aug': 8, 'august': 8, 'sep': 9, 'september': 9, 'oct': 10, 'october': 10,
            'nov': 11, 'november': 11, 'dec': 12, 'december': 12
        }
        clean_col_name = col_name.strip()
        
        # Fixed regex to properly match both price and Priceevoindex columns
        match = re.search(r'^(?:price|priceevoindex)(?P<month>[a-zA-Z]+)(?P<year>\d{4})$', clean_col_name, re.IGNORECASE)
        
        if not match:
            return None
        
        # Extract just the month part after removing "evoindex" if present
        full_month = match.group('month').lower()
        if full_month.startswith('evoindex'):
            month_str = full_month[8:]  # Remove "evoindex" prefix
        else:
            month_str = full_month
            
        year = int(match.group('year'))
        month_num = MONTH_MAP.get(month_str)
        
        return (year, month_num) if month_num else None

    def find_insourcing_opportunities(self, part: Dict[str, Any], price: float, latest_price_col: str) -> Optional[str]:
        material = str(part.get("material", "")).strip().lower()
        if not material or not latest_price_col:
            return None

        candidates = self.parts_by_material.get(material, [])
        best_alt = min(
            (c for c in candidates if c.get('Part Number') != part.get('Part Number') and c.get('suppliername') != part.get('suppliername')),
            key=lambda c: self._parse_price(c.get(latest_price_col)) or float('inf'),
            default=None
        )

        if best_alt:
            alt_price = self._parse_price(best_alt.get(latest_price_col))
            if alt_price and alt_price < price:
                savings = ((price - alt_price) / price) * 100
                return (f"Supplier '{best_alt.get('suppliername')}' provides a similar material ('{material}') "
                        f"via part '{best_alt.get('Part Number')}' for €{alt_price:.2f}, which is {savings:.0f}% cheaper. "
                        f"Consider requesting a quote from them for '{part.get('Part Number')}'.")
        return None

    def find_outsourcing_opportunities(self, part: Dict[str, Any]) -> Optional[str]:
        part_name = part.get("partname", part.get("Part Number", "")) # Fallback to Part Number
        query = f'"{part_name}" "{part.get("material", "")}" suppliers Europe'
        print(f"    -> Outsourcing Query: {query}")
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
        try:
            response = requests.get(f"https://www.google.com/search?q={query}", headers=headers, timeout=5)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            result = soup.find('div', class_='g')
            
            if isinstance(result, Tag):
                title_tag = result.find('h3')
                link_tag = result.find('a')

                if isinstance(title_tag, Tag) and isinstance(link_tag, Tag) and link_tag.has_attr('href'):
                    link_href_attr = link_tag['href']
                    link_href = link_href_attr[0] if isinstance(link_href_attr, list) else link_href_attr
                    
                    if isinstance(link_href, str):
                        link = link_href.split('/url?q=')[1].split('&sa=U')[0] if '/url?q=' in link_href else link_href
                        return f"Found potential supplier: '{title_tag.get_text()}'. Website: {link}. Recommendation: Benchmark for potential outsourcing."

        except requests.RequestException as e:
            print(f"    -> Web scraping failed for query '{query}': {e}")
        return None

    def run_analysis(self) -> ProcurementAnalysis:
        print("\n--- STARTING PROCUREMENT ANALYSIS (COMPLETE REWRITE) ---")
        opportunities = []

        if not self.data:
            return ProcurementAnalysis(summary="Analysis failed: No data found in sheet.", opportunities=[])

        all_cols = self.data[0].keys()
        
        price_cols = sorted(
            [col for col in all_cols if re.match(r'^price[a-zA-Z]+\d{4}$', col.strip(), re.IGNORECASE)],
            key=lambda col: self._get_date_from_col(col) or (0, 0)
        )
        index_cols = sorted(
            [col for col in all_cols if re.match(r'^Priceevoindex[a-zA-Z]+\d{4}$', col.strip(), re.IGNORECASE)],
            key=lambda col: self._get_date_from_col(col) or (0, 0)
        )
        
        print(f"DEBUG: Found {len(price_cols)} strictly matched Price Columns.")
        print(f"DEBUG: Found {len(index_cols)} strictly matched Index Columns.")
        
        TARGET_YEAR = 2025
        TARGET_MONTH = 6
        target_date_tuple = (TARGET_YEAR, TARGET_MONTH)
        print(f"INFO: Analysis is fixed to target date: {TARGET_YEAR}-{TARGET_MONTH:02d}")

        current_price_col = next((col for col in price_cols if self._get_date_from_col(col) == target_date_tuple), None)
        current_index_col = next((col for col in index_cols if self._get_date_from_col(col) == target_date_tuple), None)
        
        if not current_price_col or not current_index_col:
            summary = f"Analysis failed: Could not find both a price and index column for the target date {TARGET_YEAR}-{TARGET_MONTH:02d}."
            print(f"ERROR: {summary} (Price Col: {current_price_col}, Index Col: {current_index_col})")
            return ProcurementAnalysis(summary=summary, opportunities=[])

        print(f"Target Price Column: '{current_price_col}'")
        print(f"Target Index Column: '{current_index_col}'")

        print("\n--- STEP 1: Analyzing current month prices against market index ---")
        problem_parts = []

        for i, part in enumerate(self.data):
            part_num = part.get("Part Number", "N/A")
            latest_price = self._parse_price(part.get(current_price_col))
            
            if not latest_price:
                continue

            latest_market_price = self._parse_price(part.get(current_index_col))

            if latest_market_price and latest_price > latest_market_price:
                deviation = ((latest_price - latest_market_price) / latest_market_price) * 100
                trend_str = f"€{latest_price:.2f} ({deviation:.0f}% above market index)"
                print(f"  -> FLAG: {part_num} is {deviation:.0f}% above market index.")
                problem_parts.append(part)
                
                opportunities.append(ProcurementOpportunity(
                    part_number=part_num,
                    current_supplier=part.get("suppliername", "N/A"),
                    current_price_and_trend=trend_str,
                    type="Renegotiation",
                    description=f"This part's price is {deviation:.0f}% above the current market index. Recommend immediate renegotiation with '{part.get('suppliername', 'N/A')}'."
                ))

        print(f"\n--- STEP 2: Performing deeper analysis on {len(problem_parts)} flagged parts ---")
        
        historical_price_cols = [
            col for col in price_cols if (col_date := self._get_date_from_col(col)) and col_date <= target_date_tuple
        ]

        processed_for_outsourcing = set()
        for i, part in enumerate(problem_parts):
            part_num = part.get("Part Number", "N/A")
            print(f"\n[{i+1}/{len(problem_parts)}] Deeper Dive on Part: {part_num}")
            
            if len(historical_price_cols) >= 2:
                latest_price = self._parse_price(part.get(current_price_col))
                prev_price_col = historical_price_cols[-2] 
                prev_price = self._parse_price(part.get(prev_price_col))

                if latest_price and prev_price and latest_price > prev_price:
                    increase_percent = ((latest_price - prev_price) / prev_price) * 100
                    print(f"  -> INFO: Historical price spike of {increase_percent:.0f}% found.")
                    insourcing_desc = self.find_insourcing_opportunities(part, latest_price, current_price_col)
                    if insourcing_desc:
                        print(f"  -> SUCCESS: Found insourcing opportunity for {part_num}.")
                        opportunities.append(ProcurementOpportunity(
                            part_number=part_num,
                            current_supplier=part.get("suppliername", "N/A"),
                            current_price_and_trend=f"€{latest_price:.2f} (+{increase_percent:.0f}% spike)",
                            type="Insourcing",
                            description=insourcing_desc
                        ))

            part_identifier = (part.get("partname", part.get("Part Number", "")), part.get("material", ""))
            if part_identifier not in processed_for_outsourcing:
                print(f"  -> INFO: Checking outsourcing for {part_num}.")
                processed_for_outsourcing.add(part_identifier)
                time.sleep(1.5)
                
                outsourcing_desc = self.find_outsourcing_opportunities(part)
                if outsourcing_desc:
                    print(f"  -> SUCCESS: Found outsourcing opportunity for {part_num}.")
                    opportunities.append(ProcurementOpportunity(
                        part_number=part_num,
                        current_supplier=part.get("suppliername", "N/A"),
                        current_price_and_trend=f"€{self._parse_price(part.get(current_price_col)):.2f}",
                        type="Outsourcing",
                        description=outsourcing_desc
                    ))
                else:
                    print(f"  -> FAIL: No outsourcing opportunity found for {part_num}.")

        print("\n--- ANALYSIS COMPLETE ---")
        summary = f"Analysis complete. Found {len(opportunities)} total cost-saving opportunities across {len(problem_parts)} parts."
        return ProcurementAnalysis(summary=summary, opportunities=opportunities)

# --- API Endpoints ---
@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")

@app.post("/api/procurement-analysis", response_model=ProcurementAnalysis, tags=["Analysis"])
def analyze_procurement(
    request_body: AnalysisRequest = Body(..., example={"analysis_type": "full"})
):
    if sheet is None:
        raise HTTPException(status_code=503, detail="Google Sheets service is unavailable. Check credentials.")
    try:
        records = sheet.get_all_records()
        if not records:
            raise HTTPException(status_code=404, detail="No data found in the Google Sheet.")
            
        analysis_result = ProcurementAnalyzer(records).run_analysis()
        return analysis_result
    
    except Exception as e:
        print(f"ERROR: An unexpected error occurred during analysis: {e}")
        raise HTTPException(status_code=500, detail=f"An internal error occurred: {e}")

@app.get("/api/health", tags=["Monitoring"])
def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

# To run locally: uvicorn main:app --reload
# Ensure GOOGLE_SERVICE_ACCOUNT_JSON is set as an environment variable.