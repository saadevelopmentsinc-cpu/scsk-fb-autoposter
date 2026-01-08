# SCSK Facebook Auto-Poster Setup Guide

**Zero cost. Fully automated. Posts to your Facebook Page on autopilot.**

---

## Overview

This system automatically posts to your Facebook Page using:
- **GitHub Actions** (free tier: 2000 minutes/month = plenty)
- **Facebook Graph API** (free)
- **Python** (free)

Once set up, it runs completely hands-free.

---

## What You Need

1. A **Facebook Page** (not a personal profile)
2. A **GitHub account** (free)
3. About **30 minutes** for initial setup

---

## Step 1: Create a Facebook Page (Skip if you have one)

1. Go to [facebook.com/pages/create](https://www.facebook.com/pages/create)
2. Choose **Business or Brand**
3. Enter:
   - Page Name: `SCSK - Site Companion Side Kick`
   - Category: `Software` or `App`
4. Complete the setup
5. **Note your Page name** - you'll need it later

---

## Step 2: Create a Facebook App

This gives you API access to post to your Page.

### 2.1 Go to Facebook Developers

1. Go to [developers.facebook.com](https://developers.facebook.com/)
2. Click **Log In** (use your Facebook account)
3. If first time, click **Get Started** and complete registration

### 2.2 Create New App

1. Click **My Apps** (top right)
2. Click **Create App**
3. Select **Business** as the app type
4. Click **Next**
5. Enter:
   - App Name: `SCSK Auto Poster`
   - App Contact Email: your email
6. Click **Create App**

### 2.3 Add Facebook Login Product

1. On your app dashboard, find **Add Products to Your App**
2. Click **Set Up** on **Facebook Login**
3. Choose **Web**
4. For Site URL, enter: `https://localhost/`
5. Click **Save** and **Continue**
6. Keep clicking **Next** through the quickstart (we don't need it)

---

## Step 3: Get Your Page Access Token

This is the key that lets the script post to your Page.

### 3.1 Open Graph API Explorer

1. Go to [developers.facebook.com/tools/explorer](https://developers.facebook.com/tools/explorer/)
2. In the top right, select your app: `SCSK Auto Poster`

### 3.2 Get User Token First

1. Click **Generate Access Token** button
2. A popup asks for permissions. Make sure these are checked:
   - `pages_show_list`
   - `pages_read_engagement`
   - `pages_manage_posts`
3. Click **Continue** and then **OK** to approve

### 3.3 Get Page Access Token

1. In the Graph API Explorer, look at the dropdown that says "User Token"
2. Click it and select **Get Page Access Token**
3. Select your Page from the list
4. A new token appears in the Access Token field
5. **Copy this token** - you'll need it for GitHub

### 3.4 Extend Token to Long-Lived (Important!)

The token above expires in 1 hour. We need a long-lived one (60 days).

1. Go to [developers.facebook.com/tools/debug/accesstoken](https://developers.facebook.com/tools/debug/accesstoken/)
2. Paste your Page Access Token
3. Click **Debug**
4. Look at **Expires** - it probably says "about an hour"
5. Click **Extend Access Token** at the bottom
6. Copy the new extended token
7. Debug it again to confirm it now shows ~60 days expiry

**Note:** You'll need to refresh this token every ~60 days. Set a calendar reminder!

---

## Step 4: Get Your Page ID

1. Go to your Facebook Page
2. Click **About** (or look in Page settings)
3. Scroll down to find **Page ID** (a long number like `123456789012345`)
4. **Copy this number**

OR use Graph API Explorer:
1. With your Page token selected, enter `/me` in the query field
2. Click **Submit**
3. The response shows your Page ID

---

## Step 5: Create GitHub Repository

### 5.1 Create New Repository

1. Go to [github.com/new](https://github.com/new)
2. Repository name: `scsk-fb-autoposter`
3. Set to **Private** (keep your tokens secret!)
4. Check **Add a README file**
5. Click **Create Repository**

### 5.2 Upload Files

Upload these files to your repository:

```
scsk-fb-autoposter/
├── .github/
│   └── workflows/
│       └── facebook-poster.yml
├── fb_poster.py
├── content.csv
├── posted.json
└── README.md
```

**To upload:**
1. Click **Add file** → **Upload files**
2. Drag all the files from the `fb-autoposter` folder
3. Click **Commit changes**

For the `.github` folder:
1. Click **Add file** → **Create new file**
2. Name it: `.github/workflows/facebook-poster.yml`
3. Paste the contents from the workflow file
4. Click **Commit new file**

---

## Step 6: Add GitHub Secrets

This is where you securely store your Facebook credentials.

1. In your repository, click **Settings** (tab)
2. In the left sidebar, click **Secrets and variables** → **Actions**
3. Click **New repository secret**

### Add these two secrets:

**Secret 1:**
- Name: `FB_PAGE_ACCESS_TOKEN`
- Value: Your long-lived Page Access Token from Step 3.4

**Secret 2:**
- Name: `FB_PAGE_ID`
- Value: Your Page ID from Step 4

4. Click **Add secret** for each

---

## Step 7: Enable GitHub Actions

1. Go to the **Actions** tab in your repository
2. You should see the workflow `Facebook Auto-Poster`
3. If it says "Workflows aren't being run", click **I understand my workflows, go ahead and enable them**

---

## Step 8: Test It!

### Manual Test First

1. Go to **Actions** tab
2. Click on **Facebook Auto-Poster** workflow
3. Click **Run workflow** → **Run workflow**
4. Wait for it to complete (green checkmark)
5. Check your Facebook Page - a post should appear!

### Check the Logs

1. Click on the workflow run
2. Click on **post** job
3. Expand **Run Facebook Poster** to see output

---

## How It Works

Once set up, the system:

1. **Runs automatically** on the schedule defined in the workflow
2. **Reads** the next unposted content from `content.csv`
3. **Posts** to your Facebook Page
4. **Logs** the posted ID to `posted.json`
5. **Commits** the updated log back to the repository
6. **Repeats** on schedule

### Default Schedule

The workflow runs every 30 minutes from 6am-10pm AEST. 

That's **32 posts per day** - adjust as needed.

---

## Customizing the Schedule

Edit `.github/workflows/facebook-poster.yml`:

```yaml
schedule:
  # Runs at minute 0 of every hour from 6am-10pm AEST
  # (Converted to UTC: 8pm previous day to 12pm)
  - cron: '0 20-23 * * *'    # 6am-9am AEST
  - cron: '0 0-12 * * *'     # 10am-10pm AEST
```

### Cron Format
```
┌─────── minute (0 - 59)
│ ┌───── hour (0 - 23) [UTC!]
│ │ ┌─── day of month (1 - 31)
│ │ │ ┌─ month (1 - 12)
│ │ │ │ ┌ day of week (0 - 6)
│ │ │ │ │
* * * * *
```

### Time Zone Conversion (AEST = UTC+10)
| AEST | UTC |
|------|-----|
| 6am | 8pm (previous day) |
| 12pm | 2am |
| 6pm | 8am |
| 10pm | 12pm |

### Example Schedules

**Every hour 6am-10pm AEST (16 posts/day):**
```yaml
- cron: '0 20-23 * * *'
- cron: '0 0-12 * * *'
```

**Every 30 min 7am-7pm AEST (24 posts/day):**
```yaml
- cron: '0,30 21-23 * * *'
- cron: '0,30 0-9 * * *'
```

**4 times per day (8am, 12pm, 4pm, 7pm AEST):**
```yaml
- cron: '0 22 * * *'   # 8am AEST
- cron: '0 2 * * *'    # 12pm AEST
- cron: '0 6 * * *'    # 4pm AEST
- cron: '0 9 * * *'    # 7pm AEST
```

---

## Adding More Content

To add more posts:

1. Edit `content.csv` in your repository
2. Add new rows following the format:
   ```
   id,pillar,content,hashtags,cta
   134,Pain Point,"Your content here","#hashtags #here","sc-sk.com"
   ```
3. Use `"` quotes around content with commas or newlines
4. Commit the changes

---

## Maintenance

### Token Refresh (Every 60 Days)

1. Repeat Step 3 to get a new long-lived token
2. Update the `FB_PAGE_ACCESS_TOKEN` secret in GitHub
3. Go to Settings → Secrets → Click on the secret → Update

**Set a calendar reminder** for 55 days from setup!

### Monitor Performance

- Check **Actions** tab for failed runs
- Check your Facebook Page for actual posts
- Review `posted.json` to see what's been posted

---

## Troubleshooting

### "Missing credentials" error
- Check that both secrets are set in GitHub
- Names must be exactly `FB_PAGE_ACCESS_TOKEN` and `FB_PAGE_ID`

### "Token expired" error
- Your token has expired. Repeat Step 3 to get a new one

### Posts not appearing
- Check the workflow completed successfully (green checkmark)
- Verify your Page ID is correct
- Check token has `pages_manage_posts` permission

### "Error validating access token"
- Token is invalid or expired
- Repeat Step 3 to generate a fresh token

### Workflow not running on schedule
- GitHub Actions cron can be delayed up to 15 minutes
- Make sure Actions are enabled in your repository
- Check for workflow errors in the Actions tab

---

## Cost Breakdown

| Service | Cost |
|---------|------|
| GitHub Actions | Free (2000 min/month) |
| Facebook API | Free |
| Total | **$0/month** |

Each workflow run takes ~30 seconds. At 20 posts/day:
- 20 posts × 30 sec = 10 minutes/day
- 10 min × 30 days = 300 minutes/month
- Well under the 2000 minute free tier!

---

## Files Reference

| File | Purpose |
|------|---------|
| `fb_poster.py` | Main Python script that posts to Facebook |
| `content.csv` | All your post content |
| `posted.json` | Tracks what's been posted (auto-updated) |
| `.github/workflows/facebook-poster.yml` | GitHub Actions schedule |

---

## Advanced: Local Running

You can also run the script locally for testing:

```bash
# Set environment variables
export FB_PAGE_ACCESS_TOKEN="your_token_here"
export FB_PAGE_ID="your_page_id"

# Test mode (doesn't post)
python fb_poster.py test

# Post once
python fb_poster.py

# Batch post (5 posts with 30 min gaps)
python fb_poster.py batch 5
```

---

## Questions?

Email: admin@sc-sk.com

---

**That's it! Your Facebook Page is now on autopilot. 🚀**
