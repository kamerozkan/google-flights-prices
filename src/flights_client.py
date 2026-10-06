from __future__ import annotations

import asyncio
import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Awaitable

from fast_flights import FlightData, Passengers, create_filter, core
from primp import Client

CONSENT_COOKIE = {"SOCS": "CAESEwgDEgk2NDU4MzQ2OTQaAmVuIAEaBgiA_L20Bg"}


def parse_price_number(raw_price: str | None) -> float | None:
    if not raw_price:
        return None
    # Strip currency symbols and commas, e.g. "$1,234" -> 1234.0, "€500" -> 500.0, "500 TL" -> 500.0
    cleaned = re.sub(r"[^\d\.]", "", raw_price.replace(",", ""))
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


def parse_date(value: Any, today: date) -> date:
    """Accepts YYYY-MM-DD, 'today', 'tomorrow', '+14', '+14 days', '2 weeks', '1 month'."""
    if value in (None, ""):
        return today + timedelta(days=14)
    if isinstance(value, date):
        return value
    val = str(value).strip().lower()
    if val in ("today", "now"):
        return today
    if val == "tomorrow":
        return today + timedelta(days=1)

    m = re.match(r"^(?:today\s*)?\+\s*(\d+)\s*(d|day|days|w|week|weeks|m|month|months)?$", val)
    if m:
        num = int(m.group(1))
        unit = (m.group(2) or "d")[0]
        if unit == "d":
            return today + timedelta(days=num)
        if unit == "w":
            return today + timedelta(weeks=num)
        if unit == "m":
            return today + timedelta(days=num * 30)

    try:
        return datetime.strptime(val[:10], "%Y-%m-%d").date()
    except ValueError:
        return today + timedelta(days=14)


class GoogleFlightsClient:
    def __init__(
        self,
        proxy_factory: Callable[[str], Awaitable[str | None]] | None = None,
        log: logging.Logger | None = None,
    ) -> None:
        self.proxy_factory = proxy_factory
        self.log = log or logging.getLogger(__name__)
        self.stats = {"searches": 0, "retries": 0, "errors": 0}

    async def search(
        self,
        from_airport: str,
        to_airport: str,
        departure_date: str,
        return_date: str | None = None,
        adults: int = 1,
        seat: str = "economy",
        currency: str = "USD",
        language: str = "en",
        country: str = "us",
        max_stops: int | None = None,
        session_id: str = "flights",
    ) -> dict[str, Any]:
        """Perform a Google Flights search and parse all itineraries and prices."""
        is_round_trip = bool(return_date)
        trip_type = "round-trip" if is_round_trip else "one-way"

        flight_data = [
            FlightData(
                date=departure_date,
                from_airport=from_airport.upper().strip(),
                to_airport=to_airport.upper().strip(),
            )
        ]
        if is_round_trip and return_date:
            flight_data.append(
                FlightData(
                    date=return_date,
                    from_airport=to_airport.upper().strip(),
                    to_airport=from_airport.upper().strip(),
                )
            )

        tfs_filter = create_filter(
            flight_data=flight_data,
            trip=trip_type,
            seat=seat,  # 'economy', 'premium-economy', 'business', 'first'
            passengers=Passengers(adults=max(1, min(adults, 9))),
            max_stops=max_stops,
        )

        b64_tfs = tfs_filter.as_b64().decode("utf-8")
        params = {
            "tfs": b64_tfs,
            "hl": language,
            "gl": country.lower(),
            "curr": currency.upper(),
            "tfu": "EgQIABABIgA",
            "ucbcb": "1",
        }

        search_url = f"https://www.google.com/travel/flights?tfs={b64_tfs}&hl={language}&gl={country.lower()}&curr={currency.upper()}"

        def _do_fetch(proxy_url: str | None) -> Any:
            client = Client(impersonate="chrome_126", verify=False, proxy=proxy_url)
            res = client.get(
                "https://www.google.com/travel/flights",
                params=params,
                cookies=CONSENT_COOKIE,
            )
            assert res.status_code == 200, f"HTTP {res.status_code}"
            return core.parse_response(res)

        loop = asyncio.get_running_loop()
        parsed = None

        for attempt in range(4):
            self.stats["searches"] += 1
            proxy_url = await self.proxy_factory(f"{session_id}_{attempt}") if self.proxy_factory else None
            try:
                parsed = await loop.run_in_executor(None, _do_fetch, proxy_url)
                break
            except Exception as err:
                self.stats["retries"] += 1
                self.log.warning(f"Google Flights fetch attempt {attempt + 1} failed: {err}")
                await asyncio.sleep(1.2 * (attempt + 1))

        if not parsed:
            self.stats["errors"] += 1
            raise RuntimeError(f"Flight search failed after 4 retries for {from_airport}->{to_airport} ({departure_date})")

        raw_flights = getattr(parsed, "flights", [])
        price_level = getattr(parsed, "current_price", None)

        itineraries = []
        for rank, f in enumerate(raw_flights, start=1):
            price_val = parse_price_number(f.price)
            itineraries.append({
                "rank": rank,
                "isBest": bool(getattr(f, "is_best", False)),
                "airline": f.name,
                "price": f.price,
                "priceValue": price_val,
                "currency": currency.upper(),
                "departure": f.departure,
                "arrival": f.arrival,
                "arrivalTimeAhead": getattr(f, "arrival_time_ahead", ""),
                "duration": f.duration,
                "stops": getattr(f, "stops", 0),
            })

        return {
            "from": from_airport.upper().strip(),
            "to": to_airport.upper().strip(),
            "tripType": "ROUND_TRIP" if is_round_trip else "ONE_WAY",
            "departureDate": departure_date,
            "returnDate": return_date,
            "adults": adults,
            "seatClass": seat,
            "currency": currency.upper(),
            "priceLevel": price_level,
            "totalFlights": len(itineraries),
            "lowestPrice": itineraries[0]["price"] if itineraries else None,
            "lowestPriceValue": itineraries[0]["priceValue"] if itineraries else None,
            "itineraries": itineraries,
            "searchUrl": search_url,
        }
