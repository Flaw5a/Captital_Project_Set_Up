"""Postcode -> area/lat-long lookup, with map + Google Earth/Maps links.

Primary source: postcodes.io (free, no API key). Returns the postcode centroid
(lat/long) and administrative area names. This is NOT a full PAF street address;
for building-level addresses set GETADDRESS_API_KEY (getAddress.io) and the
endpoint will additionally return a list of full addresses to pick from.

Everything degrades gracefully: if the network/proxy blocks the lookup, the app
still works with manual entry and the Google Maps/Earth links (built purely from
the postcode, client-openable) still function.
"""
from __future__ import annotations

import re
from urllib.parse import quote

import httpx

from ..config import get_settings

POSTCODE_RE = re.compile(r"^[A-Za-z]{1,2}\d[A-Za-z\d]?\s*\d[A-Za-z]{2}$")


def _maps_links(query: str, lat=None, lon=None) -> dict:
    q = f"{lat},{lon}" if lat is not None and lon is not None else query
    return {
        "google_maps_url": f"https://www.google.com/maps/search/?api=1&query={quote(q)}",
        "google_earth_url": f"https://earth.google.com/web/search/{quote(query)}",
        "osm_url": (
            f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=17/{lat}/{lon}"
            if lat is not None else f"https://www.openstreetmap.org/search?query={quote(query)}"
        ),
    }


def lookup_postcode(postcode: str) -> dict:
    postcode = (postcode or "").strip()
    result = {
        "input": postcode,
        "valid": False,
        "latitude": None,
        "longitude": None,
        "area": "",
        "district": "",
        "region": "",
        "country": "",
        "addresses": [],
        "error": "",
    }
    if not postcode:
        result["error"] = "No postcode provided."
        return result
    result.update(_maps_links(postcode))
    if not POSTCODE_RE.match(postcode):
        result["error"] = "That does not look like a UK postcode."
        return result

    # postcodes.io centroid + admin areas
    try:
        r = httpx.get(
            f"https://api.postcodes.io/postcodes/{quote(postcode)}",
            timeout=8.0, trust_env=True,
        )
        if r.status_code == 200:
            d = r.json().get("result", {}) or {}
            lat, lon = d.get("latitude"), d.get("longitude")
            district = d.get("admin_district") or ""
            region = d.get("region") or d.get("country") or ""
            ward = d.get("admin_ward") or ""
            area = ", ".join(p for p in (ward, district) if p) or district
            result.update(
                valid=True, latitude=lat, longitude=lon,
                area=area, district=district, region=region,
                country=d.get("country") or "",
            )
            result.update(_maps_links(postcode, lat, lon))
        else:
            result["error"] = f"Postcode not found (HTTP {r.status_code})."
    except Exception as e:  # network/proxy/offline -> keep manual entry + links
        result["error"] = f"Lookup unavailable ({type(e).__name__}). Enter address manually."

    # Optional full PAF addresses via getAddress.io
    key = get_settings().GETADDRESS_API_KEY
    if key:
        try:
            r = httpx.get(
                f"https://api.getAddress.io/find/{quote(postcode)}?api-key={key}&expand=true",
                timeout=8.0, trust_env=True,
            )
            if r.status_code == 200:
                for a in r.json().get("addresses", []):
                    line = ", ".join(
                        p for p in [
                            a.get("line_1", ""), a.get("line_2", ""),
                            a.get("town_or_city", ""),
                        ] if p
                    )
                    if line:
                        result["addresses"].append(f"{line}, {postcode}")
        except Exception:
            pass
    return result
