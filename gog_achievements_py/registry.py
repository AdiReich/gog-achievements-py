import sys


def get_refresh_token() -> str:
    if sys.platform != "win32":
        raise RuntimeError(
            "GOG Galaxy refresh tokens are currently read from the Windows registry."
        )

    import winreg

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, r"Software\GOG.com\Galaxy"
        ) as key:
            token, _ = winreg.QueryValueEx(key, "refreshToken")
    except OSError as exc:
        raise RuntimeError(
            f"Could not read the GOG Galaxy refresh token: {exc}"
        ) from exc

    if not isinstance(token, str) or not token:
        raise RuntimeError("No refresh token found in the GOG Galaxy registry key.")
    return token
