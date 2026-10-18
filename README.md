# GOG achievements for Python

A Python CLI for viewing, unlocking, and clearing GOG achievements, rewritten from the original GOG Achievements Manager.

## Requirements

- Python 3.10 or later
- Windows with GOG Galaxy installed and signed in (the refresh token is read from the Windows registry)

## CLI

```powershell
py -m gog_achievements
py -m gog_achievements <game-id>
py -m gog_achievements <game-id> <achievement-id> [achievement-id ...]
py -m gog_achievements <game-id> -c <achievement-id> [achievement-id ...]
py -m gog_achievements -v <game-id>
```

For example, `py -m gog_achievements 1558393671` lists a game's unlocked and locked achievements. Add achievement IDs to unlock them, or pass `-c` to clear (lock) them.

## Authentication and cache

The application reads the GOG Galaxy refresh token from `HKCU\Software\GOG.com\Galaxy`, then calls GOG's authentication and gameplay APIs and GOGDB.org. Authentication and product credentials are cached as `auths.json` and `products.json` beside the launched application. An active internet connection is required.

## Credits / Acknowledgments

This project is a complete Python rewrite of the original [GOG Achievements Manager](https://github.com/timendum/gog_achievements) created by [@timendum](https://github.com/timendum). 
The entire codebase has been translated and reconstructed in Python with the assistance of AI (GitHub Copilot) to optimize code structure and implementation.