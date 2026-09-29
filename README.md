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
Open http://localhost:5173. Two demo businesses load with one scan each. Switch between them in the top bar.

| | E-commerce package | Services package |
|---|---|---|
| Demo business | Piel Fina Leather Co. (online leather goods, Shopify + eBay) | Taller Hernández Auto Repair |
| Facts checked | Price and stock per product, shipping time, return window | Hours, prices, services, phone, languages |
| Headline metric | Product and store fact accuracy | Named in AI answers (inclusion rate) |
| Typical errors caught | "Sold out" when in stock, wrong price, "no returns" | Wrong hours, wrong phone number, missed services |
| Evidence source | Synced from store (Shopify, eBay) | Google Business Profile, documents, owner |

**Demo script for the pitch (e-commerce):** Overview (product accuracy + Spanish gap) → Truth vs. AI
(boots shown as sold out, "no returns") → Issues → "Draft a fix" → type a name → "Approve fix" →
"Run scan" → accuracy jumps. Then switch to the auto shop to show the services package.

To reset the demo, stop the backend and delete `backend/aparece.db`.

One-command option: run `npm run build` in `frontend`, then open http://localhost:8000
(the backend serves the built app).

## Go live with real assistants

Copy `backend/.env.example` to `backend/.env`, add `ANTHROPIC_API_KEY` and/or `OPENAI_API_KEY`,
then load it before starting (`export $(cat .env | xargs)` on Mac/Linux). With keys present,
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
