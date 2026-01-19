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
"""

import os
import json
import csv
import requests
import time
from datetime import datetime, timedelta
import random

# =============================================================================
# CONFIGURATION
# =============================================================================

PAGE_ACCESS_TOKEN = os.environ.get('FB_PAGE_ACCESS_TOKEN')
PAGE_ID = os.environ.get('FB_PAGE_ID')

GRAPH_API_URL = f"https://graph.facebook.com/v18.0/{PAGE_ID}/feed"

CONTENT_FILE = "content.csv"
POSTED_LOG = "posted.json"

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

def post_to_facebook(message, image_path=None):
    """Post message to Facebook Page with optional image."""
    if not PAGE_ACCESS_TOKEN or not PAGE_ID:
        print("ERROR: Missing FB_PAGE_ACCESS_TOKEN or FB_PAGE_ID")
        print("Set these as environment variables or GitHub Secrets")
        return False, "Missing credentials"
    
    add_random_delay()
    
    headers = {
        'User-Agent': get_random_user_agent(),
        'Accept': 'application/json',
    }
    
    try:
        add_random_delay()
        
        # If image provided, post as photo (different endpoint)
        if image_path and os.path.exists(image_path):
            print(f"📸 Attaching image: {os.path.basename(image_path)}")
            
            # Use photos endpoint for image posts
            photo_url = f"https://graph.facebook.com/v18.0/{PAGE_ID}/photos"
            
            with open(image_path, 'rb') as f:
                files = {'source': f}
                data = {
                    'message': message,
                    'access_token': PAGE_ACCESS_TOKEN
                }
                response = requests.post(photo_url, files=files, data=data, headers=headers, timeout=30)
        else:
            # Text-only post
            payload = {
                'message': message,
                'access_token': PAGE_ACCESS_TOKEN
            }
            response = requests.post(GRAPH_API_URL, data=payload, headers=headers, timeout=30)
        
        result = response.json()
        
        if 'id' in result or 'post_id' in result:
            post_id = result.get('id') or result.get('post_id')
            print(f"✓ Posted successfully! Post ID: {post_id}")
            return True, post_id
        else:
            error = result.get('error', {}).get('message', 'Unknown error')
            print(f"✗ Failed to post: {error}")
            return False, error
            
    except Exception as e:
        print(f"✗ Exception: {str(e)}")
        return False, str(e)

# =============================================================================
# MAIN EXECUTION
# =============================================================================

def main():
    """Main execution - posts one piece of content."""
    print("=" * 50)
    print("SCSK Facebook Auto-Poster (Enhanced)")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
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
    
    if (posts_count + 1) % 3 == 0:  # Every 3rd post
        selected_image = 'Screenshot1.jpg'
        print(f"📸 Adding featured image: {selected_image}")
    else:
        # Random ad image
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
        # Update log
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
