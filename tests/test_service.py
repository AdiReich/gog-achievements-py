import unittest
from threading import Barrier
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from gog_achievements_py.models import AuthResponse
from gog_achievements_py.service import GOGClient, GOGError


class AuthenticationTests(unittest.TestCase):
    def test_uses_default_client_credentials_when_not_provided(self):
        client = GOGClient()
        with (
            patch(
                "gog_achievements_py.service._load_default_client_credentials",
                return_value=("client-id", "client-secret"),
            ) as load_credentials,
            patch.object(client, "_read_cache", return_value={}),
            patch.object(client, "_write_cache"),
            patch.object(
                client,
                "_request_json",
                return_value={
                    "access_token": "access",
                    "expires_in": 3600,
                    "refresh_token": "refresh",
                    "user_id": "user",
                },
            ) as request_json,
        ):
            client.authenticate("refresh")

        params = parse_qs(urlparse(request_json.call_args.args[0]).query)
        self.assertEqual(params["client_id"], ["client-id"])
        self.assertEqual(params["client_secret"], ["client-secret"])
        load_credentials.assert_called_once_with()


class LatestBuildTests(unittest.TestCase):
    def test_chooses_newest_listed_published_build(self):
        product = {
            "builds": [
                {"id": 1, "date_published": "2023-01-01", "listed": True},
                {"id": 2, "date_published": "2025-04-20", "listed": True},
                {"id": 3, "date_published": "2026-01-01", "listed": False},
                {"id": 4, "date_published": "", "listed": True},
            ]
        }

        self.assertEqual(GOGClient._latest_build(product)["id"], 2)

    def test_rejects_products_without_valid_builds(self):
        with self.assertRaisesRegex(GOGError, "No valid published builds"):
            GOGClient._latest_build({"builds": []})


class ListOwnedGamesTests(unittest.TestCase):
    def test_loads_product_details_concurrently_and_preserves_order(self):
        client = GOGClient()
        concurrent_lookups = Barrier(2, timeout=2)

        def request_json(url, headers=None):
            if url.endswith("/user/data/games"):
                return {"owned": [101, 202]}
            concurrent_lookups.wait()
            product_id = int(url.split("/")[-2])
            return {"title": f"Game {product_id}", "builds": [1]}

        with patch.object(client, "_request_json", side_effect=request_json):
            games = client.list_owned_games(AuthResponse("token", "", 0, "user"))

        self.assertEqual(
            [(game.product_id, game.title) for game in games],
            [(101, "Game 101"), (202, "Game 202")],
        )


if __name__ == "__main__":
    unittest.main()
