# AI-Powered Procurement Analysis API (v3.0.0)

This FastAPI backend provides a sophisticated, AI-driven procurement analysis service. It analyzes single-sourced part data from a Google Sheet to identify cost-saving opportunities through **market index comparison**, **in-house benchmarking**, and **real-time web scraping** for alternative suppliers.

This is a "rules-based expert system" that does not use an LLM, ensuring your data remains 100% private and the analysis is fast and free.

## 🚀 Core Features

-   **Market Index Benchmarking (Primary Analysis)**: Flags parts where your price for a specific month is higher than the market average (`Priceevoindex`), providing a powerful, data-driven argument for renegotiation.
-   **In-House Benchmarking**: For parts that are flagged as overpriced, it intelligently finds *other parts* made of a similar material from *different suppliers* in your sheet to provide an internal benchmark for renegotiation.
-   **Web-Based Supplier Discovery**: For flagged parts, it performs real-time Google searches to find new potential suppliers in Europe. It is designed to handle network errors or bot detection gracefully.
-   **Targeted Analysis**: The agent is currently configured to perform its analysis specifically for the **June 2025** period.

## 🛠️ Setup

1.  **Clone the repository** and navigate into the directory.
2.  **Install dependencies**: `pip install -r requirements.txt`
3.  **Create `service-account.json`**: Place your Google Cloud Service Account JSON key file in the root of the project. This file is listed in `.gitignore` and will not be committed.
4.  **Set `GOOGLE_SERVICE_ACCOUNT_JSON` Environment Variable**:
    -   **PowerShell**: `$env:GOOGLE_SERVICE_ACCOUNT_JSON = Get-Content -Raw -Path .\service-account.json`
    -   **Linux/macOS**: `export GOOGLE_SERVICE_ACCOUNT_JSON=$(cat service-account.json)`
5.  **Share Google Sheet**: Ensure your service account email (found in your `service-account.json`) has "Viewer" access to the Google Sheet.

## 📊 Google Sheet Structure

The agent is designed to work with the following exact column names and formats.

#### Supplier & Part Details
-   `suppliernumber`, `suppliername`, `suppliercontactname`, `suppliercontactemail`, `suppliermanufacturinglocation`
-   `Part Number`: **(Required)** Unique ID for the part.
-   `partname`: **(Required)** Description of the part, used for web searches.
-   `material`: **(Required)** The material type (e.g., `EPDM`), used for cross-material comparisons.
-   `currency`: The currency for pricing (e.g., `EUR`).

#### Monthly Volume Data
-   `voljanuary2023`, `volfebruary2023`, ..., `voldecember2025`
-   (Currently informational, not used in core analysis).

#### Monthly Price Data (CRITICAL)
-   Must follow the exact format: `pricemonthYYYY` (e.g., `pricemay2025`, `pricejune2025`).
-   The month name must be spelled out and lowercase.

#### Price Evolution Index (CRITICAL)
-   Must follow the exact format: `PriceevoindexmonthYYYY` (e.g., `Priceevoindexmay2025`, `Priceevoindexjune2025`).
-   The 'P' must be capitalized, and there is no space between `Priceevoindex` and the month.

## 🚀 Running the Application

Ensure the `GOOGLE_SERVICE_ACCOUNT_JSON` environment variable is set in your terminal session, then:
```bash
python -m uvicorn main:app --reload
```
Using `python -m` is recommended to ensure it uses the Python environment where your packages are installed. Access the interactive documentation at `http://localhost:8000/docs`.

## 📋 API Endpoints

### `POST /api/procurement-analysis`

Triggers a full analysis of the Google Sheet for the **June 2025** period. It requires no request body.

**Example Response:**
```json
{
  "summary": "Analysis complete. Found 2 opportunities for June 2025.",
  "opportunities": [
    {
      "part_number": "ABC123",
      "current_supplier": "Supplier A",
      "current_price_and_trend": "€3.40 (15% above market index)",
      "type": "Renegotiation",
      "description": "This part's price is 15% above the current market index. Recommend immediate renegotiation with 'Supplier A'."
    },
    {
      "part_number": "ABC123",
      "current_supplier": "Supplier A",
      "current_price_and_trend": "€3.40 (15% above market index)",
      "type": "Outsourcing",
      "description": "Found potential supplier: 'Example Corp Components'. Website: http://example.com. Recommendation: Benchmark for potential outsourcing."
    }
  ],
  "analysis_timestamp": "2024-08-01T12:00:00.000000"
}
```

## 💡 Agent Logic Explained (v3)

The analysis is performed in a specific, prioritized order for the target month of **June 2025**:

1.  **Find Problem Parts (Market Index Analysis)**: The agent first scans all parts to find "problem parts." A part is considered a problem if its price in `pricejune2025` is higher than the market index in `Priceevoindexjune2025`. For each of these, it immediately creates a high-priority **"Renegotiation"** opportunity.
2.  **Deeper Analysis on Problem Parts**: The agent then performs further analysis *only* on the list of problem parts identified in step 1.
    -   **Insourcing**: It searches for other suppliers in the sheet that provide the same `material` for a lower price, creating an **"Insourcing"** opportunity.
    -   **Outsourcing**: It performs a web search using the part's name and material to find new potential suppliers, creating an **"Outsourcing"** opportunity. This step may be skipped if Google blocks the request.

---
*This project is licensed under the MIT License.* 