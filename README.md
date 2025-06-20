# AI-Powered Procurement Analysis API (v2.0)

This FastAPI backend provides a sophisticated, AI-driven procurement analysis service. It analyzes single-sourced part data from a Google Sheet to identify cost-saving opportunities through **price trend analysis**, **cross-material benchmarking**, and **real-time web scraping** for alternative suppliers.

This is a "rules-based expert system" that does not use an LLM, ensuring your data remains 100% private and the analysis is fast and free.

## 🚀 Core Features

-   **Price Spike & Trend Analysis**: Automatically detects parts with recent, significant price increases (>10% MoM) by analyzing historical price data.
-   **In-House Benchmarking**: For parts with price spikes, it intelligently finds *other parts* with similar materials from *different suppliers* in your sheet to provide a powerful internal benchmark for renegotiation.
-   **Web-Based Supplier Discovery**: Performs real-time Google searches to find new potential suppliers in Europe for high-cost or price-spike parts, then extracts their name and website.
-   **Dynamic & Private**: Analysis is performed based on the data you provide, and your sensitive procurement data never leaves your system.
-   **Structured, Actionable Output**: Provides a clear summary and a detailed list of opportunities with specific next steps.

## 🛠️ Setup

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/getonow/akaiconsola1-backend.git
    cd akaiconsola1-backend
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Set `GOOGLE_SERVICE_ACCOUNT_JSON` Environment Variable:**
    This application now loads Google credentials securely from an environment variable.

    -   **In PowerShell (for local development):**
        Before running the server, execute this command in your terminal. Make sure `service-account.json` is in your project directory.
        ```powershell
        $env:GOOGLE_SERVICE_ACCOUNT_JSON = Get-Content -Raw -Path .\service-account.json
        ```
    -   **In Linux/macOS:**
        ```bash
        export GOOGLE_SERVICE_ACCOUNT_JSON=$(cat service-account.json)
        ```
    -   **For Production:** Set this as a secret environment variable in your deployment environment.

4.  **Share Google Sheet:** Ensure your service account email has "Viewer" access to the Google Sheet.

## 📊 Expected Google Sheet Structure

For the agent to work effectively, your sheet must contain the following columns. The agent is robust to missing data but performs best with complete information.

| Column | Required? | Example | Description |
| :--- | :--- | :--- | :--- |
| **`Part Number`** | **Yes** | `ABC123` | Unique identifier for the part. |
| **`Supplier`** | **Yes** | `Supplier A` | The single, current supplier for this part. |
| **`Description`** | **Yes** | `EPDM Gasket 2mm` | Used for web searches. |
| **`Commodity`** | **Yes** | `EPDM` | Used for cross-material comparisons. |
| **`Current Price`** | No | `3.40` | The most recent price. |
| **`price_mmmYYYY`** | No | `price_apr2025` | **Crucial for trend analysis.** Use this format for historical prices (e.g., `price_may2025`, `price_jun2025`). |

## 🚀 Running the Application

Ensure your `GOOGLE_SERVICE_ACCOUNT_JSON` environment variable is set, then start the server:

```bash
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000/docs` for interactive documentation.

## 📋 API Endpoints

### `POST /api/procurement-analysis`

Triggers a full, comprehensive analysis of the Google Sheet data. It takes no request body.

**How to Call:**
```bash
curl -X POST "http://localhost:8000/api/procurement-analysis"
```

**Example Response:**
```json
{
  "summary": "Analysis complete. Found 2 total opportunities...",
  "opportunities": [
    {
      "part_number": "ABC123",
      "current_supplier": "Supplier A",
      "current_price_and_trend": "€3.40 (+12% since May)",
      "type": "Insourcing",
      "description": "Supplier 'Supplier B' provides a similar material ('epdm') via part 'DEF456' for €2.80, which is 18% cheaper. Consider requesting a quote from them for 'ABC123'."
    },
    {
      "part_number": "ABC123",
      "current_supplier": "Supplier A",
      "current_price_and_trend": "€3.40 (+12% since May)",
      "type": "Outsourcing",
      "description": "Found potential supplier: 'Supplier XYZ Inc. - Industrial Gaskets'. Website: http://xyz-gaskets.com. Recommendation: Benchmark for potential outsourcing."
    }
  ],
  "analysis_timestamp": "2025-06-21T10:00:00.000Z"
}
```

### `GET /api/health`

A simple health check endpoint to verify the service is running.

## 💡 Agent Logic Explained

1.  **Price Trend Analysis**: The agent scans for columns matching the `price_mmmYYYY` pattern to build a price history for each part. It flags any part where the latest price is >10% higher than the previous month's price.
2.  **Insourcing (Cross-Material Benchmarking)**: For each "price spike" part, the agent looks for *other* parts in your sheet with the same `Commodity`. If it finds a cheaper part from a different supplier, it generates a recommendation to request a quote, leveraging your existing supplier relationships.
3.  **Outsourcing (Web Scraping)**: For all parts (prioritizing those with price spikes), the agent constructs a Google search query using the part's `Description` and `Commodity`. It then scrapes the first page of results to find potential new suppliers and their websites.

## 🔒 Security & Privacy

-   **Credentials**: Your Google service account JSON is loaded securely from an environment variable and should **never** be hardcoded or committed to version control.
-   **Data Privacy**: Your procurement data from the Google Sheet is processed in-memory and is **never** shared with any third-party service.
-   **Web Scraping**: The web scraper uses a standard `User-Agent` and only accesses public search engine results.

---

*This project is licensed under the MIT License.* 