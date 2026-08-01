import os

os.environ.setdefault("SCHEDULER_ENABLED", "false")

import pytest
from fastapi.testclient import TestClient

from app.main import app

LB_EVENT = "epicgames_S41_RankedCupSolo_OCE"
LB_WINDOW = "S41_RankedCupSolo_Event5_OCE"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_list_tournaments(client: TestClient):
    response = client.get("/tournaments", params={"region": "OCE"})
    assert response.status_code == 200
    body = response.json()
    assert "tournaments" in body
    assert len(body["tournaments"]) > 0
    item = body["tournaments"][0]
    assert "eventId" in item
    assert "displayData" in item
    assert "isLive" in item


def test_list_tournaments_live_filter(client: TestClient):
    response = client.get("/tournaments", params={"live": "true"})
    assert response.status_code == 200
    for item in response.json()["tournaments"]:
        assert item["isLive"] is True


def test_tournament_detail(client: TestClient):
    listing = client.get("/tournaments", params={"region": "OCE"})
    event_id = listing.json()["tournaments"][0]["eventId"]

    response = client.get(f"/tournaments/{event_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["eventId"] == event_id
    assert "eventWindows" in body
    if body["eventWindows"]:
        window = body["eventWindows"][0]
        assert "scoreLocations" in window
        assert "isLive" in window


def test_leaderboard_cached_page(client: TestClient):
    response = client.get(f"/leaderboard/{LB_EVENT}/{LB_WINDOW}", params={"page": 0})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["leaderboardEventId"] == LB_EVENT
    assert len(body["entries"]) > 0
    assert body["entries"][0]["rank"] == 1


def test_leaderboard_uncached_page_enqueues(client: TestClient):
    response = client.get(
        f"/leaderboard/{LB_EVENT}/{LB_WINDOW}",
        params={"page": 9999},
    )
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "loading"
    assert body["page"] == 9999


def test_player_placements(client: TestClient):
    lb = client.get(f"/leaderboard/{LB_EVENT}/{LB_WINDOW}", params={"page": 0})
    account_id = lb.json()["entries"][0]["players"][0]["accountId"]

    response = client.get(f"/players/{account_id}/placements")
    assert response.status_code == 200
    body = response.json()
    assert body["accountId"] == account_id
    assert len(body["placements"]) >= 1
    assert body["placements"][0]["leaderboardEventId"] == LB_EVENT


def test_player_search_database(client: TestClient):
    lb = client.get(f"/leaderboard/{LB_EVENT}/{LB_WINDOW}", params={"page": 0})
    username = lb.json()["entries"][0]["players"][0]["username"]
    assert username

    response = client.get("/players/search", params={"name": username[:4]})
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "database"
    assert any(p["username"] == username for p in body["players"])
