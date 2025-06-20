from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import gspread
from google.oauth2.service_account import Credentials
import os
import json
from typing import List, Dict, Any, Optional
from collections import defaultdict
import re
from datetime import datetime
import requests
from bs4 import BeautifulSoup, Tag

app = FastAPI(
    title="AI-Powered Procurement Analysis API",
    description="Analyzes procurement data from Google Sheets to identify cost-saving opportunities through price trend analysis, cross-material benchmarking, and web-based supplier discovery.",
    version="2.1.0",
)

# --- CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
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
    # This will be caught on startup if credentials are not valid
    print(f"ERROR: Could not connect to Google Sheets. {e}")
    sheet = None

# --- Pydantic Models for Structured IO ---
class ProcurementOpportunity(BaseModel):
    part_number: str
    current_supplier: str
    current_price_and_trend: str = Field(..., description="e.g., '€3.40 (+12% vs last month)' or '€3.40 (15% above market index)'")
    type: str = Field(..., description="'Renegotiation', 'Insourcing', or 'Outsourcing'")
    description: str = Field(..., description="Detailed explanation and next action.")

class ProcurementAnalysis(BaseModel):
    summary: str
    opportunities: List[ProcurementOpportunity]
    analysis_timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

class ProcurementAnalyzer:
    def __init__(self, sheet_data: List[Dict[str, Any]]):
        self.data = self._clean_data(sheet_data)
        self.parts_by_material = self._group_by_material()

    def _clean_data(self, sheet_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Clean and normalize sheet data."""
        clean_data = []
        for row in sheet_data:
            if row.get("Part Number") and row.get("suppliername"):
                clean_data.append(row)
        return clean_data

    def _group_by_material(self) -> Dict[str, list]:
        """Group parts by their material for cross-part analysis."""
        grouped = defaultdict(list)
        for part in self.data:
            material = str(part.get("material", "")).strip().lower()
            if material:
                grouped[material].append(part)
        return grouped

    def _parse_price(self, price_val: Any) -> Optional[float]:
        """Extract float from various price string formats."""
        if price_val is None:
            return None
        try:
            # Remove currency, whitespace, and take the first valid number
            price_str = str(price_val).strip()
            cleaned_str = re.sub(r'[€$£,\s]', '', price_str)
            match = re.search(r'(\d+\.\d+|\d+)', cleaned_str)
            return float(match.group(1)) if match else None
        except (ValueError, TypeError):
            return None

    def _find_dynamic_columns(self, pattern: re.Pattern) -> List[str]:
        """Dynamically find columns matching a given pattern."""
        if not self.data:
            return []
        # Create a date-sortable key: (YYYY, MM)
        def sort_key(col_name):
            match = re.search(r'(?P<month>[a-zA-Z]+)(?P<year>\d{4})', col_name)
            if not match: return (0, 0)
            month_str = match.group('month').lower()
            year = int(match.group('year'))
            # Convert month name to number for sorting
            try:
                month_num = datetime.strptime(month_str, '%B').month
            except ValueError:
                month_num = 0 # Should not happen with valid month names
            return (year, month_num)

        return sorted([col for col in self.data[0].keys() if pattern.match(col)], key=sort_key)

    def analyze_price_trends_and_index(self, part: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Analyzes historical prices for a single part to find trends and compare to market index."""
        price_cols = self._find_dynamic_columns(re.compile(r'price\w+\d{4}', re.IGNORECASE))
        index_cols = self._find_dynamic_columns(re.compile(r'Priceevoindex\w+\d{4}', re.IGNORECASE))
        
        if len(price_cols) < 2:
            return None

        # --- Month-over-Month Spike Analysis ---
        latest_price_col = price_cols[-1]
        prev_price_col = price_cols[-2]
        latest_price = self._parse_price(part.get(latest_price_col))
        prev_price = self._parse_price(part.get(prev_price_col))

        if latest_price and prev_price and latest_price > prev_price:
            increase_percent = ((latest_price - prev_price) / prev_price) * 100
            if increase_percent > 10.0:
                trend_str = f"€{latest_price:.2f} (+{increase_percent:.0f}% vs last month)"
                return {"trend_str": trend_str, "latest_price": latest_price, "is_spike": True, "is_above_index": False}

        # --- Market Index Deviation Analysis ---
        if index_cols and price_cols:
            latest_index_col = index_cols[-1]
            latest_market_price = self._parse_price(part.get(latest_index_col))
            if latest_price and latest_market_price and latest_price > latest_market_price:
                deviation = ((latest_price - latest_market_price) / latest_market_price) * 100
                if deviation > 10.0:
                    trend_str = f"€{latest_price:.2f} ({deviation:.0f}% above market index)"
                    return {"trend_str": trend_str, "latest_price": latest_price, "is_spike": False, "is_above_index": True}

        # --- Default/Stable Case ---
        trend_str = f"€{latest_price:.2f} (Stable)" if latest_price else "Price N/A"
        return {"trend_str": trend_str, "latest_price": latest_price, "is_spike": False, "is_above_index": False}

    def find_insourcing_opportunities(self, part: Dict[str, Any], price: float) -> Optional[str]:
        """For a part, find cheaper, similar parts from other suppliers."""
        material = str(part.get("material", "")).strip().lower()
        if not material:
            return None

        candidates = self.parts_by_material.get(material, [])
        best_alt = min(
            (c for c in candidates if c['Part Number'] != part['Part Number'] and c['suppliername'] != part['suppliername']),
            key=lambda c: self._parse_price(c.get(self._find_dynamic_columns(re.compile(r'price\w+\d{4}', re.IGNORECASE))[-1])) or float('inf'),
            default=None
        )

        if best_alt:
            alt_price = self._parse_price(best_alt.get(self._find_dynamic_columns(re.compile(r'price\w+\d{4}', re.IGNORECASE))[-1]))
            if alt_price and alt_price < price:
                savings = ((price - alt_price) / price) * 100
                return (f"Supplier '{best_alt['suppliername']}' provides a similar material ('{material}') "
                        f"via part '{best_alt['Part Number']}' for €{alt_price:.2f}, which is {savings:.0f}% cheaper. "
                        f"Consider requesting a quote from them for '{part['Part Number']}'.")
        return None

    def find_outsourcing_opportunities(self, part: Dict[str, Any]) -> Optional[str]:
        """Perform a web search to find new potential suppliers."""
        query = f'"{part.get("partname", "")}" "{part.get("material", "")}" suppliers Europe'
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
                    
                    link = link_href.split('/url?q=')[1].split('&sa=U')[0] if '/url?q=' in link_href else link_href
                    return f"Found potential supplier: '{title_tag.get_text()}'. Website: {link}. Recommendation: Benchmark for potential outsourcing."

        except requests.RequestException as e:
            print(f"Web scraping failed for query '{query}': {e}")
        return None

    def run_analysis(self) -> ProcurementAnalysis:
        opportunities = []
        processed_for_outsourcing = set()

        for part in self.data:
            trend_info = self.analyze_price_trends_and_index(part)
            if not trend_info: continue

            latest_price = trend_info["latest_price"]
            
            # Opportunity 1: Price is above market index
            if trend_info["is_above_index"]:
                opportunities.append(ProcurementOpportunity(
                    part_number=part["Part Number"],
                    current_supplier=part["suppliername"],
                    current_price_and_trend=trend_info["trend_str"],
                    type="Renegotiation",
                    description=f"This part's price is significantly above the market index. Recommend renegotiating with '{part['suppliername']}' for a price closer to the market average."
                ))

            # Opportunity 2: Price spiked recently (In-house benchmarking)
            if trend_info["is_spike"] and latest_price:
                insourcing_desc = self.find_insourcing_opportunities(part, latest_price)
                if insourcing_desc:
                    opportunities.append(ProcurementOpportunity(
                        part_number=part["Part Number"],
                        current_supplier=part["suppliername"],
                        current_price_and_trend=trend_info["trend_str"],
                        type="Insourcing",
                        description=insourcing_desc
                    ))

            # Opportunity 3: Find external suppliers (Outsourcing)
            if part["Part Number"] not in processed_for_outsourcing:
                if outsourcing_desc := self.find_outsourcing_opportunities(part):
                    opportunities.append(ProcurementOpportunity(
                        part_number=part["Part Number"],
                        current_supplier=part["suppliername"],
                        current_price_and_trend=trend_info["trend_str"],
                        type="Outsourcing",
                        description=outsourcing_desc
                    ))
                processed_for_outsourcing.add(part["Part Number"])
        
        summary = (f"Analysis complete. Found {len(opportunities)} opportunities. "
                   f"{len([o for o in opportunities if o.type == 'Renegotiation'])} parts are priced above market index. "
                   f"{len([o for o in opportunities if o.type == 'Insourcing'])} parts have price spikes suitable for internal benchmarking. "
                   f"{len([o for o in opportunities if o.type == 'Outsourcing'])} potential external suppliers found.")

        return ProcurementAnalysis(summary=summary, opportunities=opportunities)

@app.post("/api/procurement-analysis", response_model=ProcurementAnalysis, tags=["Analysis"])
def analyze_procurement():
    """
    Performs a comprehensive procurement analysis by:
    1. Analyzing historical price trends to identify price spikes.
    2. Finding internal benchmarking opportunities for high-price parts.
    3. Searching the web for new, external suppliers.
    """
    if sheet is None:
        raise HTTPException(status_code=503, detail="Google Sheets service is unavailable. Check credentials.")
    try:
        records = sheet.get_all_records()
        if not records:
            raise HTTPException(status_code=404, detail="No data found in the Google Sheet.")
            
        analysis_result = ProcurementAnalyzer(records).run_analysis()
        return analysis_result
    
    except Exception as e:
        # Log the full exception for debugging
        print(f"ERROR during analysis: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during analysis: {str(e)}")

@app.get("/api/health", tags=["Monitoring"])
def health_check():
    """Health check endpoint to verify service status."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

# To run locally: uvicorn main:app --reload
# Ensure GOOGLE_SERVICE_ACCOUNT_JSON is set as an environment variable.