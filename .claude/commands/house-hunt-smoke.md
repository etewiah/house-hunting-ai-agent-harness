---
description: Smoke-test the browser-assisted house-hunt flow on a given buyer brief. Discovers listings on the web, normalizes them, and runs the harness.
---

Run a smoke test of the browser-assisted house-hunt workflow on this buyer brief:

$ARGUMENTS

## Steps to follow

1. **Validate the brief.** If `$ARGUMENTS` is empty or unclear, ask the user for a complete brief that includes: target location, budget, bedroom count, and key priorities (e.g. parking, garden, quiet street, schools). Then stop and wait.

2. **Discover candidate listings.** Use `WebSearch` to find 5–8 candidate listing URLs that plausibly match the brief. Search across major UK listing sites (Rightmove, Zoopla, OnTheMarket) if possible. Aim for a mix of price points and locations within the brief.

   Example searches:
   - `2-bed flat to rent Birmingham under £250k`
   - `site:rightmove.co.uk 3-bed house Surbiton`
   - `Zoopla 4-bed Bristol garden parking`

3. **Fetch and extract listings.** For each candidate URL, use `WebFetch` (or `claude-in-chrome` `navigate` + `read_page` if WebFetch is blocked) to fetch the page and extract:
   - `id`: a slug or sequential ID
   - `title`: listing title or headline
   - `price`: integer, in pounds
   - `bedrooms`: integer count
   - `bathrooms`: integer count
   - `location`: city, area, or postal code
   - `commute_minutes`: integer or null (do not invent; leave null if not on page)
   - `features`: list of normalized keywords (parking, garden, garage, walkable, quiet street, balcony, lift, etc.)
   - `description`: a few sentences from the listing summary or key features
   - `source_url`: the canonical URL

4. **Filter and normalize.** Keep only listings where you successfully extracted at least price, bedrooms, bathrooms, and location. If a listing has sparse data (e.g. missing description), normalize what you have and mark it; do not discard it.

5. **Call the harness.** Invoke the `run_house_hunt` MCP tool with:
   ```
   brief = "<the buyer brief>"
   listings = [<the normalized listing dicts>]
   limit = 5
   ```

6. **Report to the user.** Format a summary containing:
   - **Buyer profile** (parsed location, budget, beds, commute, priorities)
   - **Ranked listings** (top 5 or fewer, with score, price, beds, location, key matches, key misses, warnings)
   - **Comparison** (side-by-side of the top 3)
   - **Affordability** (deposit, loan, monthly payment for the top match)
   - **Tour questions** (what to ask on a viewing)
   - **Offer brief** (points to consider for the top match)
   - **Boundary notice** (the harness's disclaimer about advice limits)
   - **Trace path** (if the MCP tool returned one, include it for diagnostics)

## Guardrails

- Do not invent missing fields. Leave `commute_minutes` null if not on the page.
- Do not present outputs as legal, mortgage, survey, or inspection advice.
- Always cite sources (e.g. "listing says…", "estimated from brief").
- Keep source URLs so the user can verify.
- If a site blocks access, skip it and move to another source.
- If discovery finds fewer than 3 good candidates, tell the user and suggest relaxing the brief (broader location, higher budget, fewer must-haves).

## If the `house-hunt` MCP server is not available

- Verify that `.mcp.json` exists at the repo root and contains the `house-hunt` server config.
- Try reloading the MCP server by running `uv run house-hunt serve` from the repo root in a terminal outside this session.
- As a fallback, use the `run-house-hunt` skill (the no-browser version) if you have listings to pass in.

## Example output format

```
## Smoke Test Results: 3-bed near Surbiton, budget £650k

### Buyer Profile
- Location: Surbiton, south west London
- Budget: £650,000
- Bedrooms: 3+
- Max commute: 45 min to Waterloo
- Must-haves: garden, quiet street
- Nice-to-haves: parking, good schools

### Ranked Listings (top 5)
1. Victorian semi, Surbiton [82/100] — £645,000 · 3 bed · 2 bath · Surbiton
   + Garden, quiet street
   - Estimated 38 min commute
   Source: https://www.rightmove.co.uk/...

2. Modern flat, Berrylands [71/100] — £580,000 · 3 bed · 2 bath · Berrylands
   + Garden, parking
   - Commute not listed (estimated ~40 min)
   ! No reference to quiet street in listing
   Source: https://www.zoopla.co.uk/...

### Comparison (Top 3)
[Side-by-side table of the top 3]

### Affordability (Top Match)
- Deposit (15%): £96,750
- Loan: £548,250
- Monthly: ~£2,800/month
- Assumptions: 5.25% annual rate, 25-year term. Not financial advice.

### Tour Questions for #1
- When was the property last updated? Any major renovations?
- Is the garden south-facing? Mature trees or established planting?
- What are the council tax band and annual rates?
- How far to Surbiton Station? Are there commute options to Waterloo?

### Offer Brief for #1
[Advice on offer strategy, not legal counsel]

### Boundary Notice
You are a buyer-side house-hunting assistant. [Full boundary text from the harness]

### Trace
[MCP tool returned trace path: .tmp/house-hunt-web-run-1234567890.json]
```
