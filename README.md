# Google Flights Prices & Fare Tracker API

Scrape real-time airfares, airline comparisons, flight schedules, and price trends directly from **Google Flights** without browser overhead, slow render times, or consent screen blocks.

Supports **one-way** and **round-trip** flights, multiple cabin classes, custom currencies, and multi-date calendar price tracking.

---

## Features

- **Direct Protobuf & Protocol Engine:** Connects straight to Google Flights backend services without heavy Puppeteer or Playwright browsers. Up to 10x faster execution and 90% cheaper in compute costs.
- **One-Way & Round-Trip Flights:** Search point-to-point flights or round-trips with configurable stay durations.
- **Multi-Date Fare Calendar:** Automatically scan airfares across 7 to 30 consecutive departure dates (`numberOfDates`) to pinpoint the cheapest travel days.
- **Comprehensive Flight Intelligence:**
  - Real-time airfare prices (`price`, `priceValue`, `currency`)
  - Airline name & operating carrier
  - Departure and arrival times (with overnight `+1` day flags)
  - Flight duration and number of stops (direct vs layover)
  - Google Flights price insight indicator (`low`, `typical`, `high`)
  - Google's "Best Flights" recommendation flag (`isBest`)
  - Direct link to the live Google Flights booking itinerary
- **Worldwide Coverage & Custom Currencies:** Query any global IATA airport pair with custom currencies (USD, EUR, GBP, TRY, etc.).
- **Pay-Per-Result Pricing:** Pay only $0.003 per searched flight route. No expensive hourly compute bills.

---

## Use Cases

- **Flight Fare Tracking & Price Drop Alerts:** Monitor key business travel or holiday routes daily to notify users when airfares drop to "low" levels.
- **OTA & Travel Metasearch Engines:** Build or augment travel comparison platforms with up-to-date schedule and pricing data.
- **Dynamic Pricing for Travel Agencies:** Track competitor airline price shifts across high-demand travel dates.
- **Travel Expense Management & Audits:** Verify market rates for corporate travel routes at booking time.

---

## Input Parameters

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `fromAirport` | String | **Yes** | `"JFK"` | 3-letter IATA code of origin airport (e.g. `JFK`, `IST`, `LHR`). |
| `toAirport` | String | **Yes** | `"LHR"` | 3-letter IATA code of destination airport (e.g. `LHR`, `CDG`, `HND`). |
| `departureDate` | String | No | `"today+14"` | Departure date in `YYYY-MM-DD` format or relative string (`today+14`, `today+30`, `tomorrow`). |
| `isRoundTrip` | Boolean | No | `false` | Enable round-trip flight search. |
| `returnDurationDays` | Integer | No | `7` | Days between departure and return for round trips. |
| `numberOfDates` | Integer | No | `1` | Scan consecutive departure dates (multi-date fare calendar). |
| `adults` | Integer | No | `1` | Number of adult passengers (1 to 9). |
| `seatClass` | String | No | `"economy"` | Cabin class: `"economy"`, `"premium-economy"`, `"business"`, `"first"`. |
| `currency` | String | No | `"USD"` | 3-letter currency code (e.g. `USD`, `EUR`, `GBP`, `TRY`). |
| `expandItineraries` | Boolean | No | `true` | When true, emits every flight itinerary as an individual record. When false, emits route summaries. |
| `proxyConfiguration` | Object | No | `{ "useApifyProxy": true }` | Apify datacenter or residential proxy settings. |

### Example Input

```json
{
  "fromAirport": "JFK",
  "toAirport": "LHR",
  "departureDate": "today+14",
  "isRoundTrip": false,
  "adults": 1,
  "seatClass": "economy",
  "currency": "USD",
  "numberOfDates": 1
}
```

---

## Output Data Structure

The Actor pushes structured flight records to the default Apify Dataset:

```json
{
  "from": "JFK",
  "to": "LHR",
  "tripType": "ONE_WAY",
  "departureDate": "2026-10-20",
  "returnDate": null,
  "adults": 1,
  "seatClass": "economy",
  "currency": "USD",
  "priceLevel": "typical",
  "totalFlights": 149,
  "lowestPrice": "$325",
  "lowestPriceValue": 325.0,
  "rank": 1,
  "isBest": true,
  "airline": "Virgin Atlantic",
  "price": "$325",
  "priceValue": 325.0,
  "departure": "7:01 PM on Fri, Oct 20",
  "arrival": "7:15 AM on Sat, Oct 21",
  "arrivalTimeAhead": "+1",
  "duration": "7 hr 14 min",
  "stops": 0,
  "searchUrl": "https://www.google.com/travel/flights?tfs=...",
  "scrapedAt": "2026-10-06T20:20:00Z"
}
```

---

## Pricing

This Actor uses the **Pay-per-event** pricing model:

- **$0.003** per searched flight route.
- **Compute:** Extremely lightweight (runs comfortably on 512 MB memory), costing virtually zero compute overhead.

---

## Disclaimer

This Actor extracts publicly available information from Google Flights. It is an independent tool and is not affiliated with, authorized, or endorsed by Google LLC or Alphabet Inc.
