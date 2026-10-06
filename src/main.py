from __future__ import annotations

import asyncio
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any

from apify import Actor
from .flights_client import GoogleFlightsClient, parse_date


class ChargeLimitReached(Exception):
    pass


class Runner:
    def __init__(self, inp: dict[str, Any], client: GoogleFlightsClient) -> None:
        self.inp = inp
        self.client = client
        self.pushed = 0
        self.failed: list[dict[str, Any]] = []
        self.stop = False
        self.sem = asyncio.Semaphore(int(inp.get("maxConcurrency") or 5))
        self.expand = inp.get("expandItineraries", True)

    async def charge_search(self) -> None:
        if self.stop:
            return
        try:
            await Actor.charge(event_name="flight-search")
        except Exception as err:
            err_msg = str(err).lower()
            if "budget" in err_msg or "limit" in err_msg or "charge" in err_msg:
                Actor.log.warning(f"Spending budget reached: {err}. Halting scraper.")
                self.stop = True
                raise ChargeLimitReached() from err
            Actor.log.debug(f"Non-fatal charge notice: {err}")

    async def push_item(self, item: dict[str, Any]) -> None:
        if self.stop:
            return
        item["scrapedAt"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        await Actor.push_data(item)
        self.pushed += 1

    async def run_route(
        self,
        from_code: str,
        to_code: str,
        dep_date: str,
        ret_date: str | None,
        adults: int,
        seat: str,
        currency: str,
        max_stops: int | None,
    ) -> None:
        if self.stop:
            return

        label = f"{from_code}->{to_code} ({dep_date})"
        if ret_date:
            label += f" <-> {ret_date}"

        async with self.sem:
            try:
                res = await self.client.search(
                    from_airport=from_code,
                    to_airport=to_code,
                    departure_date=dep_date,
                    return_date=ret_date,
                    adults=adults,
                    seat=seat,
                    currency=currency,
                    max_stops=max_stops,
                    session_id=f"{from_code}_{to_code}_{dep_date}",
                )
            except Exception as err:
                Actor.log.warning(f"Search failed for {label}: {err}")
                self.failed.append({"route": label, "error": str(err)[:300]})
                return

        # Charge per completed route search
        await self.charge_search()

        itineraries = res.pop("itineraries", [])
        total_found = res["totalFlights"]
        Actor.log.info(f"{label}: {total_found} flights found, lowest price: {res.get('lowestPrice')} {currency}")

        if self.expand and itineraries:
            for flight in itineraries:
                if self.stop:
                    break
                row = {
                    **res,
                    **flight,
                }
                await self.push_item(row)
        else:
            res["topItineraries"] = itineraries[:5]
            res["itineraries"] = itineraries
            await self.push_item(res)


async def main() -> None:
    async with Actor:
        inp: dict[str, Any] = await Actor.get_input() or {}
        today = datetime.now(timezone.utc).date()

        # Build list of route search requests
        route_tasks: list[tuple[str, str, str, str | None]] = []

        # 1. Structured 'routes' array input
        raw_routes = inp.get("routes") or []
        for r in raw_routes:
            if isinstance(r, dict):
                f_code = str(r.get("from") or "").strip().upper()
                t_code = str(r.get("to") or "").strip().upper()
                d_date = str(parse_date(r.get("departureDate"), today))
                r_date = str(parse_date(r.get("returnDate"), today)) if r.get("returnDate") else None
                if f_code and t_code:
                    route_tasks.append((f_code, t_code, d_date, r_date))

        # 2. Simple top-level inputs (with multi-date calendar support)
        f_top = str(inp.get("fromAirport") or "").strip().upper()
        t_top = str(inp.get("toAirport") or "").strip().upper()
        if f_top and t_top:
            first_dep = parse_date(inp.get("departureDate"), today)
            trip_duration = max(1, min(int(inp.get("returnDurationDays") or 7), 60))
            is_round = bool(inp.get("isRoundTrip", False)) or bool(inp.get("returnDate"))

            n_dates = max(1, min(int(inp.get("numberOfDates") or 1), 60))
            step = max(1, min(int(inp.get("dateStep") or 1), 30))

            for i in range(n_dates):
                dep = first_dep + timedelta(days=i * step)
                ret = (dep + timedelta(days=trip_duration)) if is_round else None
                route_tasks.append((f_top, t_top, str(dep), str(ret) if ret else None))

        if not route_tasks:
            # Prefill JFK -> LHR default for demo
            first_dep = today + timedelta(days=14)
            route_tasks.append(("JFK", "LHR", str(first_dep), None))

        adults = max(1, min(int(inp.get("adults") or 1), 9))
        seat = (inp.get("seatClass") or "economy").lower()
        currency = (inp.get("currency") or "USD").upper()
        max_stops = int(inp["maxStops"]) if (inp.get("maxStops") is not None and str(inp["maxStops"]).isdigit()) else None

        proxy_cfg = await Actor.create_proxy_configuration(actor_proxy_input=inp.get("proxyConfiguration"))

        async def proxy_factory(session: str) -> str | None:
            safe_session = re.sub(r"[^a-zA-Z0-9_]", "_", session)
            return await proxy_cfg.new_url(session_id=safe_session) if proxy_cfg else None

        client = GoogleFlightsClient(proxy_factory if proxy_cfg else None, log=Actor.log)
        runner = Runner(inp, client)

        Actor.log.info(
            f"Starting Google Flights Scraper: {len(route_tasks)} route search(es), "
            f"{adults} adult(s), seat={seat}, currency={currency}, expandItineraries={runner.expand}"
        )
        await Actor.set_status_message(f"Searching flights for {len(route_tasks)} route dates...")

        tasks = [
            runner.run_route(f_c, t_c, d_d, r_d, adults, seat, currency, max_stops)
            for f_c, t_c, d_d, r_d in route_tasks
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for res in results:
            if isinstance(res, Exception) and not isinstance(res, ChargeLimitReached):
                Actor.log.exception(res)

        summary = {
            "itemsPushed": runner.pushed,
            "failedSearches": len(runner.failed),
            "failures": runner.failed[:100],
            "clientStats": client.stats,
        }
        await Actor.set_value("RUN_SUMMARY", summary)

        msg = f"Completed: {runner.pushed} flight records pushed"
        if runner.failed:
            msg += f", {len(runner.failed)} search errors"
        Actor.log.info(msg)
        await Actor.set_status_message(msg)


if __name__ == "__main__":
    asyncio.run(main())
