# Dossier Builder — Research Plan

This is the concrete "where to go, how to get it, how much to trust it"
plan behind the person/organization templates in `templates/`. It's
informed by OSINT methodology, investigative-journalism backgrounding
practice, executive due-diligence research, and intelligence-community
source-credibility frameworks — sources cited throughout, 30+ distinct
sources across the areas below.

Scope boundary (per AJ, 2026-07-01): public professional-role
information plus broader public-record footprint (property, campaign
finance, other directorships). Never home address, family members, or
personal (non-official) social media.

## 1. Confidence scoring

Adapted from the **Admiralty Code / NATO STANAG 2511** two-axis system
(source reliability A–F × information credibility 1–6) — the standard
framework intelligence analysts use to grade sourced claims
([Wikipedia](https://en.wikipedia.org/wiki/Admiralty_code),
[SANS](https://www.sans.org/blog/enhance-your-cyber-threat-intelligence-with-the-admiralty-system),
[Blockint critical review](https://www.blockint.nl/intel-analysis/critical-review-of-the-admiralty-code/)).
Collapsed into a single 0.0–1.0 score for practicality, computed as:

```
confidence = source_tier_weight + corroboration_bonus
corroboration_bonus = 0.05 × (independent_corroborating_sources - 1), capped at +0.15
final = min(confidence, 0.98)
```

**Source tiers** (weight applied per claim, based on where it was found):

| Tier | Weight | Examples |
|---|---|---|
| 1 — Primary/official | 1.00 | `.gov` domains, official district/state website, court records, campaign-finance filings, official meeting minutes |
| 2 — High-credibility secondary | 0.85 | Ballotpedia, NCES, state report-card sites, FollowTheMoney/OpenSecrets, major national/regional news with editorial standards |
| 3 — Medium | 0.65 | Local news outlets, trade publications, self-published press releases (lower independence) |
| 4 — Low | 0.35 | Blogs, forums, people-search aggregators (Spokeo etc.), opinion pieces, unverified social posts |
| Excluded | — | Anonymous tips, single-source social-media rumor, AI-generated content, content behind a paywall we can't verify |

A single Tier-4 source alone can never reach 0.9 even with the
corroboration bonus (0.35 + 0.15 = 0.50) — by design, weak sourcing
can't be laundered into "confirmed" just by finding two blogs that
copied each other. **Only claims at ≥0.9 appear in the rendered
dossier.** Everything below stays in the underlying `crm_claims` table
(audit trail) but is omitted from the markdown output, per instruction.

Wikipedia is treated as Tier 2, not Tier 1 — useful for orientation and
often correct, but it's crowd-edited, not authoritative; a Wikipedia
claim should ideally be corroborated before counting toward 0.9 alone.

## 2. Search engine strategy

Different engines index meaningfully different portions of the web —
even at scale, overlap between major engines' result sets has
historically been as low as ~11%
([search-engine-indexing research](https://en.wikipedia.org/wiki/Search_engine_indexing),
[academic search overlap study](https://arxiv.org/pdf/1701.02617)).
One engine's page 1 can be another's page 4. Engines to query in
parallel per search (already partially built this session in
`esb/crm/connectors.py`):

1. **DuckDuckGo** (HTML endpoint, no key) — already integrated
2. **Bing** (HTML scrape, no key) — already integrated
3. **Mojeek** (HTML scrape, no key, independent index — not a Bing/Google reseller) — already integrated
4. **Brave Search API** — free tier (2,000 queries/month), needs an API key (AJ: let me know if you want me to request one, or I'll gate this connector to no-op without a key, same pattern as OpenRouter)
5. **Startpage or Yandex** as a 5th — Startpage proxies Google results but ToS-restricts scraping; Yandex has historically been more permissive but I'd want to confirm current robots.txt before relying on it. Recommend starting with 4 solid engines and only adding a 5th if coverage gaps show up in practice, rather than integrating a shakier source just to hit a number.

**Depth**: page through at least 10 result pages per engine per query
(not just the first 1-2) — deep pagination surfaces older/less-SEO'd
content that's often exactly the kind of thing (old board minutes,
local news that didn't rank) a dossier needs and a quick Google search
misses.

## 3. Wayback Machine / archive.org

Free, no key, no rate-limit concerns at our volume. Used for:
- Any official bio/staff page that 404s or has clearly been edited —
  check the CDX API (`web.archive.org/cdx/search/cdx?url=...`) for
  snapshot history, diff the earliest available version against
  current
- District strategic-plan pages, board pages — same treatment
- News articles that have been taken down or altered

This is one of the highest-value techniques in modern investigative
work — 100+ news stories a month now cite Wayback-recovered material
to reconstruct timelines or catch quiet edits
([Internet Archive blog, "9 Ways Web Archives are Used in Digital Investigations"](https://blog.archive.org/2026/02/02/follow-the-changes/),
[GIJN Wayback Machine tips](https://gijn.org/resource/tips-for-using-the-internet-archives-wayback-machine-in-your-next-investigation/)).
Note some major news sites now block the Wayback crawler going forward
([Forbes coverage](https://www.forbes.com/sites/anishasircar/2026/04/14/why-major-news-sites-are-blocking-the-internet-archives-wayback-machine/))
— for those, existing already-archived snapshots are still usable, we
just can't force new ones.

## 4. Section → source mapping

### Person dossier

| Section | Primary sources | Method |
|---|---|---|
| Current Role | District official website, state ed department directory | Direct fetch |
| Career History | LinkedIn (via search-engine snippet only — see §5), Ballotpedia, prior-employer press releases, news archive | Search + fetch, never direct LinkedIn scrape |
| Education | Ballotpedia, official bio page, news profiles | Search + fetch |
| Track Record | State report card (superintendent tenure correlation), board meeting minutes/votes, official press releases | Direct fetch + search |
| Public Statements | News archive, official district press releases, YouTube/meeting recordings (title/description only, not audio transcription in v1) | Search |
| News Coverage Timeline | News search across all engines, local outlet sites directly | Search, deep pagination |
| Areas of Scrutiny | News search (adversarial-term query, same term list already built for Newsworthy Scraper), court records search, Ballotpedia controversies section | Search, deep pagination |
| Campaign Finance | FollowTheMoney.org, OpenSecrets (state/local coverage varies), state disclosure portal (via `followthemoney.org/resources/state-disclosure-agencies`) | Direct fetch/search |
| Professional Network | Ballotpedia, LinkedIn snippets, professional association member directories (AASA etc., where public) | Search |
| Public Financial/Property | County assessor sites (per-county, no unified free API — best-effort structured search query per county name), business-entity search (state Secretary of State sites are free and unified per-state) | Search, direct fetch where a specific county/state is known |
| Historical Note | Wayback Machine CDX API | Direct API |

### Organization (district) dossier

| Section | Primary sources | Method |
|---|---|---|
| Basic Profile | NCES Common Core of Data (CCD) — `nces.ed.gov/ccd` | Direct fetch/API |
| Governance Structure | District official website (board page), Ballotpedia | Direct fetch |
| Recent Leadership History | News archive, district board-meeting archive, Ballotpedia election results | Search + direct fetch |
| Financial Health | NCES School District Finance Survey, local news (bond measure coverage) | Direct fetch + search |
| Academic Performance | State-specific report card site (mapped per state — see `ed.gov`'s state report card directory) | Direct fetch |
| Demographic/Enrollment Trends | NCES CCD (multi-year) | Direct fetch/API |
| Strategic Priorities | District official website (strategic plan page, if published) | Direct fetch |
| Areas of Scrutiny | News search (adversarial terms), state oversight/takeover announcements | Search, deep pagination |
| Media Coverage Timeline | News search | Search, deep pagination |
| Community Context | Local news, union website (if public), community org sites found via search | Search |
| Historical Note | Wayback Machine | Direct API |

## 5. What we deliberately don't scrape directly

- **LinkedIn**: direct scraping is a LinkedIn User Agreement violation
  even though not a CFAA crime post-*hiQ v. LinkedIn*
  ([hiQ case background](https://phantombuster.com/blog/linkedin-automation/is-linkedin-scraping-legal/)) —
  LinkedIn actively sues scrapers and shut down at least one
  scraping-API vendor's entire product in 2025
  ([Nubela/Proxycurl case](https://nubela.co/blog/is-scraping-linkedin-legal-in-2026/)).
  We surface LinkedIn URLs and title/snippet text as they appear in
  search engine results (that's the engine's own indexing, not us
  scraping LinkedIn) and let the practitioner click through themselves.
  Same treatment for any other site whose robots.txt or ToS
  meaningfully restricts automated access — matches the CGCS scraper
  precedent already built this session (checked robots.txt before
  building).
- **Court records (PACER)**: PACER charges per-page fees and requires
  an account; not "freely available" in the sense meant here. County
  court websites vary wildly and aren't worth building 3,000+
  county-specific scrapers for. v1 relies on news coverage of lawsuits
  (which reliably covers anything a practitioner would care about) —
  direct court-record lookup can be a manual follow-up step, not
  automated.
- **County property records**: same fragmentation problem (every
  county has its own site/format). v1 does a best-effort structured
  search query (`"{name}" property records {county} {state}`) rather
  than building per-county scrapers — this surfaces the right site to
  click through to, without pretending we have unified coverage.

## 6. Sources consulted for this plan

OSINT methodology: [OSINT Journalism guide](https://www.osint.industries/post/osint-journalism-our-guide-to-osint-for-journalists), [ShadowDragon OSINT guide](https://shadowdragon.io/resources/what-is-osint/), [Media Helping Media](https://mediahelpingmedia.org/advanced/open-source-intelligence-osint-in-journalism/), [National Press Foundation](https://nationalpress.org/topic/osint-basics-any-journalist-can-use-now/), [Moody's OSINT overview](https://www.moodys.com/web/en/us/insights/compliance-tprm/open-source-intelligence-osint-types-tools-and-methods.html)

IntelTechniques / Bazzell / Bellingcat: [inteltechniques.com](https://inteltechniques.com/), [OSINT Navigator for Investigative Journalists](https://bird.tools/wp-content/uploads/2022/03/OSINT.pdf)

Admiralty Code: [Wikipedia](https://en.wikipedia.org/wiki/Admiralty_code), [SANS Institute](https://www.sans.org/blog/enhance-your-cyber-threat-intelligence-with-the-admiralty-system), [ResearchGate NATO AJP-2.1 table](https://www.researchgate.net/figure/NATO-AJP-21-Source-Reliability-and-Information-Credibility-Scales_tbl1_328858953)

IRE/GIJN backgrounding: [GIJN Introduction to Investigative Journalism: Backgrounding](https://gijn.org/resource/introduction-investigative-journalism-finding-sources-backgrounding/), [GIJN Toolbox: Backgrounding People and Companies](https://gijn.org/2018/11/07/gijn-toolbox/), [Center for Cooperative Media IRE checklist](https://centerforcooperativemedia.org/ire-checklist/)

Campaign finance / education databases: [OpenSecrets](https://www.opensecrets.org/), [FollowTheMoney](https://www.followthemoney.org/), [FollowTheMoney state disclosure agencies](https://www.followthemoney.org/resources/state-disclosure-agencies), [NCES CCD](https://nces.ed.gov/ccd/), [NCES state report card directory](https://www.ed.gov/birth-to-grade-12-education/elementary-and-secondary-education/where-can-i-find-my-state-report-card-website)

Wayback Machine: [Internet Archive blog — digital investigations](https://blog.archive.org/2026/02/02/follow-the-changes/), [GIJN Wayback tips](https://gijn.org/resource/tips-for-using-the-internet-archives-wayback-machine-in-your-next-investigation/), [Forbes — sites blocking Wayback](https://www.forbes.com/sites/anishasircar/2026/04/14/why-major-news-sites-are-blocking-the-internet-archives-wayback-machine/)

Search engine coverage: [search overlap study, arXiv](https://arxiv.org/pdf/1701.02617), [search engine indexing, Wikipedia](https://en.wikipedia.org/wiki/Search_engine_indexing)

OSINT Framework / tools: [osintframework.com](https://osintframework.com/), [awesome-osint](https://github.com/jivoi/awesome-osint)

LinkedIn scraping legality: [hiQ v. LinkedIn analysis](https://phantombuster.com/blog/linkedin-automation/is-linkedin-scraping-legal/), [Nubela/Proxycurl 2025 shutdown](https://nubela.co/blog/is-scraping-linkedin-legal-in-2026/)

Executive/due-diligence report structure: [Infortal executive due diligence](https://infortal.com/solutions/executive-due-diligence/), [iprospectcheck executive background check guide](https://iprospectcheck.com/executive-background-check/), [La Piana nonprofit due diligence checklist](http://www.lapiana.org/wp-content/uploads/2020/06/Due-Diligence-Checklist.pdf), [Stanford PACS nonprofit vetting chapter](https://pacscenter.stanford.edu/wp-content/uploads/2020/07/due_dilligence_08.pdf)

School board records / property records: [school board meeting minutes legal requirements](https://www.diligent.com/resources/blog/what-legal-requirements-school-board-meeting-minutes), county assessor examples ([Maricopa](https://mcassessor.maricopa.gov/), [Spartanburg](https://www.spartanburgcounty.gov/288/Assessor-Property-Records-Search))

## 7. Open questions for AJ before implementation

1. **Brave Search API key** — want me to sign up for the free tier (2,000 queries/month, needs an account), or start with the 4 keyless engines and revisit?
2. **State report-card site mapping** — there's no single federal database with live test-score data (NCES CCD covers enrollment/finance, not achievement); each state runs its own report-card site. I'll build the mapping for whichever states you actually work in first rather than trying to hardcode all 50 up front — which states should I prioritize?
3. Templates/rubric above — good to build against, or changes first?
