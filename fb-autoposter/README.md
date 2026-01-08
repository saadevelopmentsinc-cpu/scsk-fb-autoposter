# SCSK Facebook Auto-Poster

Automatically posts content to Facebook Page using GitHub Actions.

## Quick Start

1. Read `SETUP-GUIDE.md` for full instructions
2. Get your Facebook Page Access Token
3. Add secrets to this repository
4. Enable GitHub Actions
5. Sit back and watch it post!

## Files

- `fb_poster.py` - Main posting script
- `content.csv` - 133 pre-written posts
- `posted.json` - Tracks what's been posted
- `.github/workflows/` - Automation schedule

## Schedule

Default: Posts every 30 minutes from 6am-10pm AEST

Edit `.github/workflows/facebook-poster.yml` to customize.

## Cost

**$0/month** - Uses free tiers only.

## Maintenance

- Refresh your Facebook token every 60 days
- Add new content to `content.csv` as needed

---

Built for [SCSK - Site Companion Side Kick](https://sc-sk.com)
