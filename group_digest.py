#!/usr/bin/env python3
"""
SCSK Group Post Digest
Generates market-specific group-ready posts every morning and opens a GitHub
Issue with all of them, ready to copy/paste manually into relevant trade
Facebook groups whose rules allow member or product posts.

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

MARKET_ORDER = (
    'AU_NZ', 'US', 'UK', 'CA', 'IE',
    'ZA', 'UAE_GCC', 'SG_MY', 'IN', 'PH',
)

MARKET_EMOJI = {
    'AU_NZ': '🇦🇺🇳🇿',
    'US': '🇺🇸',
    'UK': '🇬🇧',
    'CA': '🇨🇦',
    'IE': '🇮🇪',
    'ZA': '🇿🇦',
    'UAE_GCC': '🇦🇪',
    'SG_MY': '🇸🇬🇲🇾',
    'IN': '🇮🇳',
    'PH': '🇵🇭',
}

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
        'search_queries': [
            'construction contractors USA',
            'general contractors USA',
            'construction site managers USA',
            'construction project managers USA',
            'small construction business USA',
            'construction technology USA',
        ],
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
            "If you want a practical construction app for real jobsites, it's at https://sc-sk.com/. Built by a foreman and available now.",
            "The Android app is on Google Play: https://play.google.com/store/apps/details?id=com.saa.scsk_app. I'd value feedback from US contractors.",
            "Built it for crews who need jobs, photos, reports, and calculators in one place — https://sc-sk.com/ if you want a look.",
        ],
        'closer_options': [
            "Happy to answer any questions in the comments.",
            "Mods — please remove if this isn't allowed. Just sharing a tool built for real site work.",
            "Not trying to spam, just sharing something I built for contractors who need less admin.",
        ],
    },
    'UK': {
        'name': 'United Kingdom',
        'search_queries': [
            'UK builders and trades',
            'construction site managers UK',
            'UK contractors network',
            'UK site supervisors',
            'small builders UK',
            'construction technology UK',
        ],
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
            "Available now at https://sc-sk.com/. Would love feedback from UK tradesmen on what works and what doesn't.",
            "The Android app is on Google Play: https://play.google.com/store/apps/details?id=com.saa.scsk_app",
            "If anyone here would use it on a real site, I'd value your input. https://sc-sk.com/",
        ],
        'closer_options': [
            "Happy to answer any questions below.",
            "Mods — apologies if this isn't allowed, please remove. Just trying to find real users.",
            "Not trying to flog anything, just sharing a practical tool built from site work.",
        ],
    },
    'AU_NZ': {
        'name': 'Australia / New Zealand',
        'search_queries': [
            'Australian builders and tradies',
            'construction site managers Australia',
            'New Zealand builders and tradies',
            'site supervisors Australia',
            'construction project managers New Zealand',
            'construction technology Australia',
        ],
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
            "Available now. Would really value feedback from Aussie/Kiwi tradies. https://sc-sk.com/",
            "Have a crack at it on a real job and tell me what would make it better — https://play.google.com/store/apps/details?id=com.saa.scsk_app",
            "Built by a foreman, for tradies. Jobs, photos, reports, calculators, and site tools in one place. https://sc-sk.com/",
        ],
        'closer_options': [
            "Happy to answer any questions below.",
            "Mods — pull this if it's not allowed. Just sharing a tool built for the jobsite.",
            "Not trying to spam. Just want real feedback from people who actually use this stuff.",
        ],
    },
    'CA': {
        'name': 'Canada',
        'search_queries': [
            'Canadian construction contractors',
            'builders and trades Canada',
            'construction site managers Canada',
            'Canadian general contractors',
            'construction project managers Canada',
            'construction technology Canada',
        ],
        'opener_options': [
            "Hello — I'm a site foreman who got tired of construction software that falls apart in the field.",
            "Quick share for the Canadian contractors and site managers here:",
            "I built this after years of paper notes, scattered photos, and unreliable site apps.",
        ],
        'dialect_swaps': {
            'tradie': 'contractor',
            'tradies': 'contractors',
            'sparky': 'electrician',
            'sparkies': 'electricians',
            'subbie': 'subcontractor',
            'subbies': 'subcontractors',
            'smoko': 'coffee break',
        },
        'soft_cta_options': [
            "It's available now at https://sc-sk.com/. I'd value feedback from Canadian construction teams.",
            "The Android app is on Google Play: https://play.google.com/store/apps/details?id=com.saa.scsk_app",
            "If your crew needs offline site records, photos, and reports in one place, have a look at https://sc-sk.com/.",
        ],
        'closer_options': [
            "Happy to answer practical questions in the comments.",
            "Mods — please remove if product posts aren't allowed here.",
            "Sharing for feedback from people who actually run work in the field.",
        ],
    },
    'IE': {
        'name': 'Ireland',
        'search_queries': [
            'Irish builders and trades',
            'construction professionals Ireland',
            'site managers Ireland',
            'Irish construction contractors',
            'construction project managers Ireland',
            'construction technology Ireland',
        ],
        'opener_options': [
            "Hello all — I'm a site foreman who built a practical app for keeping site records together.",
            "Quick one for the Irish builders, trades, and site managers here:",
            "I built this after years of paper, spreadsheets, and job photos scattered everywhere.",
        ],
        'dialect_swaps': {
            'tradie': 'tradesperson',
            'tradies': 'tradespeople',
            'sparky': 'electrician',
            'sparkies': 'electricians',
            'smoko': 'tea break',
        },
        'soft_cta_options': [
            "Available at https://sc-sk.com/. I'd genuinely value feedback from Irish site teams.",
            "The Android app is on Google Play: https://play.google.com/store/apps/details?id=com.saa.scsk_app",
            "If it sounds useful on a real job, take a look at https://sc-sk.com/ and tell me what it still needs.",
        ],
        'closer_options': [
            "Happy to answer any questions below.",
            "Mods — apologies if this type of post isn't allowed.",
            "Sharing for practical feedback, not to flood the group with ads.",
        ],
    },
    'ZA': {
        'name': 'South Africa',
        'search_queries': [
            'South African construction professionals',
            'builders and contractors South Africa',
            'site managers South Africa',
            'construction project managers South Africa',
            'small contractors South Africa',
            'construction technology South Africa',
        ],
        'opener_options': [
            "Hello — I'm a site foreman who built an offline-first app for everyday construction records.",
            "Quick share for the South African contractors and site managers here:",
            "I built this because site photos, notes, checklists, and reports should not live in five different places.",
        ],
        'dialect_swaps': {
            'tradie': 'contractor',
            'tradies': 'contractors',
            'sparky': 'electrician',
            'sparkies': 'electricians',
            'smoko': 'tea break',
        },
        'soft_cta_options': [
            "Available now at https://sc-sk.com/. Feedback from South African construction teams would be valuable.",
            "The Android app is here: https://play.google.com/store/apps/details?id=com.saa.scsk_app",
            "If reliable offline site records matter to your crew, have a look at https://sc-sk.com/.",
        ],
        'closer_options': [
            "Happy to answer questions from anyone working on site.",
            "Mods — please remove if product posts aren't permitted.",
            "I'd value honest feedback from contractors using it in real conditions.",
        ],
    },
    'UAE_GCC': {
        'name': 'UAE / Gulf',
        'search_queries': [
            'UAE construction professionals',
            'Dubai contractors and site managers',
            'GCC construction network',
            'UAE construction project managers',
            'Gulf site engineers',
            'Middle East construction technology',
        ],
        'opener_options': [
            "Hello — I'm a construction foreman who built an app to simplify daily site records.",
            "Sharing this for the contractors, engineers, and site managers working across the Gulf:",
            "I built this to keep job photos, notes, checklists, and reports usable even when connectivity is poor.",
        ],
        'dialect_swaps': {
            'tradie': 'site professional',
            'tradies': 'site professionals',
            'sparky': 'electrician',
            'sparkies': 'electricians',
            'subbie': 'subcontractor',
            'subbies': 'subcontractors',
            'smoko': 'break',
        },
        'soft_cta_options': [
            "You can see it at https://sc-sk.com/. Feedback from UAE and Gulf construction teams would be welcome.",
            "The Android app is available here: https://play.google.com/store/apps/details?id=com.saa.scsk_app",
            "If your team needs structured daily site records, take a look at https://sc-sk.com/.",
        ],
        'closer_options': [
            "Happy to answer workflow or product questions below.",
            "Admins — please remove if member product posts aren't allowed.",
            "Sharing to learn what Gulf construction teams need from a field app.",
        ],
    },
    'SG_MY': {
        'name': 'Singapore / Malaysia',
        'search_queries': [
            'Singapore construction professionals',
            'Malaysia contractors and builders',
            'construction site managers Singapore Malaysia',
            'Singapore construction project managers',
            'Malaysia site engineers',
            'Southeast Asia construction technology',
        ],
        'opener_options': [
            "Hello — I'm a site foreman who built an offline-first construction management app.",
            "Quick share for the Singapore and Malaysian contractors and site teams here:",
            "I built this to replace scattered site photos, paper notes, and late daily reports.",
        ],
        'dialect_swaps': {
            'tradie': 'site professional',
            'tradies': 'site professionals',
            'sparky': 'electrician',
            'sparkies': 'electricians',
            'subbie': 'subcontractor',
            'subbies': 'subcontractors',
            'smoko': 'break',
        },
        'soft_cta_options': [
            "It's available at https://sc-sk.com/. I'd value feedback from Singaporean and Malaysian site teams.",
            "The Android app is here: https://play.google.com/store/apps/details?id=com.saa.scsk_app",
            "If it suits your field workflow, take a look at https://sc-sk.com/ and tell me what should improve.",
        ],
        'closer_options': [
            "Happy to answer any questions in the comments.",
            "Admins — please remove if this isn't suitable for the group.",
            "Looking for practical feedback from people running active sites.",
        ],
    },
    'IN': {
        'name': 'India',
        'search_queries': [
            'Indian construction professionals',
            'builders and contractors India',
            'site engineers and managers India',
            'construction project managers India',
            'small contractors India',
            'construction technology India',
        ],
        'opener_options': [
            "Hello — I'm a site foreman who built an app to make daily construction records easier.",
            "Sharing this for the contractors, site engineers, and project teams in India:",
            "I built this because site photos, notes, checklists, and reports should stay organised even offline.",
        ],
        'dialect_swaps': {
            'tradie': 'site professional',
            'tradies': 'site professionals',
            'sparky': 'electrician',
            'sparkies': 'electricians',
            'subbie': 'subcontractor',
            'subbies': 'subcontractors',
            'smoko': 'break',
        },
        'soft_cta_options': [
            "Available now at https://sc-sk.com/. Feedback from Indian construction teams would be genuinely useful.",
            "The Android app is on Google Play: https://play.google.com/store/apps/details?id=com.saa.scsk_app",
            "If your team needs offline field records, have a look at https://sc-sk.com/.",
        ],
        'closer_options': [
            "Happy to answer practical questions below.",
            "Admins — please remove if member product posts are not allowed.",
            "I'd value direct feedback from engineers and contractors using it on site.",
        ],
    },
    'PH': {
        'name': 'Philippines',
        'search_queries': [
            'Philippines construction professionals',
            'Filipino contractors and builders',
            'site engineers Philippines',
            'construction project managers Philippines',
            'small contractors Philippines',
            'construction technology Philippines',
        ],
        'opener_options': [
            "Hello — I'm a site foreman who built an offline-first app for managing everyday site records.",
            "Quick share for the Filipino contractors, engineers, and builders here:",
            "I built this to keep job photos, daily notes, checklists, and reports together on site.",
        ],
        'dialect_swaps': {
            'tradie': 'construction professional',
            'tradies': 'construction professionals',
            'sparky': 'electrician',
            'sparkies': 'electricians',
            'subbie': 'subcontractor',
            'subbies': 'subcontractors',
            'smoko': 'break',
        },
        'soft_cta_options': [
            "Available now at https://sc-sk.com/. I'd really value feedback from Philippine construction teams.",
            "The Android app is here: https://play.google.com/store/apps/details?id=com.saa.scsk_app",
            "If it sounds useful for your site workflow, take a look at https://sc-sk.com/.",
        ],
        'closer_options': [
            "Happy to answer questions below.",
            "Admins — please remove if this type of post isn't allowed.",
            "Sharing for honest feedback from people working on real projects.",
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


def commit_image_to_repo(image_path):
    """
    Copy the image into the repo at digest_images/<filename> and commit via
    the GitHub Contents API. Returns a markdown image URL pointing at the
    committed file (renders inline in issue body), or (None, basename) on
    failure.

    Why not base64-embed: GitHub caps issue bodies at 65,536 chars. A 50KB
    image becomes ~70K base64 chars and blows the limit. Committing the file
    keeps the body small and the image rendering identical.
    """
    try:
        prepared = _prepare_image(image_path)
        with open(prepared, 'rb') as f:
            data = f.read()

        # Build the in-repo path: digest_images/2026-05-04_ad-3.png
        date_prefix = datetime.now().strftime('%Y-%m-%d')
        original_name = os.path.basename(image_path)
        repo_path = f"digest_images/{date_prefix}_{original_name}"
        size_kb = len(data) / 1024
        print(f"   📎 Committing image: {repo_path} ({size_kb:.0f}KB)")

        # GitHub Contents API: PUT /repos/{owner}/{repo}/contents/{path}
        b64 = base64.b64encode(data).decode('ascii')
        payload = {
            'message': f'Add digest image {repo_path} [skip ci]',
            'content': b64,
            'branch': 'main',
        }
        resp = gh_request('PUT', f'/repos/{GITHUB_REPO}/contents/{repo_path}',
                          json=payload)

        # Clean up temp file if we resized
        if prepared != str(image_path):
            try: os.unlink(prepared)
            except OSError: pass

        if resp.status_code in (200, 201):
            # The download_url in the response is the raw.githubusercontent.com URL
            # which renders inline in markdown.
            download_url = resp.json().get('content', {}).get('download_url')
            if download_url:
                print(f"   ✓ Image URL: {download_url}")
                return download_url, original_name
            print(f"   ⚠️  No download_url in response — image may not render")
            return None, original_name
        else:
            print(f"   ⚠️  Image commit failed: {resp.status_code}")
            print(f"   Response: {resp.text[:300]}")
            return None, original_name
    except Exception as e:
        print(f"   ⚠️  Image commit failed: {e}")
        return None, os.path.basename(image_path)


def _prepare_image(image_path):
    """Same resize logic — keeps committed images small."""
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
      - One section per configured market, each with search ideas and a
        copy-friendly code block
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
            f"![{image_name}]({image_md})",
            "",
            f"Direct download: {image_md}",
            "",
            "On mobile: long-press the image to save. On desktop: right-click → Save image.",
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
    for country_key, draft in country_drafts.items():
        config = COUNTRY_CONFIGS[country_key]
        emoji = MARKET_EMOJI.get(country_key, '🌍')
        search_queries = ' · '.join(
            f'`{query}`' for query in config['search_queries']
        )
        body_parts.extend([
            f"## {emoji} {config['name']} version",
            "",
            f"**Facebook group searches:** {search_queries}",
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
    ])

    for country_key in MARKET_ORDER:
        body_parts.append(
            f"- [ ] Posted to one approved {COUNTRY_CONFIGS[country_key]['name']} group"
        )

    body_parts.extend([
        "- [ ] Replied to first comment within 30 min",
        "- [ ] Closed this issue when done",
        "",
        "## 🛡️ Group posting reminders",
        "",
        "- Post only where the group's rules allow member or product posts.",
        "- Join as a genuine member and contribute before sharing your product.",
        "- Limit activity to one relevant group per market per day; quality beats volume.",
        "- Tailor at least one sentence to the group instead of pasting identical copy.",
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
    for country_key in MARKET_ORDER:
        country_drafts[country_key] = reword_for_country(source, country_key)
        print(f"   ✓ {country_key} version ({len(country_drafts[country_key])} chars)")

    # Pick & embed image
    print("\n📸 Selecting image...")
    image_path, image_name = pick_image_for_post(source)
    if image_path:
        print(f"   Selected: {image_name}")
        image_data = commit_image_to_repo(image_path)
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

    # GitHub caps issue bodies at 65,536 chars. With image as URL (not base64)
    # this is impossible to hit, but failsafe: trim if somehow exceeded.
    if len(issue_body) > 60000:
        print(f"   ⚠️  Body too long ({len(issue_body)} chars) — truncating to 60,000")
        issue_body = issue_body[:60000] + "\n\n_(truncated)_"

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
