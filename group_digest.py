#!/usr/bin/env python3
"""
SCSK Group Post Digest
Generates 3 country-specific group-ready posts (US, UK, AU/NZ) every morning
and opens a GitHub Issue with all of them, ready to copy/paste manually
into trade Facebook groups.

Why semi-automated?
- Facebook removed third-party group posting from the Graph API in 2020.
- Browser automation gets accounts banned.
- The founder voice ("I built this because...") outperforms marketing copy in
  trade groups by 10x — and humans saying it manually is the only way.

This script does the boring parts: picks the source post, rewords it for each
country, attaches the right image, creates the Issue with a copy-friendly
format. You do the 5-minute "open Facebook, paste, click post" part.
"""

import os
import json
import csv
import random
import base64
import requests
from datetime import datetime
from pathlib import Path

# Pillow for image resize/upload to Issue (same approach as fb_poster.py)
try:
    from PIL import Image
    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False

# =============================================================================
# CONFIGURATION
# =============================================================================

GITHUB_TOKEN = os.environ.get('DIGEST_TOKEN') or os.environ.get('GITHUB_TOKEN')
GITHUB_REPO = os.environ.get('GITHUB_REPOSITORY')  # e.g., "saadevelopmentsinc-cpu/scsk-fb-autoposter"

CONTENT_FILE = "content.csv"
DIGEST_LOG = "digest_posted.json"
IMAGES_DIR = Path(__file__).parent / "images"

# Same image size limits as the FB poster — keeps GitHub attachment + future
# group posting within Facebook's quirky limits.
MAX_UPLOAD_BYTES = 3 * 1024 * 1024
MAX_DIMENSION = 1920
JPEG_QUALITY = 85

# Pool of source pillars to draw from. Skip pillars that don't translate well
# to "founder voice" group posts (e.g. straight feature lists).
# Founder pillar is excluded — the country opener already plays the
# "I'm a foreman who built this" role, so adding a Founder post would be
# redundantly self-introducing twice.
GOOD_PILLARS_FOR_GROUPS = {
    'Pain Point', 'Tips', 'Photo', 'Quick Win',
    'Social Proof', 'Comparison',
}

# How many days before the same source post can be reused
COOLDOWN_DAYS = 30

# =============================================================================
# COUNTRY-SPECIFIC REWORDING
# =============================================================================
# Each country gets:
#   - Different opener (region-appropriate greeting + foreman framing)
#   - Dialect tweaks (tradie/mate vs buddy/GC vs lads/mate)
#   - Different soft-CTA
#   - Different group-rules-friendly closer

