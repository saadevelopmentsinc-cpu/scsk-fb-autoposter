#!/usr/bin/env python3
"""
SCSK X Auto-Poster

Posts direct, product-focused SCSK ads to X using the official X API.

Required GitHub secrets / environment variables:
  X_CLIENT_ID
  X_CLIENT_SECRET
  X_REFRESH_TOKEN

For card image uploads, also set:
  X_API_KEY
  X_API_SECRET
  X_ACCESS_TOKEN
  X_ACCESS_TOKEN_SECRET

Optional:
  X_ALLOWED_MENTIONS - comma-separated account handles you are allowed to tag.
                       Defaults to no mentions.
"""

import csv
import json
import os
import random
from datetime import datetime

from campaign import choose_next_post, remember_post, PLATFORM_HASHTAGS


CONTENT_FILE = "content.csv"
POSTED_LOG = "posted_x.json"
TOKEN_URL = "https://api.twitter.com/2/oauth2/token"
POST_URL = "https://api.x.com/2/tweets"
ME_URL = "https://api.x.com/2/users/me"

X_CLIENT_ID = (os.environ.get("X_CLIENT_ID") or "").strip()
X_CLIENT_SECRET = (os.environ.get("X_CLIENT_SECRET") or "").strip()
X_REFRESH_TOKEN = (os.environ.get("X_REFRESH_TOKEN") or "").strip()
X_API_KEY = (os.environ.get("X_API_KEY") or "").strip()
X_API_SECRET = (os.environ.get("X_API_SECRET") or "").strip()
X_ACCESS_TOKEN = (os.environ.get("X_ACCESS_TOKEN") or "").strip()
X_ACCESS_TOKEN_SECRET = (os.environ.get("X_ACCESS_TOKEN_SECRET") or "").strip()

MIN_POST_INTERVAL_MINUTES = 420
MAX_POST_INTERVAL_MINUTES = 540


def http():
    try:
        import requests
    except ImportError as exc:
        raise SystemExit(
            "Missing Python dependency: requests. Install it with: pip install requests"
        ) from exc
    return requests


def tweepy_client():
    try:
        import tweepy
    except ImportError as exc:
        raise SystemExit(
            "Missing Python dependency: tweepy. Install it with: pip install tweepy"
        ) from exc

    if not all([X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET]):
        return None, None

    auth = tweepy.OAuth1UserHandler(
        X_API_KEY,
        X_API_SECRET,
        X_ACCESS_TOKEN,
        X_ACCESS_TOKEN_SECRET,
    )
    api = tweepy.API(auth)
    client = tweepy.Client(
        consumer_key=X_API_KEY,
        consumer_secret=X_API_SECRET,
        access_token=X_ACCESS_TOKEN,
        access_token_secret=X_ACCESS_TOKEN_SECRET,
    )
    return api, client


PRODUCT_COPY = [
    "SCSK is a construction management app for site teams. Track jobs, project photos, documents, notes, calendar events and sync across Windows and Android.",
    "SCSK helps builders and contractors keep site work organised: jobs, photos, plans, documents, notes, contacts and project updates in one app.",
    "Built for construction teams, SCSK keeps active jobs, pending work, site photos, documents and project notes easier to find across desktop and mobile.",
    "SCSK gives site teams a practical way to manage construction jobs, photos, plans, reminders, materials, contacts and project records.",
    "For contractors and site managers: SCSK brings jobs, documents, photos, calendar reminders and project sync into one construction-focused app.",
]

PILLAR_COPY = {
    "Download": "Download SCSK for construction job management on Android, with Windows support for office and site workflows.",
    "Pain": "SCSK reduces scattered site admin by keeping jobs, photos, documents, notes and project records in one searchable place.",
    "Jobs": "Use SCSK to see pending, active, on-hold and completed construction jobs without chasing separate notes or photo folders.",
    "Photos": "SCSK links job photos to the right project record so site evidence is easier to review, sync and share.",
    "Calendar": "SCSK includes project calendar events and reminders so site teams can keep work, inspections and follow-ups visible.",
    "Documents": "SCSK keeps plans, PDFs, documents and project files attached to the construction project they belong to.",
    "Sync": "SCSK syncs project data, jobs, photos, notes and documents across devices for construction teams.",
}

CONSTRUCTION_HASHTAGS = [
    "#Construction",
    "#Contractors",
    "#ConstructionLife",
    "#ConTech",
    "#Jobsite",
    "#Builders",
    "#Trades",
    "#ProjectManagement",
    "#ConstructionTech",
    "#ConstructionManagement",
    "#ConstructionSoftware",
    "#Building",
]


