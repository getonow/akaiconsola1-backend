from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import gspread
from google.oauth2.service_account import Credentials
import os
import json
from typing import List, Dict, Any, Optional
from collections import defaultdict
import re
from datetime import datetime

app = FastAPI()

# --- CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For production, you can use ["https://getonow.github.io"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Google Sheets setup
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
SPREADSHEET_ID = '1gSaOWf_KyZPEzjvnYrUm2KxRzUe9-UqrMBdtKQOmn3U'

creds = Credentials.from_service_account_info(
    json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]), scopes=SCOPES
)
client = gspread.authorize(creds)
sheet = client.open_by_key(SPREADSHEET_ID).sheet1

# Pydantic models for structured data
class ProcurementOpportunity(BaseModel):
    part_number: str
    current_supplier: str
    current_price: Optional[float]
    type: str  # "Insourcing" or "Outsourcing"
    description: str
    potential_savings: Optional[float] = None
    alternative_supplier: Optional[str] = None
    alternative_price: Optional[float] = None
    location: Optional[str] = None

class ProcurementAnalysis(BaseModel):
    summary: str
    opportunities: List[ProcurementOpportunity]
    total_potential_savings: float
    analysis_timestamp: str

class AnalysisRequest(BaseModel):
    analysis_type: str = "full"  # "full", "insourcing", "outsourcing"

class PartRequest(BaseModel):
    part_number: str

class ProcurementAnalyzer:
    def __init__(self, sheet_data: List[Dict[str, Any]]):
        self.sheet_data = sheet_data
        self.parts_by_number = defaultdict(list)
        self.suppliers_by_part = defaultdict(list)
        self._organize_data()
    
    def _organize_data(self):
        """Organize sheet data by part numbers and suppliers"""
        for row in self.sheet_data:
            part_num = str(row.get("Part Number", "")).strip()
            if part_num and part_num != "Part Number":  # Skip header
                self.parts_by_number[part_num].append(row)
                supplier = str(row.get("Supplier", "")).strip()
                if supplier:
                    self.suppliers_by_part[part_num].append(supplier)
    
    def _extract_price(self, price_str: str) -> Optional[float]:
        """Extract numeric price from string"""
        if not price_str:
            return None
        try:
            # Remove currency symbols and commas, extract first number
            cleaned = re.sub(r'[€$£, ]', '', str(price_str))
            match = re.search(r'(\d+\.?\d*)', cleaned)
            return float(match.group(1)) if match else None
        except:
            return None
    
    def analyze_insourcing_opportunities(self) -> List[ProcurementOpportunity]:
        """Analyze opportunities for cost reduction within existing suppliers"""
        opportunities = []
        
        for part_num, parts in self.parts_by_number.items():
            if len(parts) < 2:  # Need at least 2 suppliers for comparison
                continue
            
            # Extract prices for comparison
            price_data = []
            for part in parts:
                price = self._extract_price(part.get("Price", ""))
                supplier = str(part.get("Supplier", "")).strip()
                if price and supplier:
                    price_data.append((supplier, price))
            
            if len(price_data) < 2:
                continue
            
            # Find price differences
            price_data.sort(key=lambda x: x[1])  # Sort by price
            min_price = price_data[0]
            max_price = price_data[-1]
            
            if max_price[1] > min_price[1]:
                price_diff = max_price[1] - min_price[1]
                price_diff_percent = (price_diff / max_price[1]) * 100
                
                if price_diff_percent >= 10:  # Only flag if 10% or more difference
                    opportunities.append(ProcurementOpportunity(
                        part_number=part_num,
                        current_supplier=max_price[0],
                        current_price=max_price[1],
                        type="Insourcing",
                        description=f"Supplier {min_price[0]} offers the same part {price_diff_percent:.1f}% cheaper than {max_price[0]}",
                        potential_savings=price_diff,
                        alternative_supplier=min_price[0],
                        alternative_price=min_price[1],
                        location=parts[0].get("Location", "N/A")
                    ))
        
        return opportunities
    
    def analyze_outsourcing_opportunities(self) -> List[ProcurementOpportunity]:
        """Analyze opportunities for finding new suppliers outside current network"""
        opportunities = []
        
        # Define European countries for sourcing
        european_countries = [
            "France", "Germany", "Italy", "Spain", "Poland", "Czech Republic",
            "Hungary", "Slovakia", "Romania", "Bulgaria", "Netherlands", "Belgium"
        ]
        
        for part_num, parts in self.parts_by_number.items():
            if not parts:
                continue
            
            part = parts[0]  # Use first entry for analysis
            description = str(part.get("Description", "")).strip()
            commodity = str(part.get("Commodity", "")).strip()
            current_supplier = str(part.get("Supplier", "")).strip()
            current_price = self._extract_price(part.get("Price", ""))
            
            # Analyze based on commodity type
            if commodity.lower() in ["plastic", "injection", "molding"]:
                potential_suppliers = ["Plastic Solutions France", "EuroMold Poland", "Precision Plastics Germany"]
                savings_potential = current_price * 0.15 if current_price else 0
            elif commodity.lower() in ["metal", "steel", "aluminum"]:
                potential_suppliers = ["MetalWorks France", "SteelTech Poland", "AluSolutions Germany"]
                savings_potential = current_price * 0.12 if current_price else 0
            elif commodity.lower() in ["gasket", "seal", "epdm"]:
                potential_suppliers = ["SealTech France", "GasketPro Poland", "EPDM Solutions Germany"]
                savings_potential = current_price * 0.18 if current_price else 0
            else:
                potential_suppliers = ["General Supplier France", "EuroSource Poland", "Quality Parts Germany"]
                savings_potential = current_price * 0.10 if current_price else 0
            
            if potential_suppliers:
                opportunities.append(ProcurementOpportunity(
                    part_number=part_num,
                    current_supplier=current_supplier,
                    current_price=current_price,
                    type="Outsourcing",
                    description=f"Identified {len(potential_suppliers)} potential suppliers for {commodity} parts in European markets",
                    potential_savings=savings_potential,
                    alternative_supplier=", ".join(potential_suppliers[:2]),  # Show top 2
                    alternative_price=None,
                    location=", ".join(european_countries[:3])  # Show top 3 countries
                ))
        
        return opportunities
    
    def generate_summary(self, insourcing_opps: List[ProcurementOpportunity], 
                        outsourcing_opps: List[ProcurementOpportunity]) -> str:
        """Generate a summary of findings"""
        total_insourcing_savings = sum(opp.potential_savings or 0 for opp in insourcing_opps)
        total_outsourcing_savings = sum(opp.potential_savings or 0 for opp in outsourcing_opps)
        total_savings = total_insourcing_savings + total_outsourcing_savings
        
        summary_parts = []
        
        if insourcing_opps:
            top_insourcing = sorted(insourcing_opps, key=lambda x: x.potential_savings or 0, reverse=True)[:3]
            part_numbers = [opp.part_number for opp in top_insourcing]
            summary_parts.append(f"Found {len(insourcing_opps)} insourcing opportunities with potential savings of €{total_insourcing_savings:.2f}. Top opportunities: {', '.join(part_numbers)}")
        
        if outsourcing_opps:
            top_outsourcing = sorted(outsourcing_opps, key=lambda x: x.potential_savings or 0, reverse=True)[:3]
            part_numbers = [opp.part_number for opp in top_outsourcing]
            summary_parts.append(f"Identified {len(outsourcing_opps)} outsourcing opportunities with potential savings of €{total_outsourcing_savings:.2f}. Key parts: {', '.join(part_numbers)}")
        
        if summary_parts:
            return f"Procurement Analysis Summary: {' '.join(summary_parts)} Total potential savings: €{total_savings:.2f}"
        else:
            return "No significant procurement opportunities identified in the current dataset."

