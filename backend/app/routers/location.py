from functools import lru_cache
from threading import Lock

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..models import LatLng

router = APIRouter()
ZIP_BOUNDARIES_URL = "https://egisdata.baltimorecity.gov/egis/rest/services/CityView/Zipcode/MapServer/0/query"
boundary_lock = Lock()
CENSUS_GEOCODER_URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"


class LocationLabel(BaseModel):
    label: str | None = None
    postal_code: str | None = None
    city: str | None = None


class AddressQuery(BaseModel):
    query: str = Field(min_length=3, max_length=100)


class AddressMatch(BaseModel):
    address: str
    label: str
    coordinates: LatLng


@router.post("/location/search", response_model=list[AddressMatch])
def search_address(body: AddressQuery) -> list[AddressMatch]:
    query = body.query.strip()
    if len(query) < 3:
        raise HTTPException(422, "Enter a street address with a city or ZIP code.")
    try:
        response = httpx.get(CENSUS_GEOCODER_URL, params={
            "address": query, "benchmark": "Public_AR_Current", "format": "json",
        }, timeout=15)
        response.raise_for_status()
        matches = response.json()["result"]["addressMatches"]
        return [AddressMatch(
            address=match["matchedAddress"],
            label=", ".join(filter(None, [match["addressComponents"].get("zip"), match["addressComponents"].get("city", "").title()])),
            coordinates=LatLng(lat=match["coordinates"]["y"], lng=match["coordinates"]["x"]),
        ) for match in matches[:5]]
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        raise HTTPException(503, "Address search is unavailable right now. Try again or use your current location.") from None


@lru_cache(maxsize=1)
def zip_boundaries() -> list[dict]:
    response = httpx.get(ZIP_BOUNDARIES_URL, params={
        "where": "1=1", "outFields": "ZIPCODE1", "outSR": "4326",
        "f": "geojson", "geometryPrecision": "6",
    }, timeout=10)
    response.raise_for_status()
    features = response.json()["features"]
    if not features:
        raise ValueError("No postal boundaries available")
    return features


def in_ring(x: float, y: float, ring: list[list[float]]) -> bool:
    inside = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
        cross = (x - x1) * (y2 - y1) - (y - y1) * (x2 - x1)
        if abs(cross) < 1e-12 and min(x1, x2) <= x <= max(x1, x2) and min(y1, y2) <= y <= max(y1, y2):
            return True
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def postal_label(point: LatLng, features: list[dict]) -> LocationLabel:
    for feature in features:
        geometry = feature["geometry"]
        if geometry["type"] not in ("Polygon", "MultiPolygon"):
            continue
        polygons = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
        for rings in polygons:
            if rings and in_ring(point.lng, point.lat, rings[0]) and not any(in_ring(point.lng, point.lat, hole) for hole in rings[1:]):
                postal_code = feature["properties"]["ZIPCODE1"]
                return LocationLabel(label=f"{postal_code}, Baltimore", postal_code=postal_code, city="Baltimore")
    return LocationLabel()


@router.post("/location/label", response_model=LocationLabel)
def locate(point: LatLng) -> LocationLabel:
    try:
        with boundary_lock:
            features = zip_boundaries()
        return postal_label(point, features)
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        raise HTTPException(status_code=503, detail="Your GPS location is available, but we couldn’t look up its postal code. Try again.") from None
