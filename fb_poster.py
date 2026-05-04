#!/usr/bin/env python3
"""
SCSK Facebook Auto-Poster - ENHANCED
Posts scheduled content to your Facebook Page automatically.
Designed to run via GitHub Actions (free tier).

Features:
- Random post formatting (avoids detection)
- Random emoji usage
- Random delays between requests
- User-Agent spoofing
- Manual trigger skip (no wait time)
- Image rotation every 3 posts
- Anti-throttling tactics
- Auto-resize oversized images (Facebook rejects >4MB)
"""

import os
import json
import csv
import requests
import time
import tempfile
from datetime import datetime, timedelta
import random

# Pillow is optional — if missing we fall back to uploading the original.
try:
    from PIL import Image
    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False

# =============================================================================
# CONFIGURATION
# =============================================================================

PAGE_ACCESS_TOKEN = os.environ.get('FB_PAGE_ACCESS_TOKEN')
PAGE_ID = os.environ.get('FB_PAGE_ID')

GRAPH_API_VERSION = "v21.0"
GRAPH_API_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{PAGE_ID}/feed"

CONTENT_FILE = "content.csv"
POSTED_LOG = "posted.json"

# Facebook /photos endpoint quirks:
#  - Hard cap is ~4MB even though docs say 10MB
#  - Max dimension 4096px on either axis
#  - Use generous safety margins
MAX_UPLOAD_BYTES = 3 * 1024 * 1024   # 3 MB target ceiling
MAX_DIMENSION = 1920                  # 1920px on the long edge
JPEG_QUALITY = 85                     # Good visual / size balance

# Construction-themed emojis
EMOJIS = ['🏗️', '👷', '🔨', '⚒️', '🛠️', '⚙️', '📐', '📏', '🧰', '🪛', '🪚', '🏢', '📋', '✅', '⭐', '💡', '🚀']

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def load_content():
    """Load content from CSV file."""
    posts = []
    with open(CONTENT_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            posts.append({
                'id': row['id'],
                'pillar': row['pillar'],
                'content': row['content'],
                'hashtags': row['hashtags'],
                'cta': row['cta']
            })
    return posts

def load_posted_log():
    """Load log of already posted content."""
    if os.path.exists(POSTED_LOG):
        with open(POSTED_LOG, 'r') as f:
            return json.load(f)
    return {'posted_ids': [], 'last_post_time': None}

def save_posted_log(log):
    """Save posted log."""
    with open(POSTED_LOG, 'w') as f:
        json.dump(log, f, indent=2)

def get_next_posts(posts, posted_log, count=1):
    """Get next posts that haven't been posted yet."""
    posted_ids = set(posted_log['posted_ids'])
    available = [p for p in posts if p['id'] not in posted_ids]

    if not available:
        print("All posts exhausted. Resetting cycle...")
        posted_log['posted_ids'] = []
        available = posts

    return available[:count]

def format_post(post):
    """Format post content with random variations."""
    content = post['content']
    hashtags = post['hashtags']
    cta = post['cta']

    # Randomly vary formatting
    variant = random.choice([1, 2, 3, 4, 5])

    if variant == 1:
        full_post = f"{content}\n\n{cta}\n\n{hashtags}"
    elif variant == 2:
        full_post = f"{hashtags}\n\n{content}\n\n{cta}"
    elif variant == 3:
        full_post = f"{content}\n\n{hashtags}\n\n{cta}"
    elif variant == 4:
        full_post = f"{content}\n\n\n{cta}\n\n{hashtags}"
    else:
        full_post = f"{content}\n{cta}\n{hashtags}"

    # Randomly add emoji (33% chance)
    if random.choice([True, False, False]):
        emoji = random.choice(EMOJIS)
        insert_pos = random.choice([0, -1])
        if insert_pos == 0:
            full_post = f"{emoji} {full_post}"
        else:
            full_post = f"{full_post} {emoji}"

    return full_post

def get_random_user_agent():
    """Return random User-Agent."""
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
        'Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15',
        'Mozilla/5.0 (iPad; CPU OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15',
    ]
    return random.choice(user_agents)

def add_random_delay():
    """Add random delay to appear human-like."""
    delay = random.uniform(0.5, 2.5)
    time.sleep(delay)

def should_post_now(posted_log, skip_wait=False):
    """Check if enough time has passed (random 107-158 minutes)."""
    if skip_wait or not posted_log['last_post_time']:
        return True, 0

    last_post = datetime.fromisoformat(posted_log['last_post_time'])
    minutes_since = (datetime.now() - last_post).total_seconds() / 60
    required_minutes = random.randint(107, 158)

    if minutes_since >= required_minutes:
        return True, 0
    else:
        return False, int(required_minutes - minutes_since)