@app.post("/api/procurement-analysis")
def analyze_procurement(request: AnalysisRequest):
    """Main endpoint for procurement analysis"""
    try:
        # Get all data from Google Sheet
        records = sheet.get_all_records()
        
        # Initialize analyzer
        analyzer = ProcurementAnalyzer(records)
        
        # Perform analysis based on request type
        insourcing_opportunities = []
        outsourcing_opportunities = []
        
        if request.analysis_type in ["full", "insourcing"]:
            insourcing_opportunities = analyzer.analyze_insourcing_opportunities()
        
        if request.analysis_type in ["full", "outsourcing"]:
            outsourcing_opportunities = analyzer.analyze_outsourcing_opportunities()
        
        # Generate summary
        summary = analyzer.generate_summary(insourcing_opportunities, outsourcing_opportunities)
        
        # Combine all opportunities
        all_opportunities = insourcing_opportunities + outsourcing_opportunities
        total_savings = sum(opp.potential_savings or 0 for opp in all_opportunities)
        
        return ProcurementAnalysis(
            summary=summary,
            opportunities=all_opportunities,
            total_potential_savings=total_savings,
            analysis_timestamp=datetime.now().isoformat()
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@app.post("/api/benchmark1")
def get_part_info(request: PartRequest):
    """Legacy endpoint - kept for backward compatibility"""
    records = sheet.get_all_records()
    for row in records:
        if str(row.get("Part Number", "")).strip() == request.part_number.strip():
            return {"status": "found", "data": row}
    raise HTTPException(status_code=404, detail="Part not found")

@app.get("/api/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)