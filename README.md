# SCSK Social Auto-Poster

Automatically posts SCSK content to Facebook, LinkedIn, and X using GitHub Actions.

## Quick Start

1. Read `SETUP-GUIDE.md` for full instructions
2. Get your Facebook Page Access Token, LinkedIn token, and X OAuth credentials
3. Add secrets to this repository
4. Enable GitHub Actions
5. Sit back and watch it post!

## Files

- `fb_poster.py` - Main posting script
- `linkedin_poster.py` - LinkedIn posting script
- `x_poster.py` - X posting script with direct product-focused ads
- `content.csv` - 133 pre-written posts
- `posted.json` - Tracks what's been posted
- `posted_linkedin.json` - Tracks LinkedIn posts
- `posted_x.json` - Tracks X posts
- `.github/workflows/` - Automation schedule

## X Setup

Add these GitHub repository secrets:

- `X_CLIENT_ID`
- `X_CLIENT_SECRET`
- `X_REFRESH_TOKEN`
- `X_ALLOWED_MENTIONS` optional, comma-separated, only for accounts you are allowed to tag

`X_REFRESH_TOKEN` is the `refresh_token` value from the local X OAuth token cache created by `python x_poster.py auth`.

The X poster avoids mass tagging or random community spam. It uses construction-focused hashtags and direct SCSK product descriptions for better long-term reach.

Test locally without posting:

```bash
python x_poster.py test
```

Check auth without posting:

```bash
python x_poster.py auth-test
```

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