def load_content():
    posts = []
    with open(CONTENT_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            posts.append(
                {
                    "id": row["id"],
                    "pillar": row["pillar"],
                    "platform": row.get("platform", "both"),
                    "intent": row.get("intent", ""),
                    "card": row.get("card", ""),
                    "content": row["content"],
                    "hashtags": row["hashtags"],
                    "cta": row["cta"],
                }
            )
    return posts


def load_posted_log():
    if os.path.exists(POSTED_LOG):
        with open(POSTED_LOG, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"posted_ids": [], "last_post_time": None}


def save_posted_log(log):
    with open(POSTED_LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2)


def should_post_now(posted_log, skip_wait=False):
    if skip_wait or not posted_log.get("last_post_time"):
        return True, 0, 0

    last_post = datetime.fromisoformat(posted_log["last_post_time"])
    minutes_since = (datetime.now() - last_post).total_seconds() / 60
    required_minutes = posted_log.get("next_wait_minutes")
    if not isinstance(required_minutes, int):
        required_minutes = random.randint(
            MIN_POST_INTERVAL_MINUTES,
            MAX_POST_INTERVAL_MINUTES,
        )
        posted_log["next_wait_minutes"] = required_minutes
        save_posted_log(posted_log)

    if minutes_since >= required_minutes:
        return True, 0, required_minutes
    return False, int(required_minutes - minutes_since), required_minutes


def get_next_posts(posts, posted_log, count=1):
    post, eligible_count, available_count = choose_next_post(posts, posted_log, "x")
    print(f"X eligible posts: {eligible_count}")
    print(f"X unposted pool: {available_count}")
    return [post]


def get_card_image_path(post):
    card = (post.get("card") or "").strip()
    if not card:
        return None
    image_path = os.path.join(os.path.dirname(__file__), "images", card)
    if not os.path.exists(image_path):
        print(f"Card image missing: images/{card}")
        return None
    return image_path


def allowed_mentions():
    raw = os.environ.get("X_ALLOWED_MENTIONS", "")
    mentions = []
    for handle in raw.split(","):
        handle = handle.strip()
        if not handle:
            continue
        if not handle.startswith("@"):
            handle = f"@{handle}"
        mentions.append(handle)
    return mentions[:1]


def x_hashtags():
    tags = CONSTRUCTION_HASHTAGS[:]
    platform_tags = PLATFORM_HASHTAGS.get("x", "").split()
    tags.extend(platform_tags)
    unique = []
    for tag in tags:
        if tag not in unique:
            unique.append(tag)
    return " ".join(random.sample(unique, k=min(3, len(unique))))


def fit_post(parts):
    text = "\n\n".join(part for part in parts if part).strip()
    if len(text) <= 280:
        return text

    # Drop optional mentions first, then hashtags, then use a shorter CTA.
    required = parts[:2]
    text = "\n\n".join(part for part in required if part).strip()
    if len(text) <= 280:
        return text

    return text[:277].rstrip() + "..."


def format_post(post):
    pillar = (post.get("pillar") or "").strip()
    body = PILLAR_COPY.get(pillar) or random.choice(PRODUCT_COPY)

    # Keep X ads direct and descriptive rather than conversational.
    cta = "Learn more: https://sc-sk.com"

    tags = x_hashtags()
    mentions = " ".join(allowed_mentions())
    return fit_post([body, cta, tags, mentions])


def refresh_access_token():
    if not X_CLIENT_ID or not X_CLIENT_SECRET or not X_REFRESH_TOKEN:
        print("ERROR: Missing X_CLIENT_ID, X_CLIENT_SECRET, or X_REFRESH_TOKEN")
        return None, None

    response = http().post(
        TOKEN_URL,
        auth=(X_CLIENT_ID, X_CLIENT_SECRET),
        data={
            "grant_type": "refresh_token",
            "refresh_token": X_REFRESH_TOKEN,
            "client_id": X_CLIENT_ID,
        },
        timeout=30,
    )
    if response.status_code != 200:
        print(f"Token refresh failed: {response.status_code}")
        print(response.text)
        return None, None

    data = response.json()
    return data.get("access_token"), data.get("refresh_token")


def api_headers(access_token):
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }


