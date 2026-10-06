# Google Flights Prices & Fare Tracker API

[![Run on Apify](https://apify.com/actor-badge?actor=kamerozkan/google-flights-prices)](https://apify.com/kamerozkan/google-flights-prices)
[![Pricing](https://img.shields.io/badge/Pricing-Pay--Per--Event%20($0.003)-blue)](https://apify.com/kamerozkan/google-flights-prices)
[![Memory](https://img.shields.io/badge/Memory-512%20MB-green)](https://apify.com/kamerozkan/google-flights-prices)
[![Speed](https://img.shields.io/badge/Speed-3.6s%20per%20search-success)](https://apify.com/kamerozkan/google-flights-prices)

Scrape real-time airfares, airline comparisons, flight schedules, carbon emissions, and historical price benchmark levels directly from **Google Flights** without browser overhead, slow render times, or consent screen blocks.

Supports **one-way** and **round-trip** flights, multiple cabin classes, worldwide IATA airports, custom currencies, and multi-date calendar fare tracking.

---

## Why Google Flights Scraper?

| Feature | This Actor (kamerozkan) | SerpApi / Traditional APIs | Playwright / Puppeteer Scrapers |
| :--- | :--- | :--- | :--- |
| **Pricing Model** | **$0.003 / route search (PPE)** | $0.015 - $0.025 / search | $50 - $150 / mo + high compute |
| **Speed** | **3.6 seconds (Direct RPC/Protobuf)**| 8 - 15 seconds | 40 - 60 seconds (Heavy Chrome) |
| **Memory Footprint** | **512 MB** | N/A (External cloud) | 2048 MB - 4096 MB |
| **Consent Wall Bypass**| **100% Automated (SOCS bypass)** | Often blocked in EU/US | Requires manual cookie clicking |
| **Price Benchmark** | **Yes (`low`, `typical`, `high`)** | Extra charge or missing | Rarely extracted |
| **Multi-Date Calendar**| **Yes (up to 60 departure dates)** | Charged per individual date | Extremely slow in browser |

---

## Core Use Cases

- **Flight Price Tracking & Fare Drop Alerts:** Monitor key corporate and vacation flight routes daily. Trigger notifications or buy signals when airfares drop to "LOW" price levels.
- **Travel Metasearch & OTA Augmentation:** Build travel portals and flight comparison tools with up-to-date schedule and pricing data across major airlines (Delta, United, American, British Airways, Lufthansa, Turkish Airlines, Ryanair, Emirates).
- **Dynamic Pricing for Travel Agencies:** Monitor airline pricing strategies and fare spikes on upcoming peak dates or holiday weekends.
- **Corporate Travel Audits:** Benchmark flight bookings against market rates and verify that business trips are booked within fair price corridors.
- **AI Travel Agents:** Feed structured flight schedules, layover times, and prices directly into LLM travel assistants, n8n, Make, or Zapier workflows.

---

## Key Features

- **Direct Protobuf Protocol Engine:** Communicates directly with Google Flights backend services without headless browsers. 10x faster and 90% cheaper in compute.
- **One-Way & Round-Trip Searches:** Full support for point-to-point one-way flights or round-trips with customizable return durations.
- **Multi-Date Fare Calendar:** Automatically scan airfares across 7 to 30 consecutive departure dates (`numberOfDates`) to pinpoint the cheapest days to fly.
- **Comprehensive Flight Intelligence:**
  - Real-time airfare prices (`price`, `priceFormatted`, `currency`)
  - Operating airlines and codes
  - Exact departure and arrival times and dates
  - Total travel duration and flight duration (in minutes and formatted hours)
  - Number of stops and detailed segment legs (airports, durations, aircraft models like Airbus A330, Boeing 777)
  - Google Flights price insight indicator (`low`, `typical`, `high`) with typical price corridors
  - Carbon emissions in grams and route average benchmark
  - Direct link to the live Google Flights itinerary
- **Worldwide IATA Support & Custom Currencies:** Query any airport pair with USD, EUR, GBP, TRY, CAD, AUD, etc.
- **Pay-Per-Result Pricing:** Pay only $0.003 per searched flight route. Zero monthly commitments.

---

## Input Parameters

| Parameter | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `fromAirport` | String | **Yes** | `"JFK"` | 3-letter IATA code of origin airport (e.g. `JFK`, `IST`, `LHR`, `LAX`). |
| `toAirport` | String | **Yes** | `"LHR"` | 3-letter IATA code of destination airport (e.g. `LHR`, `CDG`, `HND`, `IST`). |
| `departureDate` | String | No | `"today+14"` | Departure date (`YYYY-MM-DD` or relative like `today+14`, `today+30`, `tomorrow`). |
| `isRoundTrip` | Boolean | No | `false` | Enable round-trip flight search. |
| `returnDurationDays` | Integer | No | `7` | Days between departure and return for round-trip searches (1 to 60). |
| `numberOfDates` | Integer | No | `1` | Scan consecutive departure dates (multi-date fare calendar). |
| `adults` | Integer | No | `1` | Number of adult passengers (1 to 9). |
| `seatClass` | String | No | `"economy"` | Cabin class: `"economy"`, `"premium-economy"`, `"business"`, `"first"`. |
| `currency` | String | No | `"USD"` | 3-letter currency code (e.g. `USD`, `EUR`, `GBP`, `TRY`). |
| `expandItineraries` | Boolean | No | `true` | When true, emits each flight itinerary as an individual record. When false, emits route summaries. |
| `proxyConfiguration` | Object | No | `{ "useApifyProxy": true }` | Apify Datacenter or Residential proxy settings. |

---

## Example JSON Output

Each record represents one flight offer on the selected route and date:

```json
{
  "from": "JFK",
  "to": "LHR",
  "tripType": "ONE_WAY",
  "departureDate": "2026-11-20",
  "returnDate": null,
  "adults": 1,
  "seatClass": "economy",
  "currency": "USD",
  "priceLevel": "TYPICAL",
  "priceRange": {
    "low": 170,
    "typical": 224,
    "high": 300
  },
  "totalFlights": 18,
  "lowestPrice": 399,
  "rank": 1,
  "isBest": true,
  "airline": "Virgin Atlantic",
  "airlines": ["Virgin Atlantic"],
  "price": 399,
  "priceFormatted": "USD 399",
  "departure": "08:00",
  "departureDate": "2026-11-20",
  "arrival": "20:10",
  "arrivalDate": "2026-11-20",
  "stops": 0,
  "duration": "7h 10m",
  "totalDurationMinutes": 430,
  "flightDurationMinutes": 430,
  "carbonEmissionGrams": 365000,
  "typicalCarbonEmissionGrams": 432000,
  "legs": [
    {
      "from": "JFK",
      "fromAirportName": "John F. Kennedy International Airport",
      "to": "LHR",
      "toAirportName": "Heathrow Airport",
      "departureDate": "2026-11-20",
      "departureTime": "08:00",
      "arrivalDate": "2026-11-20",
      "arrivalTime": "20:10",
      "durationMinutes": 430,
      "durationFormatted": "7h 10m",
      "planeType": "Airbus A330-900neo"
    }
  ],
  "searchUrl": "https://www.google.com/travel/flights?tfs=...",
  "scrapedAt": "2026-10-06T20:29:15+00:00"
}
```

---

## Code Examples

### Python (apify-client)

```python
from apify_client import ApifyClient

client = ApifyClient("YOUR_APIFY_API_TOKEN")

run_input = {
    "fromAirport": "JFK",
    "toAirport": "LHR",
    "departureDate": "+14 days",
    "isRoundTrip": True,
    "returnDurationDays": 7,
    "currency": "USD",
}

# Run the Actor and wait for completion
run = client.actor("kamerozkan/google-flights-prices").call(run_input=run_input)

# Fetch results from dataset
for flight in client.dataset(run["defaultDatasetId"]).iterate_items():
    print(f"[{flight['airline']}] {flight['departure']} -> {flight['arrival']} ({flight['duration']}): {flight['priceFormatted']}")
```

### JavaScript / Node.js (apify-client)

```javascript
import { ApifyClient } from 'apify-client';

const client = new ApifyClient({
    token: 'YOUR_APIFY_API_TOKEN',
});

const runInput = {
    fromAirport: 'IST',
    toAirport: 'LHR',
    departureDate: '+21 days',
    currency: 'EUR',
    numberOfDates: 7, // Scan a full week of departure dates
};

const run = await client.actor('kamerozkan/google-flights-prices').call(runInput);
const { items } = await client.dataset(run.defaultDatasetId).listItems();

console.log(`Collected ${items.length} flight schedules:`, items);
```

### cURL

```bash
curl --request POST \
  --url "https://api.apify.com/v2/acts/kamerozkan~google-flights-prices/runs?token=YOUR_APIFY_API_TOKEN" \
  --header "Content-Type: application/json" \
  --data '{
    "fromAirport": "LAX",
    "toAirport": "HND",
    "departureDate": "2026-12-10",
    "currency": "USD"
  }'
```

---

## Pricing Details

This Actor operates under **Pay-Per-Event (PPE)**:
- **Per Route Search ($0.003):** Charged per flight route date search executed.
- 1,000 route searches cost only $3.00, returning dozens of complete airline itineraries per search.
- Platform compute usage is fully included in the event fee.

---

## Related Apify Intelligence & Scraping Tools

- [Google Hotels Prices & OTA Rate Tracker API](https://apify.com/kamerozkan/google-hotels-prices) - Real-time hotel rates, room types, and OTA rate disparity scraper.
- [Google Ads Transparency Center Scraper & Spy API](https://apify.com/kamerozkan/google-ads-transparency-scraper) - Track competitor ad copy, creatives, formats, and active dates.
- [AI Brand Visibility & GEO Rank Tracker API](https://apify.com/kamerozkan/ai-brand-visibility-tracker) - Track brand mentions, Share of Voice (SOV), and citations across ChatGPT, Perplexity, Gemini, and Claude.
