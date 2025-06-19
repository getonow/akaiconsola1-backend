# Akaiconsola1 Backend

A FastAPI backend service that provides an API to query part information from Google Sheets.

## Features

- FastAPI-based REST API
- Google Sheets integration for data retrieval
- Part number lookup functionality

## Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/akaiconsola1-backend.git
cd akaiconsola1-backend
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up Google Sheets credentials:
   - Create a service account in Google Cloud Console
   - Download the service account JSON file
   - Rename it to `service-account.json` and place it in the project root
   - Share your Google Sheet with the service account email

4. Update the `SPREADSHEET_ID` in `main.py` with your actual Google Sheet ID

## Running the Application

Start the development server:
```bash
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`

## API Endpoints

### POST /api/benchmark1

Query part information by part number.

**Request Body:**
```json
{
  "part_number": "YOUR_PART_NUMBER"
}
```

**Response:**
```json
{
  "status": "found",
  "data": {
    "Part Number": "YOUR_PART_NUMBER",
    "Description": "Part description",
    // ... other columns from your sheet
  }
}
```

## Environment Variables

- `SPREADSHEET_ID`: Your Google Sheet ID (currently hardcoded in main.py)

## Security Note

The `service-account.json` file contains sensitive credentials and is excluded from version control. Make sure to keep this file secure and never commit it to the repository. 