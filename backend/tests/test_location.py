import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import LatLng
from app.routers import location


def feature(rings, kind="Polygon", postal_code="21218"):
    return {"properties": {"ZIPCODE1": postal_code}, "geometry": {"type": kind, "coordinates": rings}}


OUTER = [[-76.64, 39.31], [-76.60, 39.31], [-76.60, 39.34], [-76.64, 39.34], [-76.64, 39.31]]
HOLE = [[-76.63, 39.32], [-76.62, 39.32], [-76.62, 39.33], [-76.63, 39.33], [-76.63, 39.32]]


@pytest.mark.parametrize("kind,rings", [("Polygon", [OUTER]), ("MultiPolygon", [[OUTER]])])
def test_returns_postal_city_for_gps(monkeypatch, kind, rings):
    monkeypatch.setattr(location, "zip_boundaries", lambda: [feature(rings, kind)])
    result = TestClient(app).post("/location/label", json={"lat": 39.329, "lng": -76.615})
    assert result.status_code == 200
    assert result.json() == {"label": "21218, Baltimore", "postal_code": "21218", "city": "Baltimore"}


def test_holes_and_outside_points_are_not_assigned_a_postal_code():
    features = [feature([OUTER, HOLE])]
    assert location.postal_label(LatLng(lat=39.325, lng=-76.625), features).label is None
    assert location.postal_label(LatLng(lat=40.7, lng=-74), features).label is None
    assert location.postal_label(LatLng(lat=39.31, lng=-76.61), features).postal_code == "21218"


def test_boundary_download_failure_can_be_retried(monkeypatch):
    def unavailable():
        raise httpx.ConnectError("Offline")
    monkeypatch.setattr(location, "zip_boundaries", unavailable)
    assert TestClient(app).post("/location/label", json={"lat": 39.329, "lng": -76.615}).status_code == 503


def test_gps_is_not_sent_to_boundary_provider(monkeypatch):
    calls = []
    def get(url, **kwargs):
        calls.append((url, kwargs))
        return httpx.Response(200, json={"features": [feature([OUTER])]}, request=httpx.Request("GET", url))
    location.zip_boundaries.cache_clear()
    monkeypatch.setattr(location.httpx, "get", get)
    try:
        client = TestClient(app)
        for lat in (39.329, 39.33):
            assert client.post("/location/label", json={"lat": lat, "lng": -76.615}).status_code == 200
        assert len(calls) == 1
        assert set(calls[0][1]["params"]) == {"where", "outFields", "outSR", "f", "geometryPrecision"}
    finally:
        location.zip_boundaries.cache_clear()


def test_address_search_returns_match_with_correct_coordinate_order(monkeypatch):
    def get(url, **kwargs):
        assert url == location.CENSUS_GEOCODER_URL
        assert kwargs["params"]["address"] == "400 W Lexington St Baltimore MD"
        return httpx.Response(200, json={"result": {"addressMatches": [{
            "matchedAddress": "400 W LEXINGTON ST, BALTIMORE, MD, 21201",
            "addressComponents": {"zip": "21201", "city": "BALTIMORE"},
            "coordinates": {"x": -76.62235, "y": 39.29129},
        }]}}, request=httpx.Request("GET", url))
    monkeypatch.setattr(location.httpx, "get", get)
    result = TestClient(app).post("/location/search", json={"query": "400 W Lexington St Baltimore MD"})
    assert result.status_code == 200
    assert result.json()[0]["coordinates"] == {"lat": 39.29129, "lng": -76.62235}
    assert result.json()[0]["label"] == "21201, Baltimore"


def test_no_address_matches_and_upstream_failures_are_distinct(monkeypatch):
    monkeypatch.setattr(location.httpx, "get", lambda url, **kw: httpx.Response(200, json={"result": {"addressMatches": []}}, request=httpx.Request("GET", url)))
    client = TestClient(app)
    assert client.post("/location/search", json={"query": "Unknown street address"}).json() == []
    def offline(*args, **kwargs):
        raise httpx.ConnectError("Offline")
    monkeypatch.setattr(location.httpx, "get", offline)
    assert client.post("/location/search", json={"query": "400 W Lexington St Baltimore MD"}).status_code == 503
    assert client.post("/location/search", json={"query": "   "}).status_code == 422
