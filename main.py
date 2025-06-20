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
from bs4 import BeautifulSoup

app = FastAPI(
    title="AI-Powered Procurement Analysis API",
    description="Analyzes procurement data from Google Sheets to identify cost-saving opportunities through price trend analysis, cross-material benchmarking, and web-based supplier discovery.",
    version="2.0.0",
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
    current_price_and_trend: str = Field(..., description="e.g., '€3.40 (+12% since Apr)'")
    type: str = Field(..., description="'Insourcing' or 'Outsourcing'")
    description: str = Field(..., description="Detailed explanation and next action.")

class ProcurementAnalysis(BaseModel):
    summary: str
    opportunities: List[ProcurementOpportunity]
    analysis_timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

class ProcurementAnalyzer:
    def __init__(self, sheet_data: List[Dict[str, Any]]):
        self.data = self._clean_data(sheet_data)
        self.parts_by_commodity = self._group_by_commodity()

    def _clean_data(self, sheet_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Clean and normalize sheet data."""
        clean_data = []
        for row in sheet_data:
            # Ensure essential keys exist
            if not row.get("Part Number") or not row.get("Supplier"):
                continue
            clean_data.append(row)
        return clean_data

    def _group_by_commodity(self) -> Dict[str, list]:
        """Group parts by their commodity for cross-part analysis."""
        grouped = defaultdict(list)
        for part in self.data:
            commodity = str(part.get("Commodity", "")).strip().lower()
            if commodity:
                grouped[commodity].append(part)
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

    def _find_price_columns(self) -> List[str]:
        """Dynamically find historical price columns (e.g., 'pricemonthYYYY')."""
        if not self.data:
            return []
        # Regex to find columns like "pricejan2024", "price_may_2025", etc.
        price_col_pattern = re.compile(r'price_?[a-zA-Z]{3,}_?\d{4}', re.IGNORECASE)
        return sorted([col for col in self.data[0].keys() if price_col_pattern.match(col)])

    def analyze_price_trends(self, part: Dict[str, Any], price_cols: List[str]) -> Optional[Dict[str, Any]]:
        """Analyzes historical prices for a single part to find trends."""
        if len(price_cols) < 2:
            return None

        prices = [(col, self._parse_price(part.get(col))) for col in price_cols]
        valid_prices = [(col, p) for col, p in prices if p is not None]

        if len(valid_prices) < 2:
            return None

        latest_col, latest_price = valid_prices[-1]
        previous_col, previous_price = valid_prices[-2]

        if latest_price > previous_price:
            increase_percent = ((latest_price - previous_price) / previous_price) * 100
            if increase_percent > 10.0:
                month_name = latest_col.split('_')[1].capitalize() if '_' in latest_col else latest_col.replace('price', '').capitalize()
                return {
                    "trend_str": f"€{latest_price:.2f} (+{increase_percent:.0f}% since {month_name})",
                    "latest_price": latest_price,
                    "is_spike": True
                }
        
        # Default trend string if no spike
        return {
            "trend_str": f"€{latest_price:.2f} (Stable)",
            "latest_price": latest_price,
            "is_spike": False
        }

    def find_insourcing_opportunities(self, flagged_part: Dict[str, Any], latest_price: float) -> Optional[str]:
        """For a flagged part, find cheaper, similar parts from other suppliers."""
        part_commodity = str(flagged_part.get("Commodity", "")).strip().lower()
        if not part_commodity:
            return None

        comparison_candidates = self.parts_by_commodity.get(part_commodity, [])
        best_alternative = None
        min_alternative_price = float('inf')

        for candidate in comparison_candidates:
            # Don't compare a part to itself or parts from the same supplier
            if candidate["Part Number"] == flagged_part["Part Number"] or candidate["Supplier"] == flagged_part["Supplier"]:
                continue
            
            candidate_price = self._parse_price(candidate.get("Current Price"))
            if candidate_price and candidate_price < min_alternative_price:
                min_alternative_price = candidate_price
                best_alternative = candidate

        if best_alternative and min_alternative_price < latest_price:
            price_diff_percent = ((latest_price - min_alternative_price) / latest_price) * 100
            return (
                f"Supplier '{best_alternative['Supplier']}' provides a similar material ('{part_commodity}') "
                f"via part '{best_alternative['Part Number']}' for €{min_alternative_price:.2f}, which is "
                f"{price_diff_percent:.0f}% cheaper. Consider requesting a quote from them for '{flagged_part['Part Number']}'."
            )
        return None

    def find_outsourcing_opportunities(self, part: Dict[str, Any]) -> Optional[str]:
        """Perform a web search to find new potential suppliers."""
        part_name = part.get("Description", part.get("Part Number", "")).strip()
        commodity = part.get("Commodity", "").strip()
        query = f'"{part_name}" "{commodity}" suppliers in Europe delivery to France'
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        try:
            response = requests.get(f"https://www.google.com/search?q={query}", headers=headers, timeout=5)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find search result containers
            results = soup.find_all('div', class_='g')
            if not results:
                return None
            
            # Extract info from the first valid result
            for res in results:
                title_tag = res.find('h3')
                link_tag = res.find('a')
                snippet_tag = res.find('div', class_='VwiC3b')
                
                if title_tag and link_tag and snippet_tag:
                    title = title_tag.get_text()
                    link = link_tag['href']
                    # Clean up the URL
                    if link.startswith('/url?q='):
                        link = link.split('/url?q=')[1].split('&sa=U')[0]

                    return (f"Found potential supplier: '{title}'. Website: {link}. "
                            f"Recommendation: Benchmark for potential outsourcing.")
            return None
        except requests.RequestException as e:
            print(f"Web scraping failed for query '{query}': {e}")
            return None

    def run_analysis(self) -> ProcurementAnalysis:
        opportunities = []
        price_cols = self._find_price_columns()
        
        flagged_parts_for_outsourcing = set()

        # Main analysis loop
        for part in self.data:
            trend_info = self.analyze_price_trends(part, price_cols)
            if not trend_info:
                # Use current price if no trend data
                price = self._parse_price(part.get("Current Price"))
                trend_info = {
                    "trend_str": f"€{price:.2f}" if price else "Price N/A",
                    "latest_price": price,
                    "is_spike": False
                }

            # If price spike, search for insourcing and outsourcing opportunities
            if trend_info["is_spike"]:
                flagged_parts_for_outsourcing.add(part["Part Number"])
                insourcing_desc = self.find_insourcing_opportunities(part, trend_info["latest_price"])
                if insourcing_desc:
                    opportunities.append(ProcurementOpportunity(
                        part_number=part["Part Number"],
                        current_supplier=part["Supplier"],
                        current_price_and_trend=trend_info["trend_str"],
                        type="Insourcing",
                        description=insourcing_desc
                    ))

        # Run outsourcing analysis on all unique parts, prioritizing flagged ones
        processed_for_outsourcing = set()
        sorted_parts = sorted(self.data, key=lambda p: p["Part Number"] in flagged_parts_for_outsourcing, reverse=True)

        for part in sorted_parts:
            if part["Part Number"] in processed_for_outsourcing:
                continue
            
            outsourcing_desc = self.find_outsourcing_opportunities(part)
            if outsourcing_desc:
                # Use current price for trend if no historical data
                price = self._parse_price(part.get("Current Price"))
                trend_str = trend_info.get("trend_str", f"€{price:.2f}" if price else "Price N/A")

                opportunities.append(ProcurementOpportunity(
                    part_number=part["Part Number"],
                    current_supplier=part["Supplier"],
                    current_price_and_trend=trend_str,
                    type="Outsourcing",
                    description=outsourcing_desc
                ))
            processed_for_outsourcing.add(part["Part Number"])

        # Generate Summary
        summary = f"Analysis complete. Found {len(opportunities)} total opportunities. "
        summary += f"Identified {len([o for o in opportunities if o.type == 'Insourcing'])} parts with price spikes suitable for internal benchmarking. "
        summary += f"Found {len([o for o in opportunities if o.type == 'Outsourcing'])} potential external suppliers."

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
            
        analyzer = ProcurementAnalyzer(records)
        analysis_result = analyzer.run_analysis()
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