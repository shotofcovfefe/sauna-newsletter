# Deployment Guide

## Prerequisites

Before deploying, ensure you have:
- [ ] A Vercel account (sign up at https://vercel.com)
- [ ] A GitHub account with this repository pushed
- [ ] Supabase project with the news table set up
- [ ] API keys: Perplexity, Gemini, Supabase (URL + anon key + service role key)

---

## Part 1: Deploy Website to Vercel

### Option A: Deploy via Vercel CLI (Recommended for first-time setup)

1. **Install Vercel CLI**
```bash
npm install -g vercel
```

2. **Navigate to website directory**
```bash
cd website
```

3. **Login to Vercel**
```bash
vercel login
```

4. **Deploy**
```bash
vercel
```

Follow prompts:
- Set up and deploy? **Y**
- Which scope? **Select your account**
- Link to existing project? **N**
- Project name? **sauna-newsletter** (or your preferred name)
- In which directory is your code? **./website** or **./** (if already in website dir)
- Override build settings? **N**

5. **Set environment variables**

After initial deployment, go to Vercel dashboard or run:
```bash
vercel env add NEXT_PUBLIC_SUPABASE_URL
# Enter your Supabase URL when prompted

vercel env add NEXT_PUBLIC_SUPABASE_ANON_KEY
# Enter your Supabase anon key when prompted
```

Make sure to add these for **Production**, **Preview**, and **Development**.

6. **Deploy to production**
```bash
vercel --prod
```

### Option B: Deploy via Vercel Dashboard (Easier)

1. **Go to https://vercel.com/new**

2. **Import Git Repository**
   - Click "Import Git Repository"
   - Select this GitHub repository
   - Click "Import"

3. **Configure Project**
   - **Root Directory**: Set to `website`
   - **Framework Preset**: Next.js (should auto-detect)
   - **Build Command**: `npm run build` (default is fine)
   - **Output Directory**: `.next` (default is fine)

4. **Add Environment Variables**

Click "Environment Variables" and add:

| Name | Value | Environments |
|------|-------|--------------|
| `NEXT_PUBLIC_SUPABASE_URL` | `https://xxxxx.supabase.co` | Production, Preview, Development |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | `your-anon-key` | Production, Preview, Development |

5. **Deploy**
   - Click "Deploy"
   - Wait 2-3 minutes for build to complete

6. **Verify**
   - Visit your deployed URL (e.g., `https://sauna-newsletter.vercel.app`)
   - Check that the map loads
   - Check that `/api/news` returns data (may be empty initially)

---

## Part 2: Set Up GitHub Actions for Daily Scraping

### Step 1: Add GitHub Secrets

1. **Go to your GitHub repository**
2. **Navigate to**: Settings → Secrets and variables → Actions
3. **Click "New repository secret"**

Add these **4 secrets**:

| Name | Value | Description |
|------|-------|-------------|
| `PERPLEXITY_API_KEY` | `your-perplexity-key` | From Perplexity dashboard |
| `GEMINI_API_KEY` | `your-gemini-key` | From Google AI Studio |
| `SUPABASE_URL` | `https://xxxxx.supabase.co` | From Supabase project settings |
| `SUPABASE_KEY` | `your-service-role-key` | **SERVICE_ROLE** key (not anon!) |

**Important**: For GitHub Actions, use the **SERVICE_ROLE** key from Supabase (found in Settings → API), not the anon key. This allows write access.

### Step 2: Enable GitHub Actions

1. **Go to**: Actions tab in your GitHub repository
2. **You should see**: "Daily Sauna News Scraper" workflow
3. **If disabled**: Click "I understand my workflows, go ahead and enable them"

### Step 3: Test the Workflow Manually

1. **Go to**: Actions → Daily Sauna News Scraper
2. **Click**: "Run workflow" (on the right)
3. **Configure**:
   - `lookback_days`: **7** (for testing)
   - `dry_run`: **false** (uncheck)
4. **Click**: "Run workflow"

5. **Monitor**: Watch the workflow run (takes ~5 minutes)
6. **Verify**:
   - Check workflow logs for success
   - Check Supabase table for new news items
   - Check website `/api/news` endpoint

### Step 4: Verify Daily Schedule

The workflow is configured to run automatically every day at 6:00 AM UK time.

You can see this in `.github/workflows/daily-news-scrape.yml`:
```yaml
schedule:
  - cron: '0 6 * * *'  # 6:00 AM UTC
```

No further action needed - it will run daily automatically.

---

## Part 3: Verification Checklist

### Website Deployment ✓

- [ ] Website is live at Vercel URL
- [ ] Map displays correctly with venue markers
- [ ] News sidebar appears (may be empty initially)
- [ ] Filter panel works
- [ ] Newsletter modal appears after 15 seconds
- [ ] No console errors in browser DevTools

### API Endpoints ✓

- [ ] `https://your-domain.com/api/news` returns JSON
- [ ] Response has correct CORS headers
- [ ] Data updates after scraper runs

### GitHub Actions ✓

- [ ] All 4 secrets are set in GitHub repository
- [ ] Workflow runs successfully (green checkmark)
- [ ] News items appear in Supabase after workflow runs
- [ ] Workflow is scheduled to run daily at 6 AM

### Database ✓

- [ ] Supabase `sauna_news` table exists
- [ ] Row Level Security policies allow public read access
- [ ] News items are being inserted correctly

---

## Part 4: Environment Variables Reference

### Frontend (Vercel) - Required

These must be set in **Vercel Project Settings → Environment Variables**:

```bash
NEXT_PUBLIC_SUPABASE_URL=https://xxxxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key-here
```

**Note**: The `NEXT_PUBLIC_` prefix is required for Next.js to include them in the browser bundle.

### Backend (GitHub Actions) - Required

These must be set in **GitHub Repository → Settings → Secrets**:

```bash
PERPLEXITY_API_KEY=your-perplexity-key
GEMINI_API_KEY=your-gemini-key
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_KEY=your-service-role-key  # NOT the anon key!
```

---

## Troubleshooting

### Issue: News sidebar not showing

**Check**:
1. Vercel environment variables are set correctly
2. Supabase RLS policies allow public read access
3. Browser console for errors (F12 → Console)
4. API endpoint: `https://your-domain.com/api/news`

**Fix**:
```bash
# Test API locally
curl https://your-domain.com/api/news

# Should return: {"news": [...]}
```

### Issue: GitHub Actions failing

**Check**:
1. All 4 secrets are set in GitHub
2. Using **SERVICE_ROLE** key (not anon key)
3. Workflow logs for specific error message

**Fix**:
- Go to Actions → Failed workflow → View logs
- Look for error messages in "Run news scraper" step

### Issue: News not updating after scraper runs

**Check**:
1. GitHub Actions workflow completed successfully
2. Supabase table has new rows
3. API endpoint returns fresh data

**Fix**:
- API has 30-minute cache, wait or force refresh:
```bash
curl -H "Cache-Control: no-cache" https://your-domain.com/api/news
```

---

## Ongoing Maintenance

### Daily Operations

The system runs automatically:
- GitHub Actions scrapes news daily at 6 AM UK time
- Saves new items to Supabase
- Website API fetches from Supabase (cached 30 min)
- No manual intervention needed

### Manual Operations

**Manually trigger scraper:**
```bash
# In GitHub Actions tab
Actions → Daily Sauna News Scraper → Run workflow
```

**Clear all news and reseed:**
```bash
python src/scripts/clear_news.py
python src/scripts/scrape_daily_news.py --lookback 14 --limit 7
```

**Check news items:**
```bash
# In Supabase dashboard
SQL Editor → run:
SELECT * FROM sauna_news ORDER BY scraped_at DESC LIMIT 10;
```

---

## Success Criteria

When everything is working correctly:

1. ✅ Website is live and accessible
2. ✅ News sidebar displays recent items
3. ✅ GitHub Actions runs successfully every morning
4. ✅ New news items appear daily
5. ✅ No errors in Vercel deployment logs
6. ✅ No errors in GitHub Actions logs

You're done! 🎉

---

## Support

If you encounter issues:

1. Check Vercel deployment logs: Dashboard → Deployments → View Function Logs
2. Check GitHub Actions logs: Actions → Workflow run → View logs
3. Check Supabase logs: Project → Logs
4. Review this document's Troubleshooting section
