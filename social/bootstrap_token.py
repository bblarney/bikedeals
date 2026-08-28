"""Load the Instagram access token into the database. Run once, by hand.

    IG_ACCESS_TOKEN=... python -m social.bootstrap_token

There is no OAuth flow to run. Because the Meta app only ever touches the
account that owns it, the token comes straight from the App Dashboard:
Instagram > API setup with Instagram login > 1. Generate access tokens. That
button returns a long-lived token and the account is authorised in the same
step, so no app review, no Instagram Tester invite, and no app secret anywhere
in the automation.

The token is read from the environment rather than an argument so it does not
end up in shell history, and it is never logged: only the account it belongs to
is printed, so you can confirm you authorised the right one.
"""
import asyncio
import os
import sys
from datetime import datetime, timezone

import httpx

from social import instagram
from social.state import KEY_ACCESS_TOKEN, KEY_TOKEN_REFRESHED_AT, KEY_USER_ID, Store


async def run() -> int:
    token = os.environ.get("IG_ACCESS_TOKEN", "").strip()
    if not token:
        print(
            "Set IG_ACCESS_TOKEN to the token from the Meta App Dashboard "
            "(Instagram > API setup with Instagram login).",
            file=sys.stderr,
        )
        return 1

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            account = await instagram.me(client, token)
        except instagram.InstagramError as exc:
            print(f"That token did not work: {exc}", file=sys.stderr)
            return 1

        user_id = str(account["user_id"])
        print(f"Token authorises @{account.get('username', '?')} (user id {user_id}).")

        # Check the 60-day assumption rather than trusting it. If Meta ever
        # changes what that button hands out, this is where it shows up, not on
        # the first failed refresh 50 days from now.
        try:
            refreshed = await instagram.refresh_token(client, token)
            expires_in = refreshed.get("expires_in")
            if expires_in:
                print(f"Token is long-lived: {int(expires_in) // 86400} days remaining.")
        except instagram.InstagramError as exc:
            # A token under 24 hours old cannot be refreshed yet. That is
            # expected on the day it is generated and is not a problem.
            print(f"Note: could not confirm lifetime yet ({exc}).")

    store = Store.from_env()
    try:
        await store.set_many(
            {
                KEY_ACCESS_TOKEN: token,
                KEY_USER_ID: user_id,
                KEY_TOKEN_REFRESHED_AT: datetime.now(timezone.utc).isoformat(),
            }
        )
    finally:
        await store.close()

    print("Stored. The nightly workflow will refresh it automatically from here on.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
