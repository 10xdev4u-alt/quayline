# Market, competition, and the economics

Research date 2026-09-27. Sources inline. Vendor-published figures say so.

## The pool, and it is smaller than it looks

| Line | Value | Source |
|---|---|---|
| US import TEU 2026 forecast | 25.7M | NRF Global Port Tracker, 2026-09-10 |
| Three year range | 25.4M to 25.7M, within 1.2 percent | Same |
| Waterborne import TEU, 12 months post tariff change | **minus 4.3 percent** | Descartes Datamyne via FreightWaves, 2026-09-23 |
| Containers incurring D&D | about 15 percent | Freightos 2025, third party, unverified |
| Average D&D invoice | about 600 dollars | ShippingRates 2026, third party, unverified |
| US D&D billing pool | about 2.3 billion dollars a year | Derived |
| Disputable share | 6 to 10 percent | Eller, vendor published |
| Recovery on disputable | 65 to 80 percent | Eller, vendor published |
| US D&D recoverable pool | about 130 million dollars | Derived |
| **Fee pool at 25 percent contingency** | **about 32 million dollars** (26 to 39) | Derived |

BlueCargo, the category leader, with Home Depot, Michelin, Kohler and GE
Appliances, has raised about 14 to 15 million dollars and is still seed-stage per
PitchBook. The arithmetic is consistent with that.

**D&D is a good niche business and a bad standalone venture outcome.**

## D&D is 3 to 15 percent of what the same data can reach

| | |
|---|---|
| Accessorials as share of a mid size shipper's freight spend | 15 to 30 percent trucking, 20 to 30 percent LTL |
| Total freight audit recoverability | **2 to 7 percent of freight spend**, Loop |
| D&D as a share of the recoverable opportunity | **about 3 to 15 percent** |
| D&D contribution to recoverable dollars | **0.09 to 0.3 percent of freight spend** |

The other 85 to 97 percent is base rate, class and weight, fuel, zoning and
duplicates. We already hold the container, invoice and contract data needed to go
after it.

## The non-accessorial categories, by yield

| Category | Error rate | Disputability | Evidence burden |
|---|---|---|---|
| **Fuel surcharge calculation error** | **12 to 18 percent**, the highest frequency error class in trucking | High | **Low.** The rate table and the DOE index are both public and deterministic |
| **Rate misapplication**, tariff fallback instead of contract rate | | Very high. "The single largest source of overcharge dollars in most programs", FreightPOP | **Low.** We hold the contract and the quote |
| Duplicate invoices, especially EDI | | Very high | **Lowest.** Pure deduplication |
| Dimensional, manifested versus billed weight, reclass | | High | Medium |
| Residential on a commercial address | 3 to 6 percent billed on commercial | High | Low |
| Liftgate on a dock location | 5 to 8 percent | High | Low |
| Inside delivery not requested | 4 to 7 percent | High | Low |
| Redelivery without documented first failure | 5 to 8 percent | High | Low |
| Limited access on a standard commercial delivery | 3 to 5 percent | High | Low |
| Service failure credits | 5 to 10 percent of deals miss SLA | High | Low, but a 15 day parcel window |
| Truck detention | 8 to 12 percent billed without valid occurrence | 55 to 70 percent win | **High.** Gate log plus GPS |
| Lumper | duplicate billing when the shipper already paid at the dock | 40 to 60 percent | Medium. The receipt is often lost |
| Ocean D&D | 6 to 10 percent of billing disputable | 65 to 80 percent | **Highest.** Terminal availability |

**D&D has the highest per-dispute dollar value and the worst evidence economics.**
A product that does only D&D leaves 85 to 97 percent of the recoverable dollars
untouched, and a D&D-only embed gets replaced in two quarters.

## Who is actually in this

Four categories, with different economics. Only the first is our competitor.

| Category | Players | Files disputes | Terminal data |
|---|---|---|---|
| **A. D&D recovery specialists** | BlueCargo, HarborClaim, Unwaived, 3drens, DemurrageIQ, Last Rev, Eller, Trans Audit | **Yes** | BlueCargo yes, others mostly no |
| B. TMS audit modules | Loop, Freehand, FreightPOP, Navix, Transflo | Software generated. Loop and Freehand claim autonomous | No. Ingest from CargoSmart, p44, FourKites |
| C. Visibility | project44, FourKites, CargoSmart, Descartes, CargoPilot, Windward | No | Descartes and Maersk yes, resold not re-sourced |
| D. Carrier-side recovery | Demurly, Dwell, CLAWBACK, HappyRobot, Windward | Yes, on the carrier's behalf to collect | No |

### BlueCargo, the one to beat

Founded 2018, YC S18. Alexandra Griffon and Laura Theveniau, both ex terminal ops
and stacking algorithm engineers. 11 million dollars led by Soma Capital and Left
Lane in February 2023, about 15 million total. Covina, California. Pivoted to
post-audit of historical invoices.

Proof: 5.2 million dollars recovered, 85 percent of disputed charges, Forrest
Logistics saved over 5 million in 2022, GE Appliances voided 1.55 million in D&D
fees with payback described as "a couple of weeks."

