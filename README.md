# AI-Powered Procurement Analysis API (v2.1)

This FastAPI backend provides a sophisticated, AI-driven procurement analysis service. It analyzes single-sourced part data from a Google Sheet to identify cost-saving opportunities through **price trend analysis**, **market index comparison**, and **real-time web scraping** for alternative suppliers.

This is a "rules-based expert system" that does not use an LLM, ensuring your data remains 100% private and the analysis is fast and free.

## 🚀 Core Features

-   **Price Spike & Trend Analysis**: Automatically detects parts with recent, significant price increases (>10% MoM) by analyzing historical price data.
-   **Market Index Benchmarking**: Flags parts where your price is significantly higher than the market average (`Priceevoindex`), providing a powerful, data-driven argument for renegotiation.
-   **In-House Benchmarking**: For parts with price spikes, it intelligently finds *other parts* with similar materials from *different suppliers* in your sheet to provide an internal benchmark for renegotiation.
-   **Web-Based Supplier Discovery**: Performs real-time Google searches to find new potential suppliers in Europe for high-cost or price-spike parts.

## 🛠️ Setup

1.  **Clone the repository** and navigate into the directory.
2.  **Install dependencies**: `pip install -r requirements.txt`
3.  **Set `GOOGLE_SERVICE_ACCOUNT_JSON` Environment Variable**:
    -   **PowerShell**: `$env:GOOGLE_SERVICE_ACCOUNT_JSON = Get-Content -Raw -Path .\service-account.json`
    -   **Linux/macOS**: `export GOOGLE_SERVICE_ACCOUNT_JSON=$(cat service-account.json)`
4.  **Share Google Sheet**: Ensure your service account email has "Viewer" access to the Google Sheet.

## 📊 Google Sheet Structure

The agent is designed to work with the following exact column names.

#### Supplier & Part Details
-   `suppliernumber`: Unique ID for the supplier.
-   `suppliername`: Name of the supplier.
-   `suppliercontactname`: Main contact person.
-   `suppliercontactemail`: Contact's email.
-   `suppliermanufacturinglocation`: City and country of manufacture.
-   `Part Number`: **(Required)** Unique ID for the part.
-   `partname`: **(Required)** Description of the part, used for web searches.
-   `material`: **(Required)** The material type (e.g., `EPDM`), used for cross-material comparisons.
-   `currency`: The currency for pricing (e.g., `EUR`).

#### Monthly Volume Data
-   `voljanuary2023`, `volfebruary2023`, ..., `voldecember2025`
-   Represents the purchase/production volume for each month. (Currently informational, not used in core analysis).

#### Monthly Price Data
-   `pricejanuary2023`, `pricefebruary2023`, ...
-   **Crucial for trend analysis.** The agent requires at least two consecutive months of price data to detect spikes.

#### Price Evolution Index
-   `Priceevoindexjan2023`, `Priceevoindexfeb2023`, ...
-   **Crucial for market comparison.** Represents the average market price for the part. The agent compares your `price` to this `Priceevoindex` for the same month.

## 🚀 Running the Application

Ensure the `GOOGLE_SERVICE_ACCOUNT_JSON` environment variable is set, then:
```bash
uvicorn main:app --reload
```
Access the interactive documentation at `http://localhost:8000/docs`.

## 📋 API Endpoints

### `POST /api/procurement-analysis`

Triggers a full analysis of the Google Sheet. It requires no request body.

**Example Response:**
```json
{
  "summary": "Analysis complete. Found 3 opportunities...",
  "opportunities": [
    {
      "part_number": "ABC123",
      "current_supplier": "Supplier A",
      "current_price_and_trend": "€3.40 (15% above market index)",
      "type": "Renegotiation",
      "description": "This part's price is significantly above the market index. Recommend renegotiating with 'Supplier A' for a price closer to the market average."
    },
    {
      "part_number": "DEF456",
      "current_supplier": "Supplier B",
      "current_price_and_trend": "€5.50 (+20% vs last month)",
      "type": "Insourcing",
      "description": "Supplier 'Supplier C' provides a similar material ('pa66 15%gf') via part 'GHI789' for €4.80, which is 13% cheaper. Consider requesting a quote from them for 'DEF456'."
    }
  ]
}
```

## 💡 Agent Logic Explained

1.  **Price Analysis (Highest Priority)**: For the most recent month, the agent first checks if the part's price (`price...`) is more than 10% above the market index (`Priceevoindex...`). If so, it creates a high-priority **"Renegotiation"** opportunity.
2.  **Price Spike Analysis**: If the part is not above the market index, the agent then checks if the price has spiked more than 10% compared to the previous month.
3.  **Insourcing**: If a price spike is detected, the agent searches for other parts with the same `material` from different suppliers in your sheet to find cheaper internal alternatives, creating an **"Insourcing"** opportunity.
4.  **Outsourcing**: For every part, the agent performs a web search using its `part name` and `material` to find new potential suppliers, creating an **"Outsourcing"** opportunity.

---
*This project is licensed under the MIT License.* 