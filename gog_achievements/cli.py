import argparse
import sys

from .registry import get_refresh_token
from .service import GOGClient, GOGError, configure_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gog-achievements",
        description=(
            "List owned GOG games, view their achievements, or unlock/clear achievements."
        ),
    )
    parser.add_argument("game_id", nargs="?", help="Game ID (omit to list owned games)")
    parser.add_argument(
        "achievement_ids",
        nargs="*",
        metavar="achievement-id",
        help="Achievement IDs to unlock (or clear with -c)",
    )
    parser.add_argument(
        "-c", "--clear", action="store_true", help="Clear (lock) achievements"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.clear and not args.achievement_ids:
        parser.error("-c requires at least one achievement ID")
    if args.achievement_ids and not args.game_id:
        parser.error("achievement IDs require a game ID")
    try:
        product_id = int(args.game_id) if args.game_id is not None else None
    except ValueError:
        parser.error("game-id must be an integer")

    configure_logging(args.verbose)
    client = GOGClient()
    try:
        refresh_token = get_refresh_token()
        auth = client.authenticate(refresh_token)
        if product_id is None:
            for game in client.list_owned_games(auth):
                print(f"- {game.product_id}: {game.title}")
            return 0

        if args.achievement_ids:
            unlocked = not args.clear
            verb = "unlock" if unlocked else "clear"
            for achievement_id in args.achievement_ids:
                client.set_achievement(
                    product_id, auth, refresh_token, achievement_id, unlocked
                )
                print(f"Achievement {verb}ed successfully: {achievement_id}")
            return 0

        achievements = client.get_achievements(product_id, auth)
        print("Unlocked Achievements:")
        for achievement in achievements:
            if achievement.date_unlocked is not None:
                print(
                    f"- {achievement.achievement_id}: {achievement.name} = {achievement.description}"
                )
        print("\nTo be unlocked Achievements:")
        for achievement in achievements:
            if achievement.date_unlocked is None:
                print(
                    f"- {achievement.achievement_id}: {achievement.name} = {achievement.description}"
                )
        return 0
    except (GOGError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
