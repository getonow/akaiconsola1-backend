# Akaiconsola1 Backend - AI-Powered Procurement Analysis

A FastAPI backend service that provides intelligent procurement analysis and cost optimization recommendations by analyzing Google Sheets data for supplier benchmarking and sourcing opportunities.

## 🚀 Features

- **AI-Powered Procurement Analysis**: Intelligent analysis of supplier data for cost reduction opportunities
- **Insourcing Analysis**: Compare prices between existing suppliers for the same parts
- **Outsourcing Analysis**: Identify new supplier opportunities in European markets
- **Cost Savings Calculation**: Automatic calculation of potential savings
- **Structured Data Models**: Type-safe API responses with Pydantic models
- **Google Sheets Integration**: Direct connection to your procurement master file
- **CORS Support**: Ready for frontend integration

## 📊 Analysis Capabilities

### 1. Insourcing Opportunities
- Compares prices between suppliers for the same part numbers
- Identifies significant price gaps (10%+ differences)
- Suggests switching to better-priced existing suppliers
- Calculates potential cost savings

### 2. Outsourcing Opportunities
- Analyzes parts by commodity type (plastic, metal, gaskets, etc.)
- Identifies potential new suppliers in European markets
- Focuses on France and nearby European countries
- Provides supplier recommendations based on commodity expertise

## 🛠️ Setup

1. **Clone the repository:**
```bash
git clone https://github.com/getonow/akaiconsola1-backend.git
cd akaiconsola1-backend
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Set up Google Sheets credentials:**
   - Create a service account in Google Cloud Console
   - Download the service account JSON file
   - Set the environment variable:
   ```bash
   export GOOGLE_SERVICE_ACCOUNT_JSON='{"your":"json","content":"here"}'
   ```
   - Share your Google Sheet with the service account email

4. **Update the spreadsheet ID** in `main.py` with your actual Google Sheet ID

## 🚀 Running the Application

Start the development server:
```bash
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`

## 📋 API Endpoints

### POST /api/procurement-analysis

Main endpoint for comprehensive procurement analysis.

**Request Body:**
```json
{
  "analysis_type": "full"  // "full", "insourcing", or "outsourcing"
}
```

**Response:**
```json
{
  "summary": "Procurement Analysis Summary: Found 5 insourcing opportunities...",
  "opportunities": [
    {
      "part_number": "ABC123",
      "current_supplier": "Supplier A",
      "current_price": 100.0,
      "type": "Insourcing",
      "description": "Supplier B offers the same part 22% cheaper than Supplier A",
      "potential_savings": 22.0,
      "alternative_supplier": "Supplier B",
      "alternative_price": 78.0,
      "location": "France"
    }
  ],
  "total_potential_savings": 150.0,
  "analysis_timestamp": "2024-01-15T10:30:00"
}
```

### POST /api/benchmark1 (Legacy)

Legacy endpoint for simple part lookup (maintained for backward compatibility).

**Request Body:**
```json
{
  "part_number": "YOUR_PART_NUMBER"
}
```

### GET /api/health

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00"
}
```

## 📊 Expected Google Sheet Structure

Your Google Sheet should contain columns like:
- **Part Number**: Unique identifier for each part
- **Supplier**: Current supplier name
- **Price**: Current price (can include currency symbols)
- **Description**: Part description
- **Commodity**: Type of material/component
- **Location**: Supplier location

## 🔍 Analysis Logic

### Insourcing Analysis
1. Groups parts by part number
2. Compares prices across different suppliers
3. Identifies price differences ≥10%
4. Recommends switching to lower-priced suppliers

### Outsourcing Analysis
1. Analyzes parts by commodity type
2. Identifies potential new suppliers based on:
   - Commodity expertise (plastic, metal, gaskets, etc.)
   - Geographic location (European markets)
   - Supplier reputation and capabilities
3. Calculates potential savings based on commodity type

## 💡 Usage Examples

### Full Analysis
```bash
curl -X POST "http://localhost:8000/api/procurement-analysis" \
     -H "Content-Type: application/json" \
     -d '{"analysis_type": "full"}'
```

### Insourcing Only
```bash
curl -X POST "http://localhost:8000/api/procurement-analysis" \
     -H "Content-Type: application/json" \
     -d '{"analysis_type": "insourcing"}'
```

### Outsourcing Only
```bash
curl -X POST "http://localhost:8000/api/procurement-analysis" \
     -H "Content-Type: application/json" \
     -d '{"analysis_type": "outsourcing"}'
```

## 🔒 Security Notes

- The `service-account.json` file contains sensitive credentials and should never be committed to version control
- Use environment variables for credential management in production
- Implement proper authentication for production deployments

## 🚀 Future Enhancements

- Integration with real supplier databases
- Machine learning for price prediction
- Automated supplier qualification
- Real-time market price feeds
- Advanced analytics dashboard

## 📝 License

This project is licensed under the MIT License. 