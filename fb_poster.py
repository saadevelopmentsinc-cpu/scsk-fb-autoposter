#!/usr/bin/env python3
"""
SCSK Facebook Auto-Poster - ENHANCED VERSION
Posts scheduled content to your Facebook Page automatically.
Designed to run via GitHub Actions (free tier).

Anti-Throttling Features:
- Random post formatting (line breaks, spacing)
- Randomized delays between API calls
- Variable hashtag placement
- Random emoji usage (construction-themed)
- Content variation
- User-Agent spoofing
- Staggered posting times (not exact hour marks)
"""

import os
import json
import csv
import requests
import random
import time
from datetime import datetime, timedelta

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

def format_post_variant(post):
    """Format post content with randomized variations to avoid detection."""
    content = post['content']
    hashtags = post['hashtags']
    cta = post['cta']
    
    # Randomly decide content ordering to avoid pattern detection
    variant = random.choice([1, 2, 3, 4, 5])
    
    if variant == 1:
        # Classic format
        full_post = f"{content}\n\n{cta}\n\n{hashtags}"
    elif variant == 2:
        # Hashtags first (less common = looks less bot-like)
        full_post = f"{hashtags}\n\n{content}\n\n{cta}"
    elif variant == 3:
        # CTA in middle
        full_post = f"{content}\n\n{hashtags}\n\n{cta}"
    elif variant == 4:
        # Extra spacing (humans often do this)
        full_post = f"{content}\n\n\n{cta}\n\n{hashtags}"
    else:
        # Minimal spacing (another human variation)
        full_post = f"{content}\n{cta}\n{hashtags}"
    
    # Randomly add an emoji (humans often do this, bots less commonly)
    if random.choice([True, False, False]):  # 33% chance
        emoji = random.choice(EMOJIS)
        insert_pos = random.choice([0, -1])  # Start or end
        if insert_pos == 0:
            full_post = f"{emoji} {full_post}"
        else:
            full_post = f"{full_post} {emoji}"
    
    return full_post

def get_random_user_agent():
    """Return a random User-Agent to avoid detection."""
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
        'Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15',
        'Mozilla/5.0 (iPad; CPU OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15',
    ]
    return random.choice(user_agents)

def add_random_delay():
    """Add a random delay to appear more human-like."""
    delay = random.uniform(0.5, 2.5)  # 0.5 to 2.5 seconds
    time.sleep(delay)

def post_to_facebook(message, image_path=None):
    """Post message to Facebook Page with optional image attachment."""
    if not PAGE_ACCESS_TOKEN or not PAGE_ID:
        print("ERROR: Missing FB_PAGE_ACCESS_TOKEN or FB_PAGE_ID")
        return False, "Missing credentials"
    
    # Add random delay to avoid consistent timing patterns
    add_random_delay()
    
    payload = {
        'message': message,
        'access_token': PAGE_ACCESS_TOKEN
    }
    
    # Add headers to look more like a real request
    headers = {
        'User-Agent': get_random_user_agent(),
        'Accept': 'application/json',
    }
    
    try:
        # Add random delay before request
        add_random_delay()
        
        # Handle image attachment if provided
        if image_path and os.path.exists(image_path):
            print(f"Attaching image: {image_path}")
            with open(image_path, 'rb') as f:
                files = {'source': f}
                response = requests.post(GRAPH_API_URL, data=payload, files=files, headers=headers, timeout=30)
        else:
            response = requests.post(GRAPH_API_URL, data=payload, headers=headers, timeout=30)
        
        result = response.json()
        
        if 'id' in result:
            print(f"✓ Posted successfully! Post ID: {result['id']}")
            return True, result['id']
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

def should_post_now(posted_log, skip_wait=False):
    """
    Check if enough time has passed since last post.
    Random interval between 107-158 minutes (1h47m to 2h38m).
    
    Args:
        posted_log: The log of posted content
        skip_wait: If True (manual trigger), skip the wait check and post immediately
    
    Returns:
        (should_post: bool, minutes_until_next: int)
    """
    # Skip wait check if manually triggered
    if skip_wait:
        return True, 0
    
    if not posted_log['last_post_time']:
        # First post, always post
        return True, 0
    
    last_post = datetime.fromisoformat(posted_log['last_post_time'])
    now = datetime.now()
    minutes_since = (now - last_post).total_seconds() / 60
    
    # Random interval: 107-158 minutes (1h47m to 2h38m)
    required_minutes = random.randint(107, 158)
    
    if minutes_since >= required_minutes:
        return True, 0
    else:
        minutes_until = int(required_minutes - minutes_since)
        return False, minutes_until

def main():
    """Main execution - posts one piece of content with variations."""
    print("=" * 50)
    print("SCSK Facebook Auto-Poster (Enhanced)")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    # Load content and posting log
    posts = load_content()
    posted_log = load_posted_log()
    
    print(f"Total posts available: {len(posts)}")
    print(f"Already posted: {len(posted_log['posted_ids'])}")
    
    # Check if this is a manual trigger (workflow_dispatch)
    # GitHub Actions sets GITHUB_EVENT_NAME env var
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
    message = format_post_variant(post)  # Use variant formatting
    
    print(f"\nPosting [{post['pillar']}] - ID: {post['id']}")
    print("-" * 40)
    print(message[:200] + "..." if len(message) > 200 else message)
    print("-" * 40)
    
    # Post to Facebook
    # Attach image every 3 posts (posts 3, 6, 9, etc.) - rotates through 11 images
    image_path = None
    posts_count = len(posted_log['posted_ids'])
    
    if (posts_count + 1) % 3 == 0:  # Every 3rd post
        # Rotate through 11 images in the images/ folder
        image_files = [
            'ad-1.png', 'ad-2.png', 'ad-3.png', 'ad-4.png', 'ad-5.png',
            'ad-6.png', 'ad-7.png', 'ad-8.png', 'ad-9.png', 'ad-10.png',
            'Screenshot1.jpg'
        ]
        
        # Calculate which image to use (cycles through the list)
        image_index = (posts_count // 3) % len(image_files)
        selected_image = image_files[image_index]
        
        # Look for images in the images/ folder
        image_path = os.path.join(os.path.dirname(__file__), 'images', selected_image)
        if os.path.exists(image_path):
            print(f"📸 Adding image ({image_index + 1}/11): {selected_image}")
        else:
            print(f"⚠️  Image not found: images/{selected_image}")
            image_path = None
    
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
    """Post multiple times with randomized delays."""
    import time
    
    print(f"Batch posting {count} posts with variable delays\n")
    
    for i in range(count):
        print(f"\n--- Post {i+1}/{count} ---")
        main()
        
        if i < count - 1:
            # Randomize delay between posts (15-45 minutes if base is 30)
            actual_delay = delay_minutes + random.randint(-15, 15)
            print(f"Waiting {actual_delay} minutes before next post...")
            time.sleep(actual_delay * 60)

def test_mode():
    """Test without actually posting."""
    print("=" * 50)
    print("TEST MODE - Showing formatted posts (no posting)")
    print("=" * 50)
    
    posts = load_content()
    posted_log = load_posted_log()
    
    print(f"Total posts: {len(posts)}")
    print(f"Already posted: {len(posted_log['posted_ids'])}")
    
    next_posts = get_next_posts(posts, posted_log, count=3)
    
    print(f"\nNext {len(next_posts)} posts (with random formatting):\n")
    for i, post in enumerate(next_posts, 1):
        print(f"--- Variant {i} ---")
        print(format_post_variant(post))
        print()

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
