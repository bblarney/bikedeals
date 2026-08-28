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


async def resolve_token(client: httpx.AsyncClient, pasted: str) -> tuple[str, str]:
    """Decide which token to store, and describe what happened.

    Refreshing here is not merely a health check on what the dashboard handed
    out. The timestamp stored alongside the token is what the nightly job counts
    its fifty days from, and that clock really starts when Meta *issued* the
    token, not when it was pasted in here. Paste one a fortnight after
    generating it and the job believes it is a fortnight younger than it is,
    so the automatic refresh lands at day 64 of a 60-day life: expired, and past
    the point where refreshing can recover it.

    Refreshing on load collapses that gap. The token that comes back is good for
    a full 60 days from this moment, so the timestamp written next to it is
    exact no matter how long the token sat in a clipboard first.

    The old behaviour also threw the refreshed token away and stored the pasted
    one, which was a free 60 days discarded for no reason.
    """
    try:
        refreshed = await instagram.refresh_token(client, pasted)
    except instagram.InstagramError as exc:
        # A token under 24 hours old cannot be refreshed yet. That is the normal
        # case for one generated minutes ago, and for that token "issued now" is
        # true anyway, so storing it as-is is correct.
        return pasted, (
            f"Could not refresh yet ({exc}). "
            "Stored as issued now, which is right for a token generated today. "
            "If this one is more than a day old, re-run this tomorrow so the "
            "refresh clock starts from a point we actually know."
        )

    token = refreshed.get("access_token") or pasted
    days = int(refreshed.get("expires_in", 0)) // 86400
    return token, f"Refreshed on load: valid for {days} days from now."


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

        token, note = await resolve_token(client, token)
        print(note)

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
