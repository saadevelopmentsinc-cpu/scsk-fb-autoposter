#!/usr/bin/env python3
"""
SCSK Facebook Auto-Poster - LOCAL VERSION
Run this on your own computer with Windows Task Scheduler

Setup:
1. Install Python from python.org
2. Run: pip install requests
3. Edit the CONFIG section below with your credentials
4. Run: python fb_poster_local.py
5. Set up Windows Task Scheduler to run it hourly
"""

import os
import json
import csv
import requests
from datetime import datetime
import time
import sys

# =============================================================================
# CONFIG - EDIT THESE VALUES
# =============================================================================

# Get these from Facebook Developer Console (see SETUP-GUIDE.md)
PAGE_ACCESS_TOKEN = "YOUR_PAGE_ACCESS_TOKEN_HERE"
PAGE_ID = "YOUR_PAGE_ID_HERE"

# How many posts per run (when using --multi mode)
POSTS_PER_RUN = 3

# Minutes between posts (when using --multi mode)
MINUTES_BETWEEN = 20

# =============================================================================
# DO NOT EDIT BELOW THIS LINE
# =============================================================================

GRAPH_API_URL = f"https://graph.facebook.com/v18.0/{PAGE_ID}/feed"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONTENT_FILE = os.path.join(SCRIPT_DIR, "content.csv")
POSTED_LOG = os.path.join(SCRIPT_DIR, "posted.json")

def load_content():
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
    if os.path.exists(POSTED_LOG):
        with open(POSTED_LOG, 'r') as f:
            return json.load(f)
    return {'posted_ids': [], 'last_post_time': None}

def save_posted_log(log):
    with open(POSTED_LOG, 'w') as f:
        json.dump(log, f, indent=2)

def get_next_post(posts, posted_log):
    posted_ids = set(posted_log['posted_ids'])
    available = [p for p in posts if p['id'] not in posted_ids]
    
    if not available:
        print("All posts used! Resetting cycle...")
        posted_log['posted_ids'] = []
        save_posted_log(posted_log)
        available = posts
    
    return available[0] if available else None

def format_post(post):
    return f"{post['content']}\n\n{post['cta']}\n\n{post['hashtags']}"

def post_to_facebook(message):
    if PAGE_ACCESS_TOKEN == "YOUR_PAGE_ACCESS_TOKEN_HERE":
        print("ERROR: You need to edit the script and add your credentials!")
        print("Open fb_poster_local.py and edit the CONFIG section.")
        return False, "Missing credentials"
    
    payload = {
        'message': message,
        'access_token': PAGE_ACCESS_TOKEN
    }
    
    try:
        response = requests.post(GRAPH_API_URL, data=payload)
        result = response.json()
        
        if 'id' in result:
            print(f"✓ Posted successfully! Post ID: {result['id']}")
            return True, result['id']
        else:
            error = result.get('error', {}).get('message', 'Unknown error')
            print(f"✗ Failed: {error}")
            return False, error
    except Exception as e:
        print(f"✗ Exception: {str(e)}")
        return False, str(e)

def post_single():
    """Post a single piece of content."""
    print("=" * 50)
    print("SCSK Facebook Poster")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    posts = load_content()
    posted_log = load_posted_log()
    
    print(f"Total posts: {len(posts)} | Posted: {len(posted_log['posted_ids'])}")
    
    post = get_next_post(posts, posted_log)
    if not post:
        print("No posts available!")
        return
    
    message = format_post(post)
    print(f"\nPosting [{post['pillar']}] #{post['id']}")
    print("-" * 40)
    print(message[:150] + "..." if len(message) > 150 else message)
    print("-" * 40)
    
    success, result = post_to_facebook(message)
    
    if success:
        posted_log['posted_ids'].append(post['id'])
        posted_log['last_post_time'] = datetime.now().isoformat()
        save_posted_log(posted_log)
        print(f"✓ Done! ({len(posted_log['posted_ids'])}/{len(posts)} used)")

def post_multiple():
    """Post multiple times with delays."""
    print(f"Posting {POSTS_PER_RUN} posts with {MINUTES_BETWEEN} min gaps\n")
    
    for i in range(POSTS_PER_RUN):
        print(f"\n=== Post {i+1}/{POSTS_PER_RUN} ===")
        post_single()
        
        if i < POSTS_PER_RUN - 1:
            print(f"\nWaiting {MINUTES_BETWEEN} minutes...")
            time.sleep(MINUTES_BETWEEN * 60)
    
    print("\n✓ All posts complete!")

def show_status():
    """Show current status."""
    posts = load_content()
    posted_log = load_posted_log()
    
    print("=" * 50)
    print("SCSK Facebook Poster - Status")
    print("=" * 50)
    print(f"Total posts available: {len(posts)}")
    print(f"Posts used: {len(posted_log['posted_ids'])}")
    print(f"Posts remaining: {len(posts) - len(posted_log['posted_ids'])}")
    
    if posted_log['last_post_time']:
        print(f"Last posted: {posted_log['last_post_time']}")
    
    print("\nNext 3 posts:")
    posted_ids = set(posted_log['posted_ids'])
    available = [p for p in posts if p['id'] not in posted_ids][:3]
    for p in available:
        print(f"  [{p['pillar']}] {p['content'][:50]}...")

def reset_log():
    """Reset the posted log to start fresh."""
    save_posted_log({'posted_ids': [], 'last_post_time': None})
    print("✓ Posted log reset. All posts available again.")

def show_help():
    print("""
SCSK Facebook Auto-Poster - Local Version

Usage: python fb_poster_local.py [command]

Commands:
  (none)    Post a single piece of content
  --multi   Post multiple times with delays (configure in script)
  --status  Show what's been posted and what's next
  --reset   Reset posted log (start fresh)
  --help    Show this help

Setup:
  1. Edit this script and add your credentials in the CONFIG section
  2. Run: pip install requests
  3. Run: python fb_poster_local.py

Automation:
  Use Windows Task Scheduler to run this script hourly:
  1. Open Task Scheduler
  2. Create Basic Task
  3. Set trigger to hourly (or your preference)
  4. Action: Start a program
  5. Program: python (or path to python.exe)
  6. Arguments: "C:\\path\\to\\fb_poster_local.py"
""")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == '--multi':
            post_multiple()
        elif cmd == '--status':
            show_status()
        elif cmd == '--reset':
            reset_log()
        elif cmd == '--help':
            show_help()
        else:
            print(f"Unknown command: {cmd}")
            show_help()
    else:
        post_single()