Enterprise validation on a TPM26 panel in March 2026 with Home Depot, Michelin and
Kohler. **Michelin and Kohler ran their own audit on BlueCargo's data before
trusting a single number.** That is the credibility bar. One reference clears it.
Without one, we do not.

### The pricing model is under live attack

**Freehand.ai** exited stealth at Manifest 2026, fully agentic, and **explicitly
refuses a percentage of savings** to undercut incumbents on price. 50 billion plus
dollars of freight payments a year. 12 to 14 week go live. SOC 2 Type II.

**Loop** raised 210 million dollars. Its Exception Agent "resolves carrier
disputes without a human reviewing the queue." Its own framing attacks the model
directly: "many servicers' fees are based on a percentage of found savings, they
have no incentive to fix the underlying cause."

A freight operator in June 2026: "AI just made the 30 to 50 percent contingency
fee on freight audit obsolete."

**The only defense is a published, third-party verified recovery rate.** That is
why validation comes before code in this project.

### Contingency pricing sits below the general audit band

| Model | Band |
|---|---|
| Carrier-side collection | 3.5 to 25 percent. Demurly at 3.5 percent plus a dollar per record |
| **D&D specific** | **20 to 35 percent** |
| General freight audit | 25 to 50 percent |
| Per invoice | 1 to 5 dollars |
| Freight payment service market price | 9.38 dollars per transaction, IBISWorld 2026 |

**The product requiring the most expensive data acquisition prices below the
category requiring the least.** That is an opportunity if the recovery rate is
provable, and a trap if it is not.

Carrier-side contingency is 10 times thinner because the carrier's alternative is
doing nothing. Demurly's model works because the carrier **wins** on collection,
at 90 percent against a 62 percent industry rate. That is a collections business,
not a dispute business.

## The evidence standard, and who owns it

The strongest evidence class in the domain is the receiver's own gate log.

> "If the receiver's gate log says one time and the carrier's bill says another,
> the receiver's log wins every time." Eller, 2026-05

It lives in the shipper's yard management system or on a clipboard, the shipper
owns it, and nobody has it. Kaleris already sells access to that layer for 680
customers.

The other strong class is the terminal's own operating system event history, which
APM Terminals exposes through an API and most terminals do not.

**The diagnostic question that beats any quality of earnings report:** when did
the owner last take a real vacation. If it was a weekend two years ago, the owner
is the business.

## Concentration and the ceiling

| Line | Value |
|---|---|
| Mid size shipper freight spend | 50 million dollars |
| Total recoverable overcharges | 1.5 to 3.0 million dollars |
| Fee at 30 percent contingency | **450 thousand to 1.05 million dollars a year per account** |
| Analyst cost to do it manually | 45 to 95 dollars an hour, days to weeks per dispute |

- **10 million dollars of ARR needs 33 million dollars of annual recoveries**
- at 5 percent net recovery on audited spend, that is **660 million dollars of audited freight spend under contract**
- which is **about 2.5 percent of the US market**

**Consequences to design around:**

1. Top one to three concentration above 50 percent is near certain below 5 million
   dollars of ARR. Do not plan for a diversified book before 10 million.
2. Cost to serve is the binding constraint, not demand. Beyond 2 to 4 full time
   dispute operations people per 750 thousand dollar account, the model breaks.
   Drive operating cost per dollar recovered **below about 15 percent**, which
   needs full automated coverage of the disputable population. Last Rev and
   Freehand both claim that. Neither has shown it.
3. **There is no organic path from a 5,000 container threshold to 10 million of
   ARR.** This is a specialist position with an embed, or an acquisition.

## The exit, honestly

- **3.9 times is the median** confirmed profit multiple, Acquire.com 2025,
  unchanged across 2023, 2024 and 2025. The typical outcome is no multiple
  expansion. Returns come from cash flow and growth over five to seven years.
- **About 32,000 unsold companies worth 3.8 trillion dollars sit in private equity
  portfolios**, average hold about seven years, per Bain. Large private equity has
  spent two decades buying small services assets and cannot sell them.
- **Small business multiples fell to 4.3 times in 2025 from 6.7 times in 2017.**
  The trailing twelve month multiple hit 3.3 times in Q2 2025, a 12 quarter low.
- **67 percent of advisors report AI has not moved valuations**, IBBA Q1 2026.
- **General Catalyst and Thrive both plan permanent hold.** Thrive is
  Berkshire-style with minority stakes retained. General Catalyst's stated
  destination is the public market.
- **Kaleris has three deals under letter of intent and needs roughly 500 million
  dollars of revenue before an Accel-KKR exit.** A company under visible pressure
  to hit a revenue number by acquisition is the most likely acquirer and the most
  likely acqui-hire.

## Outcomes in order of probability

1. A good, durable small business. 250 thousand to 1 million dollars of ARR at 40
   to 60 percent gross. **Most likely.**
2. An acqui-hire or bolt-on into Kaleris, Descartes, or a TMS.
3. A real platform, only through the embed, and only over a decade.

A venture outcome is not on the list. This is a specialist position with an
embed.
