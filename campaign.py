import random
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


APP_URL = "https://play.google.com/store/apps/details?id=com.saa.scsk_app"
WEBSITE_URL = "https://sc-sk.com/"

PLATFORM_LABELS = {
    "facebook": "Facebook",
    "linkedin": "LinkedIn",
    "x": "X",
}

PLATFORM_HASHTAGS = {
    "facebook": "#constructionlife #contractorlife #builders #tradies #sitework",
    "linkedin": "#constructiontechnology #constructionmanagement #contractors #fieldoperations #proptech",
    "x": "#Construction #Contractors #ConstructionLife #ConTech #Jobsite",
}


def row_platforms(post):
    raw = (post.get("platform") or "both").lower()
    if raw in ("all", "both", ""):
        return {"facebook", "linkedin", "x"}
    raw = raw.replace("twitter", "x")
    return {part.strip() for part in raw.replace("/", ",").split(",") if part.strip()}


def is_for_platform(post, platform):
    return platform in row_platforms(post)


def tracked_url(url, platform, campaign="scsk_launch"):
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.update({
        "utm_source": platform,
        "utm_medium": "autoposter",
        "utm_campaign": campaign,
    })
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def apply_tracking(text, platform):
    if not text:
        return text

    def replace_url(match):
        url = match.group(0)
        return tracked_url(url, platform)

    return re.sub(
        r"https://play\.google\.com/store/apps/details\?id=com\.saa\.scsk_app|https://sc-sk\.com/?",
        replace_url,
        text,
    )


def get_recent_values(posted_log, key, limit=4):
    return list(posted_log.get(key, []))[-limit:]


def choose_next_post(posts, posted_log, platform):
    eligible = [p for p in posts if is_for_platform(p, platform)]
    posted_ids = set(posted_log.get("posted_ids", []))
    available = [p for p in eligible if p["id"] not in posted_ids]

    if not available:
        print(f"All {PLATFORM_LABELS.get(platform, platform)} posts exhausted. Resetting cycle...")
        posted_log["posted_ids"] = []
        posted_log["recent_pillars"] = []
        posted_log["recent_cards"] = []
        available = eligible

    recent_pillars = set(get_recent_values(posted_log, "recent_pillars", limit=3))
    recent_cards = set(get_recent_values(posted_log, "recent_cards", limit=3))

    preferred = [
        p for p in available
        if p.get("pillar") not in recent_pillars and p.get("card") not in recent_cards
    ]
    if not preferred:
        preferred = [p for p in available if p.get("pillar") not in recent_pillars]
    if not preferred:
        preferred = available

    # Keep early content moving forward, but vary within the next few good options.
    window = preferred[: min(5, len(preferred))]
    return random.choice(window), len(eligible), len(available)


def remember_post(posted_log, post):
    posted_log.setdefault("recent_pillars", []).append(post.get("pillar", ""))
    posted_log["recent_pillars"] = posted_log["recent_pillars"][-6:]
    posted_log.setdefault("recent_cards", []).append(post.get("card", ""))
    posted_log["recent_cards"] = posted_log["recent_cards"][-6:]