def validate_token():
    """Quick check that the token is valid before attempting to post."""
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/me"
    resp = requests.get(url, params={'access_token': PAGE_ACCESS_TOKEN}, timeout=10)
    data = resp.json()
    if 'error' in data:
        msg = data['error'].get('message', 'Unknown error')
        print(f"❌ Token validation failed: {msg}")
        print("   → Go to developers.facebook.com/tools/explorer and generate a new Page access token.")
        return False
    print(f"✓ Token valid — posting as: {data.get('name', data.get('id', 'unknown'))}")
    return True

def _prepare_image(image_path):
    """
    Ensure an image is small enough for Facebook's /photos endpoint.

    Returns a path to either the original file (if already small) or a temp
    JPEG that has been downscaled and recompressed. The caller is responsible
    for cleaning up the temp file if it differs from the original.

    Strategy:
      1. If file is already <= MAX_UPLOAD_BYTES AND has small dimensions,
         return as-is (no rewrite).
      2. Otherwise downscale longest edge to MAX_DIMENSION and re-encode
         as JPEG q=85. If still too big, drop quality to 75, then 65.
    """
    if not _HAS_PIL:
        size_mb = os.path.getsize(image_path) / 1_048_576
        if size_mb > MAX_UPLOAD_BYTES / 1_048_576:
            print(f"⚠️  Pillow not installed — cannot resize {os.path.basename(image_path)} ({size_mb:.1f}MB).")
            print(f"    Install pillow in the workflow to fix oversized images.")
        return image_path

    try:
        original_size = os.path.getsize(image_path)
        with Image.open(image_path) as img:
            width, height = img.size
            needs_resize = max(width, height) > MAX_DIMENSION
            needs_recompress = original_size > MAX_UPLOAD_BYTES

            if not needs_resize and not needs_recompress:
                # Already fine — upload original
                return image_path

            print(f"   ↻ Resizing {os.path.basename(image_path)} "
                  f"({original_size / 1_048_576:.1f}MB, {width}x{height})")

            # Downscale if needed
            if needs_resize:
                ratio = MAX_DIMENSION / max(width, height)
                new_size = (int(width * ratio), int(height * ratio))
                img = img.resize(new_size, Image.LANCZOS)

            # Convert to RGB (JPEG can't handle alpha / paletted)
            if img.mode != 'RGB':
                img = img.convert('RGB')

            # Try progressively lower JPEG quality until we fit
            tmp = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
            tmp.close()
            for quality in (JPEG_QUALITY, 75, 65):
                img.save(tmp.name, 'JPEG', quality=quality, optimize=True)
                new_size = os.path.getsize(tmp.name)
                if new_size <= MAX_UPLOAD_BYTES:
                    print(f"   ✓ Resized to {new_size / 1_048_576:.2f}MB at q={quality}")
                    return tmp.name
            # Even q=65 didn't fit — return whatever we got, log warning.
            print(f"   ⚠️  Even at q=65 image is {new_size / 1_048_576:.2f}MB — uploading anyway.")
            return tmp.name

    except Exception as e:
        print(f"   ⚠️  Image resize failed ({e}) — uploading original.")
        return image_path

def post_to_facebook(message, image_path=None):
    """Post message to Facebook Page with optional image."""
    if not PAGE_ACCESS_TOKEN or not PAGE_ID:
        print("ERROR: Missing FB_PAGE_ACCESS_TOKEN or FB_PAGE_ID")
        print("Set these as GitHub Secrets: Settings → Secrets → Actions")
        return False, "Missing credentials"

    add_random_delay()

    headers = {
        'User-Agent': get_random_user_agent(),
        'Accept': 'application/json',
    }

    # Track temp file so we can clean it up after upload
    upload_path = None
    cleanup_path = None

    try:
        add_random_delay()

        if image_path and os.path.exists(image_path):
            print(f"📸 Attaching image: {os.path.basename(image_path)}")

            # Resize if needed (returns either original path or a temp jpg)
            upload_path = _prepare_image(image_path)
            if upload_path != image_path:
                cleanup_path = upload_path  # mark temp for cleanup later

            photo_url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{PAGE_ID}/photos"

            with open(upload_path, 'rb') as f:
                files = {'source': f}
                data = {
                    'message': message,
                    'access_token': PAGE_ACCESS_TOKEN
                }
                response = requests.post(photo_url, files=files, data=data, headers=headers, timeout=60)
        else:
            payload = {
                'message': message,
                'access_token': PAGE_ACCESS_TOKEN
            }
            response = requests.post(GRAPH_API_URL, data=payload, headers=headers, timeout=30)

        print(f"HTTP Status: {response.status_code}")
        result = response.json()

        if 'id' in result or 'post_id' in result:
            post_id = result.get('id') or result.get('post_id')
            print(f"✓ Posted successfully! Post ID: {post_id}")
            return True, post_id
        else:
            error_data = result.get('error', {})
            error_msg = error_data.get('message', 'Unknown error')
            error_code = error_data.get('code', 'N/A')
            error_subcode = error_data.get('error_subcode', 'N/A')
            print(f"✗ Failed to post:")
            print(f"   Code: {error_code} / Subcode: {error_subcode}")
            print(f"   Message: {error_msg}")
            print(f"   Full response: {result}")
            return False, error_msg

    except Exception as e:
        print(f"✗ Exception: {str(e)}")
        return False, str(e)
    finally:
        # Clean up temp resized file if we created one
        if cleanup_path and os.path.exists(cleanup_path):
            try:
                os.unlink(cleanup_path)
            except OSError:
                pass