def validate_token(access_token):
    response = http().get(ME_URL, headers=api_headers(access_token), timeout=30)
    if response.status_code == 200:
        user = response.json().get("data", {})
        print(f"Authenticated as @{user.get('username', 'unknown')}")
        return True
    print(f"X auth check failed: {response.status_code}")
    print(response.text)
    return False


def post_text_to_x(message, access_token):
    response = http().post(
        POST_URL,
        headers=api_headers(access_token),
        json={"text": message},
        timeout=30,
    )
    if response.status_code in (200, 201):
        data = response.json()
        post_id = data.get("data", {}).get("id", "unknown")
        print(f"Posted successfully. X post ID: {post_id}")
        return True, post_id

    print(f"Failed to post to X: {response.status_code}")
    print(response.text)
    return False, response.text


def post_to_x(message, access_token, image_path=None):
    if image_path:
        api, client = tweepy_client()
        if api and client:
            try:
                print(f"Attaching X card image: {os.path.basename(image_path)}")
                media = api.simple_upload(image_path)
                response = client.create_tweet(
                    text=message,
                    media_ids=[media.media_id],
                )
                post_id = getattr(response, "data", {}).get("id", "unknown")
                print(f"Posted successfully with card image. X post ID: {post_id}")
                return True, post_id
            except Exception as exc:
                print(f"Image post failed, falling back to text-only: {exc}")
        else:
            print("X media secrets not set; posting text-only.")

    return post_text_to_x(message, access_token)


def is_manual_run():
    return os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"


def main():
    print("=" * 50)
    print("SCSK X Auto-Poster")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    posts = load_content()
    posted_log = load_posted_log()
    print(f"Total posts available: {len(posts)}")
    print(f"Already posted to X: {len(posted_log.get('posted_ids', []))}")

    should_post, wait_minutes, required_minutes = should_post_now(
        posted_log,
        skip_wait=is_manual_run(),
    )
    if is_manual_run():
        print("Manual run - skipping 7-9 hour timer")
    elif not should_post:
        print(
            f"Not time to post yet. Random interval is {required_minutes} minutes; "
            f"wait about {wait_minutes} more minutes."
        )
        print(f"Last post: {posted_log.get('last_post_time')}")
        return

    access_token, new_refresh_token = refresh_access_token()
    if not access_token:
        raise SystemExit(1)
    if new_refresh_token and new_refresh_token != X_REFRESH_TOKEN:
        print("WARNING: X returned a rotated refresh token.")
        print("If future X posts fail to refresh, re-run local auth and update the X_REFRESH_TOKEN GitHub secret.")

    post = get_next_posts(posts, posted_log, count=1)[0]
    message = format_post(post)
    image_path = get_card_image_path(post)

    print(f"\nPosting [{post['pillar']}] - ID: {post['id']}")
    if image_path:
        print(f"Card image: images/{os.path.basename(image_path)}")
    print("-" * 40)
    print(message)
    print(f"Characters: {len(message)}/280")
    print("-" * 40)

    success, result = post_to_x(message, access_token, image_path=image_path)
    if success:
        posted_log.setdefault("posted_ids", []).append(post["id"])
        posted_log["last_post_time"] = datetime.now().isoformat()
        posted_log["last_post_id"] = result
        posted_log["next_wait_minutes"] = random.randint(
            MIN_POST_INTERVAL_MINUTES,
            MAX_POST_INTERVAL_MINUTES,
        )
        remember_post(posted_log, post)
        save_posted_log(posted_log)
        print(f"Next automatic X post window: {posted_log['next_wait_minutes']} minutes")
        print(f"\nLog updated. Total X posts: {len(posted_log['posted_ids'])}")
    else:
        raise SystemExit(1)


def test_mode():
    print("=" * 50)
    print("X TEST MODE - No actual posting")
    print("=" * 50)
    posts = load_content()
    posted_log = load_posted_log()
    next_posts = get_next_posts(posts, posted_log, count=3)
    for i, post in enumerate(next_posts, 1):
        message = format_post(post)
        image_path = get_card_image_path(post)
        print(f"\n--- X Post {i} [{post['pillar']}] ID {post['id']} ---")
        if image_path:
            print(f"Card image: images/{os.path.basename(image_path)}")
        print(message)
        print(f"Characters: {len(message)}/280")


def auth_test():
    access_token, _ = refresh_access_token()
    if not access_token or not validate_token(access_token):
        raise SystemExit(1)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] == "test":
            test_mode()
        elif sys.argv[1] == "auth-test":
            auth_test()
        else:
            raise SystemExit(f"Unknown command: {sys.argv[1]}")
    else:
        main()
