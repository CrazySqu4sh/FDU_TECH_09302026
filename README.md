# Botb_FDU_2026

# Aparece: AI visibility and accuracy for small businesses

Checks what AI assistants tell customers about a business, compares it to the business's
verified facts, flags wrong facts and missed opportunities (in English and Spanish),
drafts fixes, and requires a named person to approve before anything goes public.

## Run it (demo mode, no API keys needed)

Terminal 1, backend:
```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Terminal 2, frontend:
```bash
cd frontend
npm install
npm run dev
```
Open http://localhost:5173. Three demo businesses load with one scan each. Switch between them in the top bar.

| | E-commerce package | Tech products package | Services package |
|---|---|---|---|
| Demo business | Piel Fina Leather Co. (online leather goods, Shopify + eBay) | Conecta Tech Refurbished (laptops and phones) | Taller Hernández Auto Repair |
| Facts checked | Price and stock per product, shipping time, return window | Price, stock, specs (RAM, storage, battery), features (touchscreen), warranty, returns | Hours, prices, services, phone, languages |
| Headline metric | Product and store fact accuracy | Product and spec accuracy | Named in AI answers (inclusion rate) |
| Typical errors caught | "Sold out" when in stock, wrong price, "no returns" | Hallucinated touchscreen, half the RAM, "3-month warranty" | Wrong hours, wrong phone number, missed services |
| Evidence source | Synced from store (Shopify, eBay) | Store sync + manufacturer spec sheets | Google Business Profile, documents, owner |

**Sales impact tab:** weekly visits from search vs. AI assistants, AI-referred sales, a "without Aparece"
estimate (sales at the accuracy measured on the first scan), estimated sales lost to wrong facts, and customer
contacts caused by wrong AI info. Demo data is simulated (each scan = one week) and labeled as such. For real
data, `PUT /api/businesses/{id}/sales` with weekly rows from Shopify / Square / GA4 (AI referrers:
chatgpt.com, perplexity.ai, gemini.google.com, claude.ai). Deep link a pitch screen with `?biz=2&tab=impact`.

**Demo script for the pitch (e-commerce):** Overview (product accuracy + Spanish gap) → Truth vs. AI
(boots shown as sold out, "no returns") → Issues → "Draft a fix" → type a name → "Approve fix" →
"Run scan" → accuracy jumps. Then switch to the auto shop to show the services package.

To reset the demo, stop the backend and delete `backend/aparece.db`.

One-command option: run `npm run build` in `frontend`, then open http://localhost:8000
(the backend serves the built app).

## Homepage and one-step scan (just a website)

The app opens on a public **homepage** (`frontend/src/components/Landing.jsx`): who Aparece is, the problem with sourced
statistics (BrightLocal 2026, SOCi 2026, Adobe 2025), how it works, what owners get, who it's for, pricing ("we grow as
your business grows"), about us, FAQ. English and Spanish. "Sign in" opens the dashboard; `?biz=`/`?tab=` deep links skip it.

The main call to action is **one box: the business's website**. `POST /api/quick-scan` then:
1. reads the site and works out the business name, city, type and facts (asks only for name or city if the site doesn't say);
2. asks the assistants customer questions in EN + ES, including one per service found ("Who offers move-out cleaning in Houston?");
3. returns one report: how often AI recommends you, **customers you're missing** (and who AI names instead, with how to win
   each), what AI gets wrong, whether AI can read your site, a 5-step action plan and ready-to-paste bilingual Q&A;
4. "Start free trial" creates the business with everything already filled in. No CSV or CRM needed.

## Sign-up before the free scan, and Leads

The homepage's website box now opens a short **sign-up** (`Signup.jsx`, `POST /api/leads`) before the scan runs:
- about you: name, email, phone (optional), role
- your business: name, website, city, type
- why are you checking today? (fewer calls, competitors show up and I don't, wrong info, curious, Spanish-speaking customers, referred)
- what problem do you think you have? (can't be found, wrong hours/prices/phone, outdated website, no time, few reviews, not in Spanish)
- tell us more, and how do you hope we can help (free text)
- consent to be contacted about the results

The sign-up is linked to its scan and, if they start one, their trial. **Leads** (dashboard top bar, `GET /api/leads`, CSV at
`/api/leads.csv`) lists every sign-up with their answers, their scan results, the most common reasons and problems, and a
status (new, contacted, on trial, customer, not a fit). The demo has no staff login; add one before launch.

## Website check (URL and optional CSV)

"Website check" in the top bar (public, no account) and Fix → Website check (for a customer, also compares their verified
facts with their site). `POST /api/site-audit`, `backend/app/site_audit.py`. Plain code, no API key, $0.

- Reads the homepage, robots.txt and up to 5 key pages (services, prices, about, contact, FAQ, Spanish) the way an
  assistant would. Real sites are fetched live; demo `.example` sites are simulated.
- **AI-readiness score (0–100)** from 12 weighted checks: AI search crawlers allowed, structured data, phone as text, hours,
  prices, services, service area, trust facts (insured/licensed), Spanish content, Q&A, title/description, reviews.
  Each failed check has a plain-language "why it matters" and "what to do"; the top 3 are ranked by impact.
- **What AI can read on your site:** the phone, prices, hours, services, area, trust facts and structured data it found.
- **Optional CSV** (service/product, service_es, price): each item is checked for being on the site, having the same
  price, and appearing in Spanish ("2 of 3 services aren't on your site, so AI can't recommend you for them").
- **Ready-to-paste fixes:** bilingual Q&A, page title and description, and structured data, built from the true values
  (verified facts, then the CSV, then the site) with missing services added.
- **Next step:** start a free trial with the facts found on the site already filled in, or run a Free AI Check.

## Proof behind every finding (evidence layer)

`backend/app/evidence.py` and `backend/app/reader.py` (plain code, no AI, no new dependencies):

- **Fact confirmation** (Fix → Verified profile → "Check my facts on the web", `POST /api/businesses/{id}/verify-facts`):
  reads the business's website and the listings AI cites, records what each says per fact. 2+ independent sites agreeing
  makes an owner fact **Confirmed** (strong enough to mark AI answers wrong). A listing that disagrees becomes a
  **source_conflict** issue ("yellowpages.com lists your phone number wrong").
- **Copied or made up?** (`POST /api/incidents/{id}/check-sources`): opens the pages the assistant cited and labels each
  wrong claim **Copied from [site]** (a cited page says the same wrong value), **Made up** (none does), or **Unclear**.
  Runs automatically after demo scans; on demand in live mode.
- **Evidence report** per issue (`GET /api/incidents/{id}/evidence`, "Show evidence" → Download JSON): the truth and who
  confirms it, the exact AI answers with time, model and SHA-256 fingerprint, every cited page with its snippet,
  fingerprint and time, the approval trail, and the checker's measured accuracy.
- Every page read is saved in `page_snapshots` with a SHA-256 fingerprint. Demo `.example` sites are simulated and marked.

## Check the checker, $0 scans, real bookings, Proof Lab

- **Check the checker** (What AI says → Answers): a person reviews random verdicts; agreement is the checker's accuracy.
- **Paste answers from free AI apps** (Answers → "Paste answers", `POST /api/businesses/{id}/manual-scan`): answers from
  the free ChatGPT, Gemini, Perplexity or Copilot apps are read with code and checked like any scan. $0, and it's what
  customers see. Same-day pastes add up to one scan; Home warns when a scan has fewer than 12 answers.
- **Customers who found you through AI** (Data & settings, also on Sales impact): weekly "How did you hear about us?" counts.
- **Proof Lab** (Results → Proof Lab, `backend/app/prooflab.py`): same 4 competitor pages, same questions (EN + ES),
  same repeats; only the business's page changes from before to after Aparece's fixes. Measures recommended %, by language,
  and facts stated correctly; downloads every answer as CSV. Live with an API key (answers read by code); simulated and
  labeled in demo mode. It shows the mechanism, not search-engine indexing speed.

Navigation is grouped into five sections: Home, What AI says, Fix, Results, Data & settings.

## Flagship: cleaning services

Demo business **Brillo Cleaning Co.** (Houston, Gold) is selected first. Checks: prices (deep and standard clean),
bonded and insured, background checks, move-out, supplies included, eco-friendly, office cleaning, service area,
Saturday hours, phone, Spanish-speaking team. Customer questions come from real hiring intents in EN and ES
("How much does a deep clean cost for a 3-bedroom house…", "Limpieza de mudanza cerca de…").

## AI Business Assistant (chat)

"Ask Aparece" on every dashboard screen (`POST /api/businesses/{id}/chat`, `backend/app/assistant.py`). It answers only
from the business's own data (latest scan, open issues, sources, competitors named instead, growth plan) in English or
Spanish, and links to the screen that fixes it. With API keys it uses Claude (or ChatGPT) with instructions never to invent
numbers; in demo mode it answers common questions from templates over the same data.

## Growth plan: why the changes work, and the projection

- Headline in owner terms: extra jobs a month by month 3, a slow-to-fast range over 90 days, return per $1 of the plan,
  and an input for the owner's own average job value (every figure updates).
- **Projection chart** with a likely range (50%–130% of the expected effect) vs. "if nothing changes".
- **Where the extra sales come from:** a waterfall that applies each step in order in the same market.
- **Why this works** under every step: evidence from the business's own scans (e.g. fixing the phone number took accuracy
  from 25% to 100%) plus cited research (BrightLocal 2026, SOCi 2026, BLS 2023, Pew 2025, Adobe Analytics).
- **How we calculated this:** every assumption with its source. AI growth +4%/week (Adobe: +693% year over year),
  search −0.5%/week (Gartner prediction), and the Aparece assumptions labeled as such.

## What works (AI is a black box, so we measure)

We can't see how an assistant decides, but every scan asks the same questions, so the **What works** tab
(Silver and Gold, `GET /api/businesses/{id}/insights`, `backend/app/insights.py`) measures instead:

- **Trend over scans:** named in answers, named in Spanish, fact accuracy, with markers where approved fixes went live.
- **Which fixes worked:** each approved fix is an experiment. Lift = change on the questions or fact it targets
  minus the change on everything else over the same scans (difference-in-differences), so drift inside the assistants
  isn't counted as a win. Results show "worked", "no clear effect yet" or "got worse", and small samples are flagged "early".
- **What goes with being recommended:** a dumbbell chart of how often AI names you with vs. without each signal
  (your site cited, map profile, review sites, old directory, Spanish question, asked by name), plus the wrong-fact rate
  for each. Correlation only, labeled that way; e.g. an old directory gets you named more often but with wrong facts.
- **Heatmap** of customer question × scan, and **one small chart per assistant**.

Demo mode has a **Simulate 6 weeks (demo)** button (`POST /api/businesses/{id}/demo/simulate`). It runs weekly scans and
approves one wrong-fact fix and one missed-opportunity fix every other week as "Demo owner (simulated)", recorded in the audit log.

## How AI sees you (what the AI relies on)

The **How AI sees you** tab shows, for the latest scan:
- **Each assistant's view:** how it describes the business, words it associates with it, tone, how often it names it,
  average rank, and every fact it believes (wrong ones first, next to the verified value).
- **What AI associates you with** across all assistants, and **what AI doesn't know** (verified facts no answer mentioned).
- **Where AI gets its information:** the websites the assistants cited, how many answers cited each, and the share of
  those answers with a wrong fact. A source is flagged as a **likely cause** when 60%+ of answers citing it are wrong
  (a pattern, not proof; a person checks before anyone contacts the site). Each row says what to do.
- Drafted fixes name the **likely source** for that wrong fact, and the Answers tab lists each answer's sources.

Live mode records real citations: Claude web-search citations and ChatGPT `url_citation` annotations
(`agents._claude_web`, `agents._openai_web`). The extractor also returns a one-line description, descriptors and tone.
Demo mode simulates sources, including an outdated directory listing that causes most wrong facts.
`GET /api/businesses/{id}/perception`.

## Niche: contractors and trades

The flagship package is **Contractors & trades** (roofing, remodeling, landscaping, cleaning, HVAC): an industry with a
large Hispanic workforce and many Hispanic-owned firms, where customers now ask AI "licensed roofer near me" and the costly
errors are about trust. Demo business: Hernández Roofing & Remodeling (Dallas, Gold plan).

| Checks | How |
|---|---|
| Contractor license / registration | Critical severity. "Not licensed" when there is one on file is flagged wrong. Matches ignore punctuation. |
| Liability insurance | Critical severity, yes/no |
| Service area | Wrong only if AI names a city they don't serve (naming fewer cities is fine) |
| Free estimates, emergency service, prices, hours, phone, Spanish-speaking crew | Same checks as services |

## Adding a business, and what we ask for

1. **Free AI Check → Start free trial** (self-serve), or **+ Add** (assisted), or `POST /api/businesses` (partners, bulk).
2. Facts: typed in, or imported from a **CSV** (products for stores and tech; services and prices for trades and services).
   Templates download from the form. Columns that look like customer data (email, customer, address, card…) are dropped.
   Imports update matching facts instead of duplicating them.
3. Optional **weekly sales totals** CSV (Data & privacy tab): search visits, AI visits, orders or jobs, revenue. It replaces
   the simulated numbers.

We never ask for CRM exports, customer names or contacts, card details, passwords, or SSN / ITIN / immigration status.

## Data & privacy tab

What we ask for vs. never ask for, where each kind of data goes (only public customer questions go to the assistants;
sales totals never go to any AI), one-click **export of everything** (`GET /api/businesses/{id}/export`), **delete everything**
by typing the business name (`DELETE /api/businesses/{id}`), recent data activity, and a security checklist that separates
what the demo does today from what must ship before launch (sign-in with ownership verification, roles, encryption, backups, SOC 2).

## Growth plan tab (point A → point B)

Point A is measured today. Point B is a 90-day target (95% accuracy, +25 points named in answers, Spanish gap closed).
Five steps come from the business's real issues (urgent wrong facts, unproven facts, the Spanish gap, missed questions, staying current),
each with a button to the screen that fixes it. Silver and Gold add a projected-sales chart ("with the plan" vs. "if nothing changes")
and the extra sales over 90 days, counting only what the plan adds (`GET /api/businesses/{id}/growth`). Projections are model
estimates and are labeled that way.

## Who it's for, and plans

Built for small, Hispanic-owned and minority-owned businesses, with an Enterprise plan for large companies,
franchises and multi-location brands. The server enforces every limit (`backend/app/plans.py`); the UI shows locked
features with an upgrade prompt instead of hiding them.

| | Free trial | Silver | Gold | Enterprise |
|---|---|---|---|---|
| Price | $0, 14 days | $29/mo ($15 community pricing) | $99/mo | Custom |
| Assistants / questions | 2 / 3 (EN + ES) | 3 / 6 | All / 12 | All / 24 |
| Fix drafts | 3 | Unlimited | Unlimited | Unlimited |
| Adds | Truth vs. AI, bilingual, approval gate, audit log | Missed opportunities, scan history, AI-referred visits and sales | Per-product accuracy, lost sales and "without Aparece" lift, 90%-in-60-days guarantee | Multi-brand, API, more languages, SSO (roadmap) |

Governance (human approval, evidence levels, audit log) is in every plan, including the trial.
Demo plans: Taller = trial, Piel Fina = Silver, Conecta Tech = Gold. Switch plans on the Plans page (no payment in the demo).

**Free AI Check** (`?page=check`, `POST /api/check`): no account needed. Enter a business name, type and city, plus up
to two facts, and it asks every assistant 4 customer questions in English and Spanish. It shows the inclusion rate,
who gets recommended instead, the English/Spanish gap, and wrong facts. "Start free trial" (`POST /api/check/{id}/start-trial`)
turns the check into a business on the trial.

## Go live with real assistants

Copy `backend/.env.example` to `backend/.env`, add `ANTHROPIC_API_KEY` and/or `OPENAI_API_KEY`, and restart the
backend (it reads `backend/.env` automatically; `.env` is git-ignored, never commit it). With keys present,
scans ask Claude and ChatGPT for real (with web search) and a cheap model extracts claims.
Gemini and Perplexity appear only in demo mode until you add their clients in `agents.py`.
Check each provider's current model names and web-search tool names in their docs.

## How it maps to the proposal

| Proposal piece | Code |
|---|---|
| Verified profile + evidence levels | `validator.py` (`effective_evidence`), `facts` table (products via `product` column) |
| E-commerce checks (stock, shipping, returns) | `validator.values_match`, `agents.ecommerce_journeys` |
| Journey Agent (customer questions, EN + ES) | `agents.generate_journeys` |
| Query Runner | `agents.ask_assistant`, `services.run_scan` |
| Claim Extraction Agent | `agents.extract` (AI reads, returns JSON) |
| Validator (no AI grading AI) | `validator.verdict` (plain code) |
| Missed AI Opportunities, Language Visibility Gap | `services._update_incidents`, `_scan_metrics` |
| Fix Agent (plain language + structured data) | `agents.generate_fix` |
| Human approval gate + accountability | `/api/incidents/{id}/approve` requires a name; `audit_log` |
| Retest loop, resolution time | next scan auto-resolves approved issues |

**Automatic:** scanning, extracting, validating, scoring, drafting fixes, retesting.
**Needs a person:** confirming facts, approving any fix, dismissing issues. Facts backed only by the
owner produce "Needs a person" instead of "Wrong."

## Known limits (say these to judges)
- API answers can differ from what a person sees in the consumer apps; we track trends across many questions.
- Demo mode simulates answers so the workflow can be shown without keys; label screenshots as simulated.
- Stock changes daily, so stock facts expire after 7 days unless synced from the store.
- Next steps: live Shopify/eBay/Square sync, source investigation (which listing caused the error), POS/Shopify/eBay sync,
  WhatsApp approvals, PostgreSQL, logins with ownership verification.

## Stack
FastAPI + SQLite (swap for PostgreSQL), React + Vite. No UI libraries.
