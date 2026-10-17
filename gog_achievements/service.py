import json
import logging
import sys
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .models import Achievement, AuthResponse, Game

LOGGER = logging.getLogger("gog_achievements")


class GOGError(RuntimeError):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def _load_default_client_credentials() -> tuple[str, str]:
    credentials_path = Path(__file__).with_name("gog_client_credentials.json")
    try:
        credentials = json.loads(credentials_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GOGError(
            f"Could not load GOG client credentials from {credentials_path}: {exc}"
        ) from exc

    if not isinstance(credentials, dict):
        raise GOGError(f"Invalid GOG client credentials file: {credentials_path}")

    client_id = credentials.get("client_id")
    client_secret = credentials.get("client_secret")
    if not isinstance(client_id, str) or not client_id.strip():
        raise GOGError(
            f"Missing client_id in GOG client credentials file: {credentials_path}"
        )
    if not isinstance(client_secret, str) or not client_secret.strip():
        raise GOGError(
            f"Missing client_secret in GOG client credentials file: {credentials_path}"
        )
    return client_id.strip(), client_secret.strip()


class GOGClient:
    def __init__(self, cache_dir: Path | None = None, timeout: float = 30):
        self.cache_dir = cache_dir or Path(sys.argv[0]).resolve().parent
        self.timeout = timeout

    def _read_cache(self, filename: str) -> dict[str, Any]:
        path = self.cache_dir / filename
        try:
            with path.open(encoding="utf-8") as cache_file:
                value = json.load(cache_file)
        except FileNotFoundError:
            return {}
        except (OSError, json.JSONDecodeError) as exc:
            LOGGER.warning("Could not read cache %s: %s", path, exc)
            return {}
        return value if isinstance(value, dict) else {}

    def _write_cache(self, filename: str, value: dict[str, Any]) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path = self.cache_dir / filename
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(value, indent=4), encoding="utf-8")
        temporary.replace(path)

    def _request(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        data: bytes | None = None,
        accepted: tuple[int, ...] = (200,),
    ) -> bytes:
        request = urllib.request.Request(url, data=data, headers=headers or {})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read()
                status = response.status
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise GOGError(
                f"Request failed ({exc.code}): {detail or exc.reason}", exc.code
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise GOGError(
                f"Could not connect to {urllib.parse.urlparse(url).hostname}: {exc}"
            ) from exc

        if status not in accepted:
            raise GOGError(f"Request failed with status {status}.", status)
        return body

    def _request_json(
        self, url: str, headers: dict[str, str] | None = None
    ) -> dict[str, Any]:
        try:
            value = json.loads(self._request(url, headers=headers))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise GOGError(f"Invalid JSON response from {url}") from exc
        if not isinstance(value, dict):
            raise GOGError(f"Unexpected JSON response from {url}")
        return value

    def authenticate(
        self, refresh_token: str, client_id: str = "", client_secret: str = ""
    ) -> AuthResponse:
        if not client_id or not client_secret:
            default_client_id, default_client_secret = (
                _load_default_client_credentials()
            )
            client_id = client_id or default_client_id
            client_secret = client_secret or default_client_secret
        cache = self._read_cache("auths.json")
        cached_value = cache.get(client_id)
        if isinstance(cached_value, dict):
            cached = AuthResponse.from_json(cached_value)
            try:
                expires = datetime.fromisoformat(
                    cached.expire_time.replace("Z", "+00:00")
                )
                if cached.access_token and datetime.now(timezone.utc) < expires:
                    LOGGER.info(
                        "Using cached access token (expires at %s)", cached.expire_time
                    )
                    return cached
            except (ValueError, TypeError):
                pass

        params = urllib.parse.urlencode(
            {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
                "without_new_session": "1",
            }
        )
        response = self._request_json(f"https://auth.gog.com/token?{params}")
        auth = AuthResponse.from_json(response)
        if not auth.access_token:
            raise GOGError(
                "GOG authentication response did not contain an access token."
            )
        now = datetime.now(timezone.utc)
        auth.login_time = now.isoformat(timespec="seconds")
        auth.expire_time = (now + timedelta(seconds=auth.expires_in)).isoformat(
            timespec="seconds"
        )
        cache[client_id] = auth.to_json()
        self._write_cache("auths.json", cache)
        return auth

    @staticmethod
    def _latest_build(product: dict[str, Any]) -> dict[str, Any]:
        builds = [
            build
            for build in product.get("builds", [])
            if isinstance(build, dict)
            and build.get("date_published")
            and build.get("listed")
        ]
        if not builds:
            raise GOGError("No valid published builds found for this game.")
        return max(builds, key=lambda build: str(build["date_published"]))

    def get_product_credentials(self, product_id: int) -> tuple[str, str]:
        cache = self._read_cache("products.json")
        cached = cache.get(str(product_id))
        if isinstance(cached, dict) and cached.get("clientId"):
            return str(cached["clientId"]), str(cached.get("clientSecret", ""))

        product = self._request_json(
            f"https://www.gogdb.org/data/products/{product_id}/product.json"
        )
        build = self._latest_build(product)
        details = self._request_json(
            f"https://www.gogdb.org/data/products/{product_id}/builds/{build['id']}.json"
        )
        client_id = str(details.get("clientId", ""))
        client_secret = str(details.get("clientSecret", ""))
        if not client_id:
            raise GOGError("GOGDB build details did not include a client ID.")
        cache[str(product_id)] = {"clientId": client_id, "clientSecret": client_secret}
        self._write_cache("products.json", cache)
        return client_id, client_secret

    def get_achievements(
        self, product_id: int, auth: AuthResponse
    ) -> list[Achievement]:
        client_id, _ = self.get_product_credentials(product_id)
        url = f"https://gameplay.gog.com/clients/{client_id}/users/{auth.user_id}/achievements"
        response = self._request_json(
            url,
            {
                "Accept": "application/json",
                "X-Gog-Lc": "en",
                "Authorization": f"Bearer {auth.access_token}",
            },
        )
        items = response.get("items", [])
        if not isinstance(items, list):
            raise GOGError("GOG returned an invalid achievements list.")
        return [Achievement.from_json(item) for item in items if isinstance(item, dict)]

    def set_achievement(
        self,
        product_id: int,
        auth: AuthResponse,
        refresh_token: str,
        achievement_id: str,
        unlocked: bool,
    ) -> None:
        client_id, client_secret = self.get_product_credentials(product_id)
        action_auth = self.authenticate(refresh_token, client_id, client_secret)
        unlocked_at = None
        if unlocked:
            unlocked_at = (datetime.now(timezone.utc) - timedelta(seconds=3)).strftime(
                "%Y-%m-%dT%H:%M:%S%z"
            )
        body = json.dumps({"date_unlocked": unlocked_at}).encode("utf-8")
        url = (
            f"https://gameplay.gog.com/clients/{client_id}/users/{auth.user_id}"
            f"/achievements/{urllib.parse.quote(achievement_id, safe='')}"
        )
        self._request(
            url,
            {
                "Authorization": f"Bearer {action_auth.access_token}",
                "Content-Type": "application/json",
            },
            data=body,
            accepted=(200, 201, 204),
        )

    def list_owned_games(self, auth: AuthResponse) -> list[Game]:
        response = self._request_json(
            "https://embed.gog.com/user/data/games",
            {"Authorization": f"Bearer {auth.access_token}"},
        )
        owned = response.get("owned", [])
        if not isinstance(owned, list):
            raise GOGError("GOG returned an invalid owned-games list.")

        def load_game(value: Any) -> Game | None:
            try:
                product_id = int(value)
                details = self._request_json(
                    f"https://www.gogdb.org/data/products/{product_id}/product.json"
                )
            except (ValueError, TypeError):
                return None
            except GOGError as exc:
                if exc.status == 404:
                    return None
                raise
            if details.get("builds"):
                return Game(
                    product_id=product_id,
                    title=str(details.get("title") or product_id),
                )
            return None

        with ThreadPoolExecutor(max_workers=8) as executor:
            return [game for game in executor.map(load_game, owned) if game is not None]


def configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="[LOG] %(message)s",
    )
