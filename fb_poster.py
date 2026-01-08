#!/usr/bin/env python3
"""
SCSK Facebook Auto-Poster
Posts scheduled content to your Facebook Page automatically.
Designed to run via GitHub Actions (free tier).
"""

import os
import json
import csv
import requests
from datetime import datetime, timedelta
import random
import time

# =============================================================================
# CONFIGURATION
# =============================================================================

# These are set as GitHub Secrets (or environment variables)
PAGE_ACCESS_TOKEN = os.environ.get('FB_PAGE_ACCESS_TOKEN')
PAGE_ID = os.environ.get('FB_PAGE_ID')

# Random delay settings (in seconds)
# Workflow runs every 25 min, we add 0-7 min random delay = 25-32 min effective interval
MIN_RANDOM_DELAY = 0
MAX_RANDOM_DELAY = 420  # 7 minutes in seconds

# Facebook Graph API endpoints
GRAPH_API_URL = f"https://graph.facebook.com/v18.0/{PAGE_ID}/feed"
GRAPH_API_PHOTOS_URL = f"https://graph.facebook.com/v18.0/{PAGE_ID}/photos"

# Image URLs - UPDATE THIS to your actual image location
IMAGE_BASE_URL = "https://raw.githubusercontent.com/saadevelopmentsinc-cpu/scsk-fb-autoposter/main/images/ad-"
IMAGE_EXTENSION = ".png"  # Change to .png if your files are PNG

# Image rotation: ad-10 every 3rd post, random 1-9 otherwise
RANDOM_IMAGE_COUNT = 9   # Random images (ad-1 through ad-9)
FEATURED_IMAGE = 10      # ad-10 appears every 3rd post
FEATURED_EVERY = 3       # Show featured image every X posts

# Path to content file
CONTENT_FILE = "content.csv"
POSTED_LOG = "posted.json"

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
    """Get next posts that haven't been posted yet. Cycles back to start when done."""
    posted_ids = set(posted_log['posted_ids'])
    available = [p for p in posts if p['id'] not in posted_ids]
    
    if not available:
        # All posts have been used, reset and start from beginning
        print("=" * 50)
        print("🔄 ALL POSTS COMPLETE! Starting fresh cycle...")
        print("=" * 50)
        posted_log['posted_ids'] = []
        save_posted_log(posted_log)
        available = posts
    
    return available[:count]

def format_post(post):
    """Format post content for Facebook."""
    content = post['content']
    hashtags = post['hashtags']
    cta = post['cta']
    
    # Combine content with hashtags and CTA
    full_post = f"{content}\n\n{cta}\n\n{hashtags}"
    
    return full_post

def post_to_facebook(message, post_number):
    """Post message with image to Facebook Page. ad-10 every 3rd post, random otherwise."""
    if not PAGE_ACCESS_TOKEN or not PAGE_ID:
        print("ERROR: Missing FB_PAGE_ACCESS_TOKEN or FB_PAGE_ID")
        print("Set these as environment variables or GitHub Secrets")
        return False, "Missing credentials"
    
    # Pick image: ad-10 every 3rd post, random 1-9 otherwise
    if post_number % FEATURED_EVERY == 0:
        image_num = FEATURED_IMAGE
        print(f"📷 Using FEATURED image: ad-{image_num}{IMAGE_EXTENSION} (every {FEATURED_EVERY}rd post)")
    else:
        image_num = random.randint(1, RANDOM_IMAGE_COUNT)
        print(f"📷 Using random image: ad-{image_num}{IMAGE_EXTENSION}")
    
    image_url = f"{IMAGE_BASE_URL}{image_num}{IMAGE_EXTENSION}"
    print(f"   URL: {image_url}")
    
    # Post as photo with caption (message becomes the caption)
    payload = {
        'caption': message,
        'url': image_url,
        'access_token': PAGE_ACCESS_TOKEN
    }
    
    try:
        response = requests.post(GRAPH_API_PHOTOS_URL, data=payload)
        result = response.json()
        
        if 'id' in result:
            print(f"✓ Posted successfully! Post ID: {result['id']}")
            return True, result['id']
        else:
            error = result.get('error', {}).get('message', 'Unknown error')
            print(f"✗ Failed to post: {error}")
            
            # Fallback: try posting without image
            print("Attempting text-only fallback...")
            return post_to_facebook_text_only(message)
            
    except Exception as e:
        print(f"✗ Exception: {str(e)}")
        return False, str(e)

