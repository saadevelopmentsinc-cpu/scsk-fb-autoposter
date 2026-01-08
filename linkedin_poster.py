#!/usr/bin/env python3
"""
SCSK LinkedIn Auto-Poster
Posts scheduled content to your LinkedIn Page automatically.
Mirrors Facebook posting - same content, same order.
"""

import os
import json
import csv
import requests
from datetime import datetime
import random
import time

# =============================================================================
# CONFIGURATION
# =============================================================================

# These are set as GitHub Secrets (or environment variables)
LINKEDIN_ACCESS_TOKEN = os.environ.get('LINKEDIN_ACCESS_TOKEN')

# User ID will be fetched automatically from the token

# Random delay settings (in seconds)
MIN_RANDOM_DELAY = 0
MAX_RANDOM_DELAY = 420  # 7 minutes in seconds

# LinkedIn API endpoint
LINKEDIN_API_URL = "https://api.linkedin.com/v2/ugcPosts"

# Image settings
IMAGE_BASE_URL = "https://raw.githubusercontent.com/saadevelopmentsinc-cpu/scsk-fb-autoposter/main/images/"
IMAGE_EXTENSION = ".png"
RANDOM_IMAGE_COUNT = 9   # Random images (ad-1 through ad-9)
FEATURED_IMAGE = 10      # ad-10 appears every 3rd post
FEATURED_EVERY = 3       # Show featured image every X posts

# Path to content file
CONTENT_FILE = "content.csv"
POSTED_LOG = "posted_linkedin.json"  # Separate log for LinkedIn

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
    """Format post content for LinkedIn."""
    content = post['content']
    hashtags = post['hashtags']
    cta = post['cta']
    
    # Combine content with hashtags and CTA
    full_post = f"{content}\n\n{cta}\n\n{hashtags}"
    
    return full_post

def get_image_url(post_number):
    """Get image URL based on post number. ad-10 every 3rd post, random otherwise."""
    if post_number % FEATURED_EVERY == 0:
        image_num = FEATURED_IMAGE
        print(f"📷 Using FEATURED image: ad-{image_num}{IMAGE_EXTENSION} (every {FEATURED_EVERY}rd post)")
    else:
        image_num = random.randint(1, RANDOM_IMAGE_COUNT)
        print(f"📷 Using random image: ad-{image_num}{IMAGE_EXTENSION}")
    
    return f"{IMAGE_BASE_URL}ad-{image_num}{IMAGE_EXTENSION}"

def register_image_upload(image_url):
    """Register an image upload with LinkedIn (required for image posts)."""
    # For URL-based images, LinkedIn requires registering the upload first
    # This is complex - for now we'll do text-only posts
    # LinkedIn's image API requires multi-step upload process
    return None

def get_user_id():
    """Fetch the user's LinkedIn ID from the access token."""
    headers = {
        'Authorization': f'Bearer {LINKEDIN_ACCESS_TOKEN}',
    }
    
    try:
        # Try userinfo endpoint first
        response = requests.get('https://api.linkedin.com/v2/userinfo', headers=headers)
        if response.status_code == 200:
            data = response.json()
            user_id = data.get('sub')
            if user_id:
                print(f"✓ Found User ID: {user_id}")
                return user_id
        
        # Fallback to /me endpoint
        response = requests.get('https://api.linkedin.com/v2/me', headers=headers)
        if response.status_code == 200:
            data = response.json()
            user_id = data.get('id')
            if user_id:
                print(f"✓ Found User ID: {user_id}")
                return user_id
        
        print(f"✗ Could not fetch User ID. Status: {response.status_code}")
        print(f"  Response: {response.text[:200]}")
        return None
        
    except Exception as e:
        print(f"✗ Exception fetching User ID: {str(e)}")
        return None

def post_to_linkedin(message, post_number):
    """Post message to LinkedIn personal profile."""
    if not LINKEDIN_ACCESS_TOKEN:
        print("ERROR: Missing LINKEDIN_ACCESS_TOKEN")
        print("Set this as environment variable or GitHub Secret")
        return False, "Missing credentials"
    
    # Get user ID from token
    user_id = get_user_id()
    if not user_id:
        return False, "Could not fetch User ID"
    
    headers = {
        'Authorization': f'Bearer {LINKEDIN_ACCESS_TOKEN}',
        'Content-Type': 'application/json',
        'X-Restli-Protocol-Version': '2.0.0'
    }
    
    # LinkedIn post payload for personal profile
    payload = {
        "author": f"urn:li:person:{user_id}",
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {
                    "text": message
                },
                "shareMediaCategory": "NONE"
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
        }
    }
    
    try:
        response = requests.post(LINKEDIN_API_URL, headers=headers, json=payload)
        
        if response.status_code == 201:
            result = response.json()
            post_id = result.get('id', 'unknown')
            print(f"✓ Posted successfully! Post ID: {post_id}")
            return True, post_id
        else:
            error = response.json().get('message', response.text)
            print(f"✗ Failed to post: {error}")
            print(f"  Status code: {response.status_code}")
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
    print("SCSK LinkedIn Auto-Poster")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    # Add random delay for natural posting intervals
    # Skip delay if triggered manually (workflow_dispatch)
    if os.environ.get('GITHUB_ACTIONS') and os.environ.get('GITHUB_EVENT_NAME') != 'workflow_dispatch':
        delay = random.randint(MIN_RANDOM_DELAY, MAX_RANDOM_DELAY)
        print(f"Random delay: {delay // 60}m {delay % 60}s")
        time.sleep(delay)
        print(f"Posting at: {datetime.now().strftime('%H:%M:%S')}")
    else:
        print("Manual run - skipping delay")
    
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
    
    # Post to LinkedIn
    post_number = len(posted_log['posted_ids']) + 1
    success, result = post_to_linkedin(message, post_number)
    
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
    else:
        main()