COUNTRY_CONFIGS = {
    'US': {
        'name': 'United States',
        'opener_options': [
            "Hey folks — I'm a site foreman who got tired of bad construction software.",
            "Posting this for any other GCs or subs in the group:",
            "Built this myself after years of dealing with paper, spreadsheets, and apps that don't work offline.",
            "Quick share for the contractors here — I built an app to solve a real jobsite problem and would love feedback.",
        ],
        'dialect_swaps': {
            # CSV uses Aussie terms; swap them for US-readable equivalents.
            # Order matters: longer phrases first, so 'on site' is replaced
            # before 'site' alone gets touched.
            'on site': 'on the jobsite',
            'site foreman': 'site foreman',  # No-op: keep this compound intact
            'tradie': 'contractor',
            'tradies': 'contractors',
            'sparky': 'electrician',
            'sparkies': 'electricians',
            'subbie': 'sub',
            'subbies': 'subs',
            'mate': 'buddy',
            'smoko': 'lunch break',
            'tilers': 'tile setters',
            'tiler': 'tile setter',
            # Note: 'site' alone NOT swapped — too many false positives
            # (site foreman, site safety, site management). US readers
            # understand 'site' just fine in construction context.
        },
        'soft_cta_options': [
            "If you'd want to test it, it's at sc-sk.com — free during beta. Would really value honest feedback from US contractors.",
            "Free during the beta. If anyone here wants to try it on a real jobsite, I'd love your input. sc-sk.com",
            "Beta is open and free. Built it for guys like us — sc-sk.com if you want a look.",
        ],
        'closer_options': [
            "Happy to answer any questions in the comments.",
            "Mods — please remove if this isn't allowed. Just trying to get real users.",
            "Not trying to spam, just looking for honest testers. Tell me what's broken.",
        ],
    },
    'UK': {
        'name': 'United Kingdom',
        'opener_options': [
            "Hello all — I'm a site foreman who got fed up with rubbish construction software.",
            "Quick post for the tradesmen here:",
            "Built this myself after years of paper job sheets and apps that crash on site.",
            "Sharing this for any builders, sparks, or plumbers in the group — built an app to solve a real site problem.",
        ],
        'dialect_swaps': {
            'tradie': 'tradesman',
            'tradies': 'tradesmen',
            'subbie': 'subbie',  # subbie works in UK too
            'subbies': 'subbies',
            'mate': 'mate',
            'smoko': 'tea break',
            'tilers': 'tilers',
            # UK keeps "site", "sparky", "plumber" — they translate fine.
        },
        'soft_cta_options': [
            "Free during the beta. Would love feedback from UK tradesmen on what works and what doesn't. sc-sk.com",
            "It's at sc-sk.com — free for now. Honest feedback from UK builders much appreciated.",
            "Beta access is free. If anyone here would test it on a real site, I'd value your input. sc-sk.com",
        ],
        'closer_options': [
            "Happy to answer any questions below.",
            "Mods — apologies if this isn't allowed, please remove. Just trying to find real users.",
            "Not trying to flog anything, just want honest feedback. Tell me what doesn't work.",
        ],
    },
    'AU_NZ': {
        'name': 'Australia / New Zealand',
        'opener_options': [
            "Gday all — I'm a site foreman who got sick of bad construction apps.",
            "Quick one for the tradies here:",
            "Built this myself after years of paper, spreadsheets, and apps that don't work offline.",
            "Sharing for any builders, sparkies, or plumbers in the group — I built an app to fix a real site problem.",
        ],
        'dialect_swaps': {
            # No swaps needed — CSV is already in AU voice
        },
        'soft_cta_options': [
            "Free during beta. Would really value feedback from Aussie/Kiwi tradies. sc-sk.com",
            "Beta is open and free. Have a crack at it and tell me what's broken — sc-sk.com",
            "Free for now at sc-sk.com. Built by a foreman, for tradies. Would love your input.",
        ],
        'closer_options': [
            "Happy to answer any questions below.",
            "Mods — pull this if it's not allowed. Just looking for honest testers.",
            "Not trying to spam. Just want real feedback from blokes who actually use this stuff.",
        ],
    },
}

# =============================================================================
# GITHUB API HELPERS
# =============================================================================

def gh_request(method, endpoint, **kwargs):
    """Make an authenticated GitHub API request."""
    url = f"https://api.github.com{endpoint}"
    headers = kwargs.pop('headers', {})
    headers.update({
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
    })
    return requests.request(method, url, headers=headers, timeout=30, **kwargs)


def upload_image_to_issue_attachment(image_path):
    """
    GitHub doesn't have a public upload-attachment API, but we can embed
    images via base64 data URIs. For SCSK's small post images (<1MB after
    resize) this works fine and renders correctly in Issue body markdown.

    Returns a markdown image string ready to embed in the Issue body, or
    None if upload fails.
    """
    try:
        prepared = _prepare_image(image_path)
        with open(prepared, 'rb') as f:
            data = f.read()
        b64 = base64.b64encode(data).decode('ascii')
        # Detect mime type from extension
        ext = Path(prepared).suffix.lower().lstrip('.')
        if ext == 'jpg':
            ext = 'jpeg'
        size_kb = len(data) / 1024
        print(f"   📎 Embedding image: {os.path.basename(image_path)} ({size_kb:.0f}KB)")
        # Clean up temp file if we created one
        if prepared != str(image_path):
            try: os.unlink(prepared)
            except OSError: pass
        return f"data:image/{ext};base64,{b64}", os.path.basename(image_path)
    except Exception as e:
        print(f"   ⚠️  Image embed failed: {e}")
        return None, os.path.basename(image_path)


def _prepare_image(image_path):
    """Same resize logic as fb_poster.py — keeps images small for Issue body."""
    if not _HAS_PIL:
        return str(image_path)
    try:
        original_size = os.path.getsize(image_path)
        with Image.open(image_path) as img:
            width, height = img.size
            if max(width, height) <= MAX_DIMENSION and original_size <= MAX_UPLOAD_BYTES:
                return str(image_path)

            if max(width, height) > MAX_DIMENSION:
                ratio = MAX_DIMENSION / max(width, height)
                img = img.resize((int(width*ratio), int(height*ratio)), Image.LANCZOS)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            import tempfile
            tmp = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
            tmp.close()
            for q in (JPEG_QUALITY, 75, 65):
                img.save(tmp.name, 'JPEG', quality=q, optimize=True)
                if os.path.getsize(tmp.name) <= MAX_UPLOAD_BYTES:
                    return tmp.name
            return tmp.name
    except Exception as e:
        print(f"   ⚠️  Resize failed: {e}")
        return str(image_path)