def post_to_facebook_text_only(message):
    """Fallback: Post message without image."""
    payload = {
        'message': message,
        'access_token': PAGE_ACCESS_TOKEN
    }
    
    try:
        response = requests.post(GRAPH_API_URL, data=payload)
        result = response.json()
        
        if 'id' in result:
            print(f"✓ Posted (text-only) successfully! Post ID: {result['id']}")
            return True, result['id']
        else:
            error = result.get('error', {}).get('message', 'Unknown error')
            print(f"✗ Text-only also failed: {error}")
            return False, error
            
    except Exception as e:
        print(f"✗ Exception: {str(e)}")
        return False, str(e)

def post_to_facebook_scheduled(message, scheduled_time):
    """Schedule a post for later (requires additional permissions)."""
    if not PAGE_ACCESS_TOKEN or not PAGE_ID:
        return False, "Missing credentials"
    
    # Convert to Unix timestamp
    timestamp = int(scheduled_time.timestamp())
    
    payload = {
        'message': message,
        'published': 'false',
        'scheduled_publish_time': timestamp,
        'access_token': PAGE_ACCESS_TOKEN
    }
    
    try:
        response = requests.post(GRAPH_API_URL, data=payload)
        result = response.json()
        
        if 'id' in result:
            print(f"✓ Scheduled for {scheduled_time}! Post ID: {result['id']}")
            return True, result['id']
        else:
            error = result.get('error', {}).get('message', 'Unknown error')
            print(f"✗ Failed to schedule: {error}")
            return False, error
            
    except Exception as e:
        return False, str(e)

# =============================================================================
# MAIN EXECUTION
# =============================================================================

def main():
    """Main execution - posts one piece of content."""
    print("=" * 50)
    print("SCSK Facebook Auto-Poster")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    # Add random delay for natural posting intervals (25-32 min effective)
    if os.environ.get('GITHUB_ACTIONS'):  # Only delay in GitHub Actions
        delay = random.randint(MIN_RANDOM_DELAY, MAX_RANDOM_DELAY)
        print(f"Random delay: {delay // 60}m {delay % 60}s")
        time.sleep(delay)
        print(f"Posting at: {datetime.now().strftime('%H:%M:%S')}")
    
    # Load content and posting log
    posts = load_content()
    posted_log = load_posted_log()
    
    print(f"Total posts available: {len(posts)}")
    print(f"Already posted: {len(posted_log['posted_ids'])}")
    
    # Get next post
    next_posts = get_next_posts(posts, posted_log, count=1)
    
    if not next_posts:
        print("No posts available!")
        return
    
    post = next_posts[0]
    message = format_post(post)
    
    print(f"\nPosting [{post['pillar']}] - ID: {post['id']}")
    print("-" * 40)
    print(message[:200] + "..." if len(message) > 200 else message)
    print("-" * 40)
    
    # Post to Facebook (pass post number for image rotation)
    post_number = len(posted_log['posted_ids']) + 1
    success, result = post_to_facebook(message, post_number)
    
    if success:
        # Update log
        posted_log['posted_ids'].append(post['id'])
        posted_log['last_post_time'] = datetime.now().isoformat()
        posted_log['last_post_id'] = result
        save_posted_log(posted_log)
        print(f"\n✓ Log updated. Total posted: {len(posted_log['posted_ids'])}")
    else:
        print(f"\n✗ Post failed: {result}")
        # Exit with error code for GitHub Actions
        exit(1)

def batch_post(count=5, delay_minutes=30):
    """Post multiple times with delays (for local running)."""
    import time
    
    print(f"Batch posting {count} posts with {delay_minutes} min delays")
    
    for i in range(count):
        print(f"\n--- Post {i+1}/{count} ---")
        main()
        
        if i < count - 1:
            print(f"Waiting {delay_minutes} minutes...")
            time.sleep(delay_minutes * 60)

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
