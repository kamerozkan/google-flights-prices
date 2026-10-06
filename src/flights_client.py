from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Awaitable

from fast_flights import FlightQuery, Passengers, create_query
from fast_flights.parser import parse_js
from fast_flights.exceptions import FlightsNotFound
from primp import Client
from selectolax.lexbor import LexborHTMLParser

# Standard Google Consent bypass cookie
CONSENT_COOKIE = {"SOCS": "CAESEwgDEgk2NDU4MzQ2OTQaAmVuIAEaBgiA_L20Bg"}


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


def format_duration(minutes: int) -> str:
    hours = minutes // 60
    mins = minutes % 60
    if hours > 0 and mins > 0:
        return f"{hours}h {mins}m"
    if hours > 0:
        return f"{hours}h"
    return f"{mins}m"


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
        """Perform a Google Flights search and parse all itineraries, fares, and price insights."""
        is_round_trip = bool(return_date)
        trip_type = "round-trip" if is_round_trip else "one-way"

        from_clean = from_airport.upper().strip()
        to_clean = to_airport.upper().strip()

        flight_queries = [
            FlightQuery(
                date=departure_date,
                from_airport=from_clean,
                to_airport=to_clean,
                max_stops=max_stops,
            )
        ]
        if is_round_trip and return_date:
            flight_queries.append(
                FlightQuery(
                    date=return_date,
                    from_airport=to_clean,
                    to_airport=from_clean,
                    max_stops=max_stops,
                )
            )

        passengers = Passengers(adults=max(1, min(adults, 9)))
        query_obj = create_query(
            flights=flight_queries,
            seat=seat,  # 'economy', 'premium-economy', 'business', 'first'
            trip=trip_type,
            passengers=passengers,
            currency=currency.upper(),
            language=language.lower(),
            max_stops=max_stops,
        )

        params = query_obj.params()
        # Ensure consent bypass query flag is present
        params["ucbcb"] = "1"
        b64_tfs = params.get("tfs", "")
        search_url = f"https://www.google.com/travel/flights?tfs={b64_tfs}&hl={language}&curr={currency.upper()}"

        def _create_client(proxy_url: str | None) -> Client:
            for imp in ["chrome_146", "chrome_145", "chrome_131", "chrome_126", "chrome"]:
                try:
                    return Client(
                        impersonate=imp,
                        verify=False,
                        proxy=proxy_url,
                        cookie_store=True,
                    )
                except Exception:
                    continue
            return Client(verify=False, proxy=proxy_url, cookie_store=True)

        def _do_fetch(proxy_url: str | None) -> str:
            client = _create_client(proxy_url)
            res = client.get(
                "https://www.google.com/travel/flights",
                params=params,
                cookies=CONSENT_COOKIE,
            )
            if res.status_code != 200:
                raise RuntimeError(f"Google Flights returned HTTP {res.status_code}")
            return res.text

        loop = asyncio.get_running_loop()
        html = ""

        for attempt in range(4):
            self.stats["searches"] += 1
            clean_sess = re.sub(r"[^a-zA-Z0-9_]", "_", f"{session_id}_{attempt}")
            proxy_url = await self.proxy_factory(clean_sess) if self.proxy_factory else None
            try:
                html = await loop.run_in_executor(None, _do_fetch, proxy_url)
                if "Before you continue to Google" in html or "consent.google.com" in html:
                    raise RuntimeError("Consent wall encountered on attempt")
                if "script.ds:1" in html or "script class=\"ds:1\"" in html or "ds:1" in html:
                    break
                # Check if recaptcha
                if "recaptcha" in html.lower() or "unusual traffic" in html.lower():
                    raise RuntimeError("Google rate-limit captcha encountered")
                # Wait briefly before retry if page lacked script
                await asyncio.sleep(1.0)
            except Exception as err:
                self.stats["retries"] += 1
                self.log.warning(f"Google Flights fetch attempt {attempt + 1} for {from_clean}->{to_clean} failed: {err}")
                await asyncio.sleep(1.5 * (attempt + 1))

        if not html:
            self.stats["errors"] += 1
            raise RuntimeError(f"Flight search failed after 4 retries for {from_clean}->{to_clean} ({departure_date})")

        # Parse data script
        parser = LexborHTMLParser(html)
        script = parser.css_first(r"script.ds\:1")
        if not script:
            self.stats["errors"] += 1
            raise RuntimeError(f"Could not locate flight data element for {from_clean}->{to_clean}")

        js_content = script.text()
        data_str = js_content.split("data:", 1)[1].rsplit(",", 1)[0]
        if data_str.endswith("errorHasStatus: true"):
            # Route legitimately has no flight results
            return {
                "from": from_clean,
                "to": to_clean,
                "tripType": "ROUND_TRIP" if is_round_trip else "ONE_WAY",
                "departureDate": departure_date,
                "returnDate": return_date,
                "adults": adults,
                "seatClass": seat,
                "currency": currency.upper(),
                "priceLevel": None,
                "priceRange": None,
                "totalFlights": 0,
                "lowestPrice": None,
                "itineraries": [],
                "searchUrl": search_url,
            }

        payload = json.loads(data_str)
        flights_list = parse_js(js_content)

        # Extract best flights count (payload[3][1])
        best_count = 0
        if len(payload) > 3 and payload[3] and len(payload[3]) > 1:
            if isinstance(payload[3][1], int):
                best_count = payload[3][1]

        # Extract price level and typical price insights from payload[5]
        price_level = None
        price_range = None
        if len(payload) > 5 and isinstance(payload[5], list) and len(payload[5]) >= 7:
            p5 = payload[5]
            try:
                low_val = p5[4][1] if isinstance(p5[4], list) and len(p5[4]) > 1 else None
                high_val = p5[5][1] if isinstance(p5[5], list) and len(p5[5]) > 1 else None
                median_val = p5[2][1] if isinstance(p5[2], list) and len(p5[2]) > 1 else None
                level_code = p5[6] if len(p5) > 6 else None
                if level_code == 0:
                    price_level = "LOW"
                elif level_code == 1:
                    price_level = "TYPICAL"
                elif level_code == 2:
                    price_level = "HIGH"

                if low_val is not None and high_val is not None:
                    price_range = {
                        "low": low_val,
                        "typical": median_val,
                        "high": high_val,
                    }
            except Exception:
                pass

        # Build clean itinerary records
        itineraries: list[dict[str, Any]] = []
        for rank, f in enumerate(flights_list, start=1):
            is_best = rank <= best_count

            # Extract leg records
            legs_data = []
            flight_minutes_sum = 0
            for leg in f.flights:
                flight_minutes_sum += leg.duration
                d_y, d_m, d_d = leg.departure.date
                d_h, d_min = leg.departure.time
                a_y, a_m, a_d = leg.arrival.date
                a_h, a_min = leg.arrival.time

                legs_data.append({
                    "from": leg.from_airport.code,
                    "fromAirportName": leg.from_airport.name,
                    "to": leg.to_airport.code,
                    "toAirportName": leg.to_airport.name,
                    "departureDate": f"{d_y:04d}-{d_m:02d}-{d_d:02d}",
                    "departureTime": f"{d_h:02d}:{d_min:02d}",
                    "arrivalDate": f"{a_y:04d}-{a_m:02d}-{a_d:02d}",
                    "arrivalTime": f"{a_h:02d}:{a_min:02d}",
                    "durationMinutes": leg.duration,
                    "durationFormatted": format_duration(leg.duration),
                    "planeType": leg.plane_type,
                })

            stops_count = max(0, len(legs_data) - 1)
            first_leg = legs_data[0] if legs_data else None
            last_leg = legs_data[-1] if legs_data else None

            # Calculate total duration including layovers
            total_duration_minutes = flight_minutes_sum
            if len(legs_data) > 1 and first_leg and last_leg:
                try:
                    dep_dt = datetime.strptime(f"{first_leg['departureDate']} {first_leg['departureTime']}", "%Y-%m-%d %H:%M")
                    arr_dt = datetime.strptime(f"{last_leg['arrivalDate']} {last_leg['arrivalTime']}", "%Y-%m-%d %H:%M")
                    elapsed = int((arr_dt - dep_dt).total_seconds() / 60)
                    if elapsed > 0:
                        total_duration_minutes = elapsed
                except Exception:
                    pass

            carbon_emission = getattr(f.carbon, "emission", None) if getattr(f, "carbon", None) else None
            typical_carbon = getattr(f.carbon, "typical_on_route", None) if getattr(f, "carbon", None) else None

            itineraries.append({
                "rank": rank,
                "isBest": is_best,
                "airline": ", ".join(f.airlines) if f.airlines else "Unknown Airline",
                "airlines": f.airlines,
                "price": f.price,
                "priceFormatted": f"{currency.upper()} {f.price}" if f.price else None,
                "currency": currency.upper(),
                "departure": first_leg["departureTime"] if first_leg else None,
                "departureDate": first_leg["departureDate"] if first_leg else departure_date,
                "arrival": last_leg["arrivalTime"] if last_leg else None,
                "arrivalDate": last_leg["arrivalDate"] if last_leg else departure_date,
                "stops": stops_count,
                "duration": format_duration(total_duration_minutes),
                "totalDurationMinutes": total_duration_minutes,
                "flightDurationMinutes": flight_minutes_sum,
                "carbonEmissionGrams": carbon_emission,
                "typicalCarbonEmissionGrams": typical_carbon,
                "legs": legs_data,
                "priceLevel": price_level,
            })

        lowest_price = itineraries[0]["price"] if itineraries else None

        return {
            "from": from_clean,
            "to": to_clean,
            "tripType": "ROUND_TRIP" if is_round_trip else "ONE_WAY",
            "departureDate": departure_date,
            "returnDate": return_date,
            "adults": adults,
            "seatClass": seat,
            "currency": currency.upper(),
            "priceLevel": price_level,
            "priceRange": price_range,
            "totalFlights": len(itineraries),
            "lowestPrice": lowest_price,
            "itineraries": itineraries,
            "searchUrl": search_url,
        }