def create_issue(title, body, labels=None):
    """Open a new GitHub Issue."""
    payload = {'title': title, 'body': body}
    if labels:
        payload['labels'] = labels
    resp = gh_request('POST', f'/repos/{GITHUB_REPO}/issues', json=payload)
    if resp.status_code in (200, 201):
        url = resp.json().get('html_url')
        print(f"✓ Issue created: {url}")
        return resp.json()
    else:
        print(f"✗ Issue creation failed: {resp.status_code}")
        print(f"  Response: {resp.text[:500]}")
        return None


# =============================================================================
# CONTENT SELECTION & REWORDING
# =============================================================================

def load_content():
    """Load source posts from CSV."""
    posts = []
    with open(CONTENT_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            posts.append({
                'id': row['id'],
                'pillar': row['pillar'],
                'content': row['content'],
                'hashtags': row['hashtags'],
                'cta': row['cta'],
            })
    return posts


def load_digest_log():
    """Load record of which source posts have been used in past digests."""
    if os.path.exists(DIGEST_LOG):
        with open(DIGEST_LOG, 'r') as f:
            return json.load(f)
    return {'used': []}


def save_digest_log(log):
    with open(DIGEST_LOG, 'w') as f:
        json.dump(log, f, indent=2)


def pick_source_post(posts, log):
    """
    Pick a source post that:
      - Is in a 'good for groups' pillar
      - Hasn't been used in the last COOLDOWN_DAYS days
    """
    cooldown_cutoff = datetime.now().timestamp() - (COOLDOWN_DAYS * 86400)
    recent_ids = {entry['id'] for entry in log['used']
                  if entry.get('timestamp', 0) > cooldown_cutoff}

    candidates = [p for p in posts
                  if p['pillar'] in GOOD_PILLARS_FOR_GROUPS
                  and p['id'] not in recent_ids]

    if not candidates:
        # All eligible posts used recently — fall back to oldest used
        print("⚠️  All eligible posts used recently — picking oldest.")
        log['used'].sort(key=lambda x: x.get('timestamp', 0))
        oldest_id = log['used'][0]['id'] if log['used'] else posts[0]['id']
        return next((p for p in posts if p['id'] == oldest_id), posts[0])

    return random.choice(candidates)


def reword_for_country(post, country_key):
    """
    Transform a CSV post into a country-specific 'founder voice' group post.

    Strategy: opener → reworded content → soft CTA → closer.
    Drops the hashtag block entirely (group posts perform worse with hashtags).
    """
    config = COUNTRY_CONFIGS[country_key]
    content = post['content']

    # Apply dialect swaps (case-preserving for first letter, case-insensitive match)
    for src, dst in config['dialect_swaps'].items():
        # Whole-word replacement, case-insensitive but preserve target casing
        import re
        pattern = re.compile(r'\b' + re.escape(src) + r'\b', re.IGNORECASE)
        content = pattern.sub(dst, content)

    opener = random.choice(config['opener_options'])
    soft_cta = random.choice(config['soft_cta_options'])
    closer = random.choice(config['closer_options'])

    # Compose the full post
    full_post = f"{opener}\n\n{content}\n\n{soft_cta}\n\n{closer}"
    return full_post


def pick_image_for_post(post):
    """
    Same logic as fb_poster.py — every 3rd post gets Screenshot1, others get
    a random ad image. For digest purposes we just pick a random ad image
    since group posts benefit from variety more than the FB Page rotation.
    """
    ad_images = [f'ad-{i}.png' for i in range(1, 11)]
    selected = random.choice(ad_images)
    path = IMAGES_DIR / selected
    if not path.exists():
        # Try Screenshot1.jpg as fallback
        path = IMAGES_DIR / 'Screenshot1.jpg'
        if not path.exists():
            return None, None
    return path, path.name


# =============================================================================
# DIGEST ASSEMBLY
# =============================================================================

def build_issue_body(source_post, country_drafts, image_data):
    """
    Build the markdown body of the daily digest Issue.

    Layout:
      - Header with date + source post info
      - Image preview (collapsible)
      - 3 sections (US, UK, AU/NZ), each with copy-friendly code block
      - Tips footer
    """
    today = datetime.now().strftime('%A, %d %B %Y')
    body_parts = [
        f"# Group post digest — {today}",
        "",
        f"Source post: **#{source_post['id']}** ({source_post['pillar']})",
        "",
        "**How to use:** pick whichever country flavor matches the group you're posting to. Tap the copy button on the code block, paste into Facebook. Save the image below to your phone first.",
        "",
        "---",
        "",
    ]

    # Image embed (if we have one)
    image_md, image_name = image_data
    if image_md:
        body_parts.extend([
            f"### 📸 Image to attach: `{image_name}`",
            "",
            "<details><summary>Click to expand image</summary>",
            "",
            f"![{image_name}]({image_md})",
            "",
            "</details>",
            "",
            "Right-click → Save image. Or on mobile, long-press the image inside the spoiler to save.",
            "",
            "---",
            "",
        ])
    else:
        body_parts.extend([
            "_(No image attached this round)_",
            "",
            "---",
            "",
        ])

    # Country drafts
    country_emoji = {'US': '🇺🇸', 'UK': '🇬🇧', 'AU_NZ': '🇦🇺🇳🇿'}
    for country_key, draft in country_drafts.items():
        config = COUNTRY_CONFIGS[country_key]
        emoji = country_emoji.get(country_key, '🌍')
        body_parts.extend([
            f"## {emoji} {config['name']} version",
            "",
            "```",
            draft,
            "```",
            "",
            "---",
            "",
        ])

    # Footer with tips + checkboxes for tracking
    body_parts.extend([
        "## ✅ Posting checklist",
        "",
        "Tick off as you post (helps you remember which groups you've hit):",
        "",
        "- [ ] Posted to a US group",
        "- [ ] Posted to a UK group",
        "- [ ] Posted to an AU/NZ group",
        "- [ ] Replied to first comment within 30 min",
        "- [ ] Closed this issue when done",
        "",
        "## 🛡️ Group posting reminders",
        "",
        "- Lurk + comment in a group at least a week before you post.",
        "- One group per day per country (avoid spam network detection).",
        "- Different group → don't paste the exact same wording. Tweak a sentence.",
        "- Read pinned rules — many groups have \"Self-Promo Sundays\" or \"Founder Friday\".",
        "- Reply to comments fast — response speed boosts group algorithm reach.",
        "",
        "---",
        "",
        f"_Auto-generated by `group_digest.py` at {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}_",
    ])

    return '\n'.join(body_parts)


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 50)
    print("SCSK Group Post Digest Generator")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"PIL:  {'available' if _HAS_PIL else 'NOT installed (image embedding will skip)'}")
    print("=" * 50)

    # Verify env
    if not GITHUB_TOKEN:
        print("ERROR: No GITHUB_TOKEN or DIGEST_TOKEN env var set.")
        exit(1)
    if not GITHUB_REPO:
        print("ERROR: GITHUB_REPOSITORY env var not set.")
        exit(1)
    print(f"Repo: {GITHUB_REPO}")

    # Load source posts
    posts = load_content()
    log = load_digest_log()
    print(f"Source posts available: {len(posts)}")
    print(f"Already used in digests: {len(log['used'])}")

    # Pick source
    source = pick_source_post(posts, log)
    print(f"\n📝 Selected source: #{source['id']} ({source['pillar']})")
    print(f"   {source['content'][:120]}...")

    # Reword for each country
    print("\n🌍 Generating country variants...")
    country_drafts = {}
    for country_key in ('US', 'UK', 'AU_NZ'):
        country_drafts[country_key] = reword_for_country(source, country_key)
        print(f"   ✓ {country_key} version ({len(country_drafts[country_key])} chars)")

    # Pick & embed image
    print("\n📸 Selecting image...")
    image_path, image_name = pick_image_for_post(source)
    if image_path:
        print(f"   Selected: {image_name}")
        image_data = upload_image_to_issue_attachment(image_path)
    else:
        print("   ⚠️  No images found — skipping attachment.")
        image_data = (None, None)

    # Build & post Issue
    today = datetime.now().strftime('%Y-%m-%d')
    issue_title = f"📣 Group post digest — {today} (source #{source['id']})"
    issue_body = build_issue_body(source, country_drafts, image_data)

    print(f"\n📬 Creating GitHub Issue...")
    print(f"   Title: {issue_title}")
    print(f"   Body length: {len(issue_body)} chars")
    issue = create_issue(issue_title, issue_body, labels=['group-digest'])

    if issue:
        # Log the source post as used
        log['used'].append({
            'id': source['id'],
            'timestamp': datetime.now().timestamp(),
            'issue_url': issue.get('html_url'),
        })
        save_digest_log(log)
        print(f"\n✓ Digest log updated. Total used: {len(log['used'])}")
    else:
        print("\n✗ Issue creation failed. Not logging.")
        exit(1)


if __name__ == '__main__':
    main()
