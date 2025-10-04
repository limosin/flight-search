# Flight Search Frontend

React-based frontend for testing the Flight Search API.

## Setup

1. Install dependencies:
```bash
cd frontend
npm install
```

2. Make sure the backend API is running on port 8000

3. Start the development server:
```bash
npm start
```

The app will open at http://localhost:3000

## Features

- Search for flights with configurable parameters
- Support for direct flights and up to 2 stops
- Filter by departure time window
- Sort results by price, duration, or departure time
- Clean, responsive UI
- Real-time API integration

## Usage

1. Enter origin and destination airport codes (e.g., DEL, BLR)
2. Select travel date
3. Configure search parameters (passengers, cabin class, max stops, etc.)
4. Click "Search Flights"
5. View results with detailed flight information

## API Integration

The frontend connects to the backend API at `/v1/search` using a proxy configuration in `package.json`.
