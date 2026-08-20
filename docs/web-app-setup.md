# Turning the site into the live app

The website works with no configuration at all — signed-out visitors get the
interactive preview. Adding the four services below turns it into a real
product: accounts, tracked flights stored online, nightly price checks and
email alerts.

Everything is plain HTTP from Vercel functions, so there is still no build
step and no `node_modules`.

---

## What you create, and what it costs

| Service | Why | Free tier |
|---|---|---|
| **Supabase** | Accounts (magic-link sign-in) + the database holding tracked flights, price history and alerts | Free project is enough |
| **Duffel** | Live fares for the scheduled checks | Free test mode; live mode needs their approval |
| **Resend** | Sends the price-drop emails | 3,000 emails/month free |
| **Vercel** | Hosting, the API functions and the nightly cron | Already set up |

---

## 1 · Supabase

1. Create a project at [supabase.com](https://supabase.com) (any region near you).
2. Open **SQL Editor → New query**, paste all of
   [`supabase/schema.sql`](../supabase/schema.sql), and run it. It creates
   `profiles`, `tracked_flights`, `price_observations` and `alerts`, switches on
   row-level security, and adds the trigger that creates a profile on signup.
3. Open **Authentication → URL configuration** and set:
   - **Site URL**: `https://skybuddy-ochre.vercel.app`
   - **Redirect URLs**: add `https://skybuddy-ochre.vercel.app` and, if you want
     to test locally, `http://localhost:8899`
4. Open **Authentication → Providers → Email** and make sure *Email* is enabled.
   Magic links are on by default; you can turn "Confirm email" off for a
   friendlier first run.
5. Copy from **Project Settings → API**:
   - `Project URL` → `SUPABASE_URL`
   - `anon public` key → `SUPABASE_ANON_KEY`
   - `service_role` key → `SUPABASE_SERVICE_ROLE_KEY` **(server only — never put
     this in the browser)**

> Supabase's built-in email sender is rate-limited (a few messages an hour). For
> real sign-in volume, add your own SMTP under **Authentication → Emails → SMTP**,
> or point it at Resend.

## 1b · The second migration (booking, wallet, travellers)

Run [`supabase/schema-2-app-features.sql`](../supabase/schema-2-app-features.sql) in the
same SQL editor. It adds `booking_intents`, `loyalty_cards` and `passengers`,
all under row-level security, which the dashboard's **Book**, **Wallet** and
**Travellers** tools use.

## 2 · Duffel

1. Sign up at [duffel.com](https://duffel.com) and open **Developers → Access tokens**.
2. Create a **test** token to start (`duffel_test_...`) → `DUFFEL_API_KEY`.
3. Test mode returns Duffel's sandbox inventory, which is perfect for checking
   the whole loop — but the prices are invented, so identical searches come
   back different. The site labels that.

### When your live token arrives

Replace `DUFFEL_API_KEY` in Vercel with the `duffel_live_...` token and
redeploy. Nothing else changes:

* the search box switches to Duffel automatically, because the site prefers a
  live token and only falls back to Google Flights without one;
* the sandbox warning disappears on its own;
* the price history stays with the Google Flights collector, so the
  low/median/high keep comparing like with like. To hand the history to Duffel
  instead, set `PRICE_SOURCE=duffel` and the nightly sweep will fetch and store
  its prices — leave it unset to keep the collector as the source.

## 3 · Resend

1. Sign up at [resend.com](https://resend.com) → **API Keys → Create**.
2. Copy the key → `RESEND_API_KEY`.
3. Sending address → `ALERT_FROM_EMAIL`:
   - Straight away: `SkyBuddy <onboarding@resend.dev>` (works without a domain,
     but only delivers to your own verified address).
   - Properly: verify a domain in Resend and use `SkyBuddy <alerts@yourdomain>`.

## 3b · Real prices: the Google Flights collector

Duffel test tokens invent inventory, so identical searches return different
fares. For real prices without waiting for Duffel to approve a live account,
SkyBuddy prices tracked routes with the Google Flights client from a scheduled
GitHub Actions job — the site reads whatever it writes.

**GitHub → your repository → Settings → Secrets and variables → Actions → New
repository secret**, add four:

```
SUPABASE_URL                 https://xxxxxxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY    eyJhbGci...
SKYBUDDY_SITE_URL            https://skybuddy-ochre.vercel.app
CRON_SECRET                  the same value you put in Vercel
```

The workflow (`.github/workflows/price-collector.yml`) then runs at 06:10,
12:10 and 18:10 UTC. Run it by hand any time from **Actions → Collect flight
prices → Run workflow**.

To add the dashboard's **Refresh prices** button, create a fine-grained GitHub
token with *Contents: read and write* on this repository and set it in Vercel as
`GITHUB_DISPATCH_TOKEN` (optionally `GITHUB_REPO` if you rename the repo).

> The scraper reads Google Flights' public results. It is unofficial, so it can
> break if Google changes its responses, and it should be run at a modest
> frequency — three times a day is deliberate.

## 4 · Vercel environment variables

**Project → Settings → Environment Variables** (Production *and* Preview):

```
SUPABASE_URL=https://xxxxxxxx.supabase.co
SUPABASE_ANON_KEY=eyJhbGci...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGci...
DUFFEL_API_KEY=duffel_test_...
RESEND_API_KEY=re_...
ALERT_FROM_EMAIL=SkyBuddy <onboarding@resend.dev>
CRON_SECRET=<any long random string>
GITHUB_DISPATCH_TOKEN=<optional, enables the Refresh prices button>
```

Then **redeploy** (Deployments → ⋯ → Redeploy) so the functions pick them up.

Check it worked by opening `https://skybuddy-ochre.vercel.app/api/config` —
every flag under `features` should be `true`.

---

## How the pieces fit

```
browser ──sign in (magic link)──▶ Supabase Auth
   │
   ├── reads/writes tracked_flights, price_observations, alerts
   │        directly with the anon key, constrained by RLS
   │
   ├── POST /api/search  ──▶ Duffel        (key stays server-side)
   └── POST /api/check   ──▶ Duffel + Supabase + Resend

Vercel Cron ──06:00 UTC daily──▶ GET /api/cron/check-prices
                                   ├─ re-prices every active tracked flight
                                   ├─ stores an observation
                                   ├─ refreshes low / median / high
                                   └─ emails when a rule fires
```

### When an email goes out

| Rule | Fires when |
|---|---|
| `target_reached` | The fare is at or below the target the traveller set |
| `new_low` | The fare beats every price recorded for that route (needs 3+ observations) |
| `price_drop` | The fare is 10% or more below the previous check |

The same alert kind is not repeated for the same flight within 20 hours, so a
route that stays cheap does not mail every night.

### Changing the schedule

`vercel.json` → `crons[0].schedule` (cron syntax, UTC). `0 6 * * *` is daily at
06:00 UTC. Hobby projects on Vercel run cron jobs once a day; Pro allows more
frequent schedules.

---

## Local development

```bash
npm i -g vercel
vercel dev          # serves web/ and the /api functions with your env vars
```

Plain `python -m http.server --directory web 8899` also works, but `/api/*`
returns 404, so the site stays in preview mode — which is a good way to check
the signed-out experience.

---

## Troubleshooting

| Symptom | Cause |
|---|---|
| "Sign-in is not configured yet" | `SUPABASE_URL` / `SUPABASE_ANON_KEY` missing, or no redeploy after adding them |
| Magic link opens the site but stays signed out | The Site URL / Redirect URLs in Supabase do not match the deployment URL |
| "Live search is not configured" | `DUFFEL_API_KEY` missing |
| Search returns "Duffel search failed (401)" | The token is wrong, or a live token is used on a test account |
| Alerts appear in the dashboard but no email arrives | `RESEND_API_KEY` missing, or the from-address domain is not verified in Resend |
| Cron never runs | Redeploy after adding `crons` to `vercel.json`; check Vercel → Project → Cron Jobs |
