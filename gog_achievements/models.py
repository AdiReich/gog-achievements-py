from dataclasses import dataclass
from typing import Any


@dataclass
class AuthResponse:
    access_token: str
    refresh_token: str
    expires_in: int
    user_id: str
    login_time: str = ""
    expire_time: str = ""

    @classmethod
    def from_json(cls, value: dict[str, Any]) -> "AuthResponse":
        return cls(
            access_token=value.get("access_token", ""),
            refresh_token=value.get("refresh_token", ""),
            expires_in=int(value.get("expires_in", 0)),
            user_id=str(value.get("user_id", "")),
            login_time=value.get("login_time", ""),
            expire_time=value.get("expire_time", ""),
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_in": self.expires_in,
            "user_id": self.user_id,
            "login_time": self.login_time,
            "expire_time": self.expire_time,
        }


@dataclass
class Achievement:
    achievement_id: str
    achievement_key: str
    visible: bool
    name: str
    description: str
    image_url_unlocked: str
    image_url_locked: str
    rarity: float
    date_unlocked: str | None
    rarity_level_description: str
    rarity_level_slug: str

    @classmethod
    def from_json(cls, value: dict[str, Any]) -> "Achievement":
        unlocked = value.get("date_unlocked")
        return cls(
            achievement_id=str(value.get("achievement_id", "")),
            achievement_key=value.get("achievement_key", ""),
            visible=bool(value.get("visible", True)),
            name=value.get("name", ""),
            description=value.get("description", ""),
            image_url_unlocked=value.get("image_url_unlocked", ""),
            image_url_locked=value.get("image_url_locked", ""),
            rarity=float(value.get("rarity", 0)),
            date_unlocked=unlocked,
            rarity_level_description=value.get("rarity_level_description", ""),
            rarity_level_slug=value.get("rarity_level_slug", ""),
        )


@dataclass
class Game:
    product_id: int
    title: str