# =============================================================================
# MAIN EXECUTION
# =============================================================================

def main():
    """Main execution - posts one piece of content."""
    print("=" * 50)
    print("SCSK Facebook Auto-Poster (Enhanced)")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"API:  Graph API {GRAPH_API_VERSION}")
    print(f"PIL:  {'available' if _HAS_PIL else 'NOT installed (large images may fail)'}")
    print("=" * 50)

    # Validate token before doing anything else
    if not validate_token():
        exit(1)

    # Load content and posting log
    posts = load_content()
    posted_log = load_posted_log()

    print(f"Total posts available: {len(posts)}")
    print(f"Already posted: {len(posted_log['posted_ids'])}")

    # Check if manual trigger (skip wait time)
    event_name = os.environ.get('GITHUB_EVENT_NAME', 'schedule')
    skip_wait = event_name == 'workflow_dispatch'

    if skip_wait:
        print("\n🚀 MANUAL TRIGGER - Skipping wait time!")

    # Check if enough time has passed
    should_post, wait_minutes = should_post_now(posted_log, skip_wait=skip_wait)
    if not should_post:
        print(f"\nNot time to post yet. Wait {wait_minutes} more minutes.")
        if posted_log['last_post_time']:
            print(f"Last post: {posted_log['last_post_time']}")
        return

    # Get next post
    next_posts = get_next_posts(posts, posted_log, count=1)

    if not next_posts:
        print("No posts available!")
        return

    post = next_posts[0]
    message = format_post(post)

    # Debug info
    remaining = len(posts) - len(posted_log['posted_ids'])
    print(f"\nPosting [{post['pillar']}] - ID: {post['id']}")
    print(f"Progress: {len(posted_log['posted_ids']) + 1}/{len(posts)} posts")
    print(f"Remaining: {remaining - 1}")
    print("-" * 40)
    print(message[:200] + "..." if len(message) > 200 else message)
    print("-" * 40)

    # Attach image with EVERY post
    # Every 3rd post: Screenshot1.jpg
    # Other posts: Random from ad-1 to ad-10
    image_path = None
    posts_count = len(posted_log['posted_ids'])

    if (posts_count + 1) % 3 == 0:
        selected_image = 'Screenshot1.jpg'
        print(f"📸 Adding featured image: {selected_image}")
    else:
        ad_images = ['ad-1.png', 'ad-2.png', 'ad-3.png', 'ad-4.png', 'ad-5.png',
                     'ad-6.png', 'ad-7.png', 'ad-8.png', 'ad-9.png', 'ad-10.png']
        selected_image = random.choice(ad_images)
        print(f"📸 Adding random ad image: {selected_image}")

    image_path = os.path.join(os.path.dirname(__file__), 'images', selected_image)
    if not os.path.exists(image_path):
        print(f"⚠️  Image not found: images/{selected_image}")
        image_path = None

    # Post to Facebook
    success, result = post_to_facebook(message, image_path=image_path)

    if success:
        posted_log['posted_ids'].append(post['id'])
        posted_log['last_post_time'] = datetime.now().isoformat()
        posted_log['last_post_id'] = result
        save_posted_log(posted_log)
        print(f"\n✓ Log updated. Total posted: {len(posted_log['posted_ids'])}")
    else:
        print(f"\n✗ Post failed: {result}")
        exit(1)

def batch_post(count=5, delay_minutes=30):
    """Post multiple times with delays."""
    print(f"Batch posting {count} posts with {delay_minutes} min delays\n")

    for i in range(count):
        print(f"\n--- Post {i+1}/{count} ---")
        main()

        if i < count - 1:
            actual_delay = delay_minutes + random.randint(-15, 15)
            print(f"Waiting {actual_delay} minutes...")
            time.sleep(actual_delay * 60)

def test_mode():
    """Test without actually posting."""
    print("=" * 50)
    print("TEST MODE - No actual posting")
    print("=" * 50)

    posts = load_content()
    posted_log = load_posted_log()

    print(f"Total posts: {len(posts)}")
    print(f"Already posted: {len(posted_log['posted_ids'])}")

    next_posts = get_next_posts(posts, posted_log, count=3)

    print(f"\nNext {len(next_posts)} posts would be:")
    for i, post in enumerate(next_posts, 1):
        print(f"\n--- Post {i} [{post['pillar']}] ---")
        print(format_post(post)[:300] + "...")

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] == 'test':
            test_mode()
        elif sys.argv[1] == 'batch':
            count = int(sys.argv[2]) if len(sys.argv) > 2 else 5
            batch_post(count=count)
    else:
        main()
