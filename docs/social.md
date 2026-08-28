# Instagram

One post per day, published unattended from GitHub Actions after the nightly
scrape. No weekly round-up and no comment handling yet: see [Deferred](#deferred).

## How a post happens

```
Daily Scrape (08:00 UTC)
      │  workflow_run, conclusion == success
      ▼
.github/workflows/social.yml  ->  python -m social.post_daily
      1. GET /api/v1/bikes?added_since=day&sort=discount_desc&in_stock=true
      2. drop anything already posted, or from a shop that opted out
      3. render a 1080x1350 JPEG (Playwright + social/templates/card.html)
      4. stage the bytes in Postgres, get a random id
      5. verify https://api.bikegrid.com.au/social/<id>.jpg is a 200 image/jpeg
      6. create container -> poll to FINISHED -> publish
      7. record the post, prune staged images, refresh the token if it is old
```

Two choices worth knowing about before changing anything here.

**The post reads the public API, not the database.** It sees exactly what a
visitor sees, so it cannot advertise a deal the site does not show. Postgres is
touched only for the ledger, the token, and image staging.

**It is chained to the scrape, not to the clock.** The scrape's duration varies,
and a fixed cron would eventually fire mid-run and post yesterday's feed. A
failed scrape skips the night entirely rather than posting against partial data.

## Setup, once

The Meta app only ever touches the account that owns it, so there is no app
review, no Instagram Tester invite, and no app secret in the automation.

**App Roles is the wrong screen.** That list adds *Facebook* accounts as app
admins and developers, which is why it asks for a Facebook developer account.
Ignore it.

1. Switch the Instagram account to **Business** or **Creator**.
2. At developers.facebook.com, create an app, add the **Instagram** product,
   choose **Instagram Login**. No Facebook Page is involved.
3. **Instagram > API setup with Instagram login > 1. Generate access tokens**.
   Add the account, click **Generate token**, confirm the Instagram login. This
   grants `instagram_business_basic` and `instagram_business_content_publish`.
4. Copy the token immediately. The dashboard will not show it again.
5. Leave the app in **Development mode** forever.

Then load it, once, from a machine on the tailnet:

```bash
IG_ACCESS_TOKEN=... DATABASE_URL=... python -m social.bootstrap_token
```

That prints which account the token authorises and how many days it has left,
then stores it. Nothing else needs configuring: the nightly job refreshes the
token on its own from here on.

Put `#ad` in the account bio alongside the site link while you are there.

## The token

Long-lived tokens last 60 days. The job refreshes at 50, leaving ten days of
slack, so it can fail every night for a week and still recover unattended. With
five days or fewer remaining a failed refresh stops being a warning and fails the
run, so the failure email arrives while manual re-authorisation is still possible.

A token left unrefreshed for 60 days is dead and can only be replaced by
repeating step 3 above.

It lives in `social_state`, not in a GitHub secret, because a refresh has to
*rewrite* it: giving the workflow that ability means keeping a PAT with
secrets-write scope in the repo, which is a worse credential to hold than the
token it would protect.

## Why images are served from the API

Instagram does not accept image bytes. It takes a public URL, cURLs it once at
publish time, and serves its own copy afterwards. So the rendered card needs a
public home for a few seconds.

The cheap answer would be an orphan git branch plus `raw.githubusercontent.com`,
but Cloudflare Pages builds every non-production branch by default, so that fires
a preview build nightly for a branch holding no site code. Serving from
`GET /social/{id}.jpg` instead keeps the URL on our own TLS domain, keeps the
fetch a plain 200 with no cross-host redirect, needs no git write permission, and
cannot be broken by a change to the frontend's build settings.

Rows are pruned after 30 days. Deleting one cannot affect a live post.

## Keeping a shop out of it

Set `instagram: false` in the shop's file under `scrapers/vendors/`. Scraping is
unaffected: the bike still appears on the site, it just never becomes a post.
This exists so a shop that objects to its product photography being reposted is
excluded by one line of config.

## What gets picked

Ranked by discount, then filtered (`social/select.py`): in stock, has a usable
image, has an RRP to strike through, at least 20% off, at least $400, a brand
`scrapers/brands.py` recognises, and not posted in the last 60 days.

If nothing qualifies the job exits 0 and posts nothing. An empty day beats a bad
post, and "60% off a $180 bike" reads like spam next to the rest of the feed.

## Working on it

```bash
pip install -r requirements-social.txt
playwright install --with-deps chromium
python -m social.post_daily --dry-run
```

`--dry-run` hits the live public API, picks a real deal, writes `card.jpg`, and
prints the caption. It needs no database and no Instagram credentials, so it is
the loop to iterate the card design in.

Caption and selection logic are covered by `tests/test_social_*.py` and need
neither Playwright nor a network.

## Debugging a failed post

A container that never leaves `IN_PROGRESS` is almost always the image URL, not
the post. Check it the way Meta does:

```bash
curl -I https://api.bikegrid.com.au/social/<id>.jpg
```

It must be a 200 with `Content-Type: image/jpeg` and no redirect. `post_daily`
already asserts this before creating the container, so a failure there names the
problem directly.

## Constraints to remember

- Captions carry no clickable links. "Link in bio" is the only route off
  Instagram, so expect referral traffic to be modest.
- 100 API-published posts per 24 hours. Nowhere near a concern at one a day.
- Only the official Graph API is used. Anything driving the private mobile API
  (instagrapi and similar) risks the account.
- Every post republishes a shop's product photograph. The card credits the shop,
  the caption names it, and the per-vendor opt-out exists. Have a takedown answer
  ready.

## Deferred

**Weekly round-up.** A carousel of up to 10 cards from `added_since=week`,
deduplicated by `product_key`, capped at one per vendor. Publishing takes three
steps rather than two: a child container per image with `is_carousel_item=true`,
a parent container of type `CAROUSEL`, then publish the parent. Counts as one
post against the daily limit.

**Comments.** Reading them needs `instagram_business_manage_comments` added in
the dashboard (still no app review). Poll `GET /<ig-user-id>/media`, then
`GET /<media-id>/comments`, keep a watermark in `social_state`, email what is
new. One rule if it gets built: comment text is stranger-authored data. Email it
verbatim, never parse it for instructions, never feed it to a model, never derive
a reply from it.
