# Carrier tariff data

Research date 2026-09-27. Figures transcribed from carrier tariff PDFs. Where a
carrier did not publish something, it says so rather than carrying a guess.

## The shape of the problem

The 11 carrier by 9 gateway grid does not exist as public data. No amount of
searching produces it. What actually exists:

| Carrier | Publishes at | Granularity |
|---|---|---|
| **Hapag-Lloyd** | per terminal | Finest in the industry. Reference implementation |
| **Maersk** | cluster | default, Newark NYC, Miami PEFLA, Philadelphia, rail ramps, Hueneme |
| **CMA CGM** | national plus gateway exceptions | One US tariff with a California carve-out and a Baltimore block |
| **MSC** | marine terminal operator schedule | No US import demurrage tariff at 8 of 9 major gateways |
| **ONE** | calculator plus dated advisories | Excellent policy archive, no static rate PDF |
| **ZIM** | port tables plus calculator | Per port rate to tier mapping did not survive extraction |
| **Evergreen** | pointer only | Rule 036-I01 import, 036-E01 export, attachments not obtained |
| **HMM** | rule numbers only | Rates sit behind a JavaScript form |
| **COSCO** | dispute policy only | Rate tables are not on the public site |
| **Yang Ming** | not located | One of the nine FMC data submitters, so a tariff exists |
| **PIL** | not located | Not an FMC data submitter |

**The dominant acquisition problem is marine terminal operator schedules, not
carrier tariffs.** Evergreen's terminal directory is a free, citable,
carrier-published map of exactly those, with the location codes that appear on
invoices and gate tickets.

## The rule that repriced the category

Since August and September 2024, every major carrier grants free time in
**working** days and charges post-free-time in **calendar** days. The allowance
did not change. The unit did.

| Date | Carrier | Change |
|---|---|---|
| 2023-06-01 | ONE | Over-days switched to calendar basis |
| 2023-10-01 | ONE | Free time counted only when the gate is open |
| 2024-07-01 | CMA CGM | Already calendar-day. Predates the FMC rule |
| 2024-08-08 | **Maersk** | Calendar-day charging, US wide, no exceptions |
| 2024-09-01 | **Hapag-Lloyd** | Calendar-day charging, US, with a California working-day carve-out and an unscheduled shutout exclusion |
| 2024-09-09 | **ONE** | Calendar-day charging, US, gate-open basis for California only |
| 2025 | CMA CGM | Rate escalation, free days unchanged. Tier 1 $270 to $285, top tier $350 to $385 |
| 2026-01-01 | Maersk | Newark all tiers +$20, operating reefer +$40. Miami PEFLA tier 1 +$20. Philadelphia +$20. Detention +$10 all tiers, free days unchanged |
| 2026-02-22 | CMA CGM | Baltimore tier 1 $285 to $305, matching an independent Maersk East Coast +$20 in the same month |
| 2026-04-01 | **ONE** | New charge: import line demurrage at inland rail locations. $185 dry, $285 operating reefer |
| 2026-06-20 | Maersk | Current import demurrage tariff |
| 2026-09-01 | ONE | Savannah export operating reefer gets its own early receiving date |

Do not put CMA CGM in the 2024 compression cohort. It was already converted. And
do not conflate free time compression with rate inflation. They are two separate
rules and the taxonomy keeps them apart.

## Hapag-Lloyd, the reference implementation

Free time is always working days, from DOD for demurrage and DOI for detention.
Notation: `DOD + 4WD` means the discharge day is day zero and the fourth working
day after it is the last free day. `3CD` is three calendar days, `3WD` is three
working days.

### The California trap

**Hapag charges California terminals in working days and every other gateway in
calendar days.** The same table shows it. A weekend in California accrues
nothing. The same weekend in Savannah costs two days at the tier rate. It is
invisible unless you read the day-unit column.

| Terminal | Gateway | Regular dry free time | Tier unit |
|---|---|---|---|
| Savannah GA, USSVNG | calendar | DOD + 4WD | 3CD |
| Los Angeles APMT, USLAXB | **working** | DOD + 4WD | 3WD |
| Los Angeles Trapac, USLAXTP | **working** | DOD + 4WD | 3WD |
| Long Beach all, USLGB | **working** | DOD + 4WD | 3WD |
| New York all other, USNYC | calendar | DOD + 4WD | 3CD |
| Houston, USHOU | calendar | DOD + 4WD | 3CD |
| Oakland OICT, USOKL | **working** | DOD + 4WD | 3WD |
| Charleston, USCHS | calendar | DOD + 4WD | 3CD |
| Baltimore SeaGirt, USBAL | calendar | DOD + 4WD | 3CD |
| Seattle SSA, USSEA | calendar | DOD + 4WD | 3CD |

Savannah 40 foot dry: free 1 to 4, then $265, $350, $515. New York 40 foot dry:
free 1 to 4, then $625, $970, $1330. New York regular reefers are the most
expensive non-reefer block in the dataset, and New York operating reefers run
$1105, $1480, $1800.

### Four parallel detention schedules

Geography crossed with haulage mode. Same container, same day, four different
legal rates.

| Geography | Haulage | Equipment | Free time | Unit |
|---|---|---|---|---|
| US excluding California | Carrier Haulage | regular | DOI + 4WD | 3CD |
| US excluding California | Carrier Haulage | reefer operating | DOI + 3WD | 3CD |
| **California** | Carrier Haulage | regular | DOI + 4WD | **3WD** |
| **California** | Carrier Haulage | reefer operating | DOI + 3WD | **3WD** |
| US excluding California | Merchant Haulage | regular | DOI + 4WD | 3CD |
| US excluding California | Merchant Haulage | reefer operating | DOI + 3WD | 3CD |

**Haulage mode is a required input**, read from the Carrier Haulage or Merchant
Haulage checkbox on the bill of lading. Guessing it is a 15 to 20 percent error
before any dispute. Hapag errored here once: FMC Docket 22-03 found Hapag
charged for 11 containers without offering a return location, at $160 to $1845
each.

### Published waiver conditions

Hapag will not charge line demurrage or marine terminal storage for import truck
carrier haulage containers through US ports, provided all of:

1. Delivery order submitted 5 days before vessel arrival
2. Customs clearance with no regulatory restrictions 5 days before free time
   expires
3. Credit or freight payment received
4. Original bill of lading received
5. Merchant facility available when the trucker calls, with an appointment no
   later than 48 hours after Hapag's motor carrier contacted you

Rules D06 (demurrage waiver) and D07 (detention waiver), valid from 2022-07-08.

### Customs hold, an express clock stop

Verbatim from the May 2026 D&D Guide:

> "If the container is held inside the Marine or Rail Terminal, then the Line
> Demurrage clock begins at the release date. The hold and release dates and all
> days in between are not counted towards free time days... the customer is
> responsible for any storage charges imposed by the terminal operator during the
> hold days."

Outside the terminal or at a customs warehouse, the detention clock begins at
release and free time starts the day after.

> **CORRECTION, 2026-09-27, issue 16.** Three things, verified against the May 2026 and
> October 2024 editions of the guide, both of which carry the language identically.
>
> **The restart anchor is locus dependent and asymmetric.** The general sentence stops both
> the demurrage and the detention clock. The restart sentence does not follow that symmetry.
> Inside the terminal the guide names the **demurrage** clock. Outside the terminal or at a
> customs warehouse it names the **detention** clock. The summary line above, "a customs hold
> pauses both clocks", is right about the stop and wrong about the restart.
>
> **The rule is conditioned on fault.** "for no fault of the customer". A hold the customer
> caused is outside the policy and no clock stops. This condition was missing here.
>
> **Pass-through charges are collected too.** Where Hapag collects terminal charges on the
> operator's behalf, it invoices them onward, so a hold can be charged twice.
>
> The quote above is also abridged, with an ellipsis, so it was not verbatim. The full
> paragraphs are transcribed in `tariffs/hapag.py`.

### The day-counting asymmetry

Bank holidays and shutout days are excluded from free time, and free days are
extended for them. After free time expires, charges are on a calendar basis, but
**unscheduled** shutouts are still excluded while **scheduled** closures are
charged. Model that as typed closures, not a boolean.

## Maersk, cluster granularity

| Cluster | Equipment | Free | Tiers per container per calendar day |
|---|---|---|---|
| Default | dry | 4 | 1-4 free, 5-8 $300, 9-13 $345, 14+ $395 |
| Default | reefer operating | 2 | 1-2 free, 3-5 $490, 6-9 $590, 10+ $640 |
| Newark NYC | dry | 4 | 5-8 $390, 9-13 $500, 14-33 $640, 34+ $745 |
| Newark NYC | reefer operating | 2 | 3-5 $745, 6-8 $910, **9+ $1165** |
| Miami PEFLA | dry | 4 | 5-8 $360, 9-13 $455, 14-33 $570, 34+ $705 |
| Miami PEFLA | reefer operating | 2 | 3-5 $655, 6-8 $800, 9+ $1030 |
| Philadelphia | dry | 4 | 5-8 $320, 9-13 $365, 14+ $415 |
| Rail ramps | dry | 3 | 4-7 $190, 8-11 $250, 12+ $280 |

$1165 is the highest single rate in any carrier import schedule we verified.

### The price calculation date lock

> "Application: The free time & charges applied will be those in place on the
> **origin price calculation date (PCD)**"

Rates and free time are pinned to the date of loading, not the invoice date. A
January 2026 rate rise does not reach a container loaded in December 2025. This
is a free win on misapplied-rate disputes and nobody exploits it.

### Working days are Monday to Saturday

> "Working Day basis defined as any day a gate is open for container pickup
> **Monday - Saturday**. Partial day closures are considered as a full working day
> and count towards freetime. In the event a terminal closes on a day due to lack
> of appointment demand, that day shall be considered a working day for containers
> a party had an opportunity to make a timely appointment for, **but chose not to
> do so**. If a party made an appointment for a container but the terminal was
> closed, then that date shall not be considered a Working Day with respect to
> that container."

Sunday is the only weekly closure. A closure for lack of appointment demand is
chargeable to you. A closure on a day you held a booking is not a working day.

### The tariff disclaims itself

> "In the event of any discrepancies between the below and our public tariff, the
> public tariff prevails."

Cite the tariff, not the summary sheet.

**Maersk detention is UNVERIFIED.** The December 2025 advisory gives deltas only,
plus 10 dollars per tier at all US locations with free days unchanged. Do not
model detention from the advisory.

## CMA CGM

Already calendar-day billing before the FMC rule, so it is not in the 2024 cohort.

### Demurrage is a bundle

> "In the United States, 'Demurrage' issued at water port locations **includes both
> storage & demurrage charges**, and is applicable to all containers, regardless of
> ownership by merchant or carrier."

You cannot dispute a portion of the line as storage versus demurrage. Only the
whole line.

### The California carve-out

> "**California Terminals only** - No demurrage will be assessed during days for
> which a Terminal is closed, including weekends or holidays, **even when
> demurrage free time has been exceeded**."

The most protective regime of any major carrier. Compare Hapag California, which
uses working-day blocks, and Maersk, which has no CA carve-out in the D&D sheet.
Same container, same days, three carriers, three answers.

### Rates

US standard: 4 free working days, then $285, $345, $385. Baltimore from
2026-02-22: 4 free, then $305.

Reefer: 2 free days demurrage, 3 free days detention, $500 to $600 per day.
Against dry at 4 days and $285, that is roughly a 4 times effective cost
multiplier. Recovery dollars concentrate here.

Rail ramps: **10 free working days demurrage**, by far the most generous
allowance we found, against 3 to 4 at ocean terminals. And the inverse day-unit
pattern: demurrage free time in working days, detention free time in calendar
days.

## MSC, the structural problem

> "Each terminal will bill and collect their own demurrage according to their
> published tariff, except for the terminals listed below. For the following
> terminals **MSC will pass through terminal demurrage charges at cost**."

Fifteen terminals: Garden City Savannah, North Charleston, Wando, Napoleon Avenue,
LBCT, Trapac Oakland, VIT, NIT, Portsmouth, Richmond, Barbours Cut, Bayport,
Wilmington NC, Husky Tacoma, Trapac LAX.

That covers 8 of the 9 major gateways. **For MSC at those gateways the
controlling instrument is the terminal operator's schedule, not any MSC
tariff.** You cannot build an MSC rules engine from carrier data. Getting this
wrong produces plausible, silent, wrong answers.

**Two invoices are common on MSC lanes**, terminal storage direct to you plus
MSC line D&D. Deduplicate before disputing or you double-count and lose
credibility.

**Label inversion.** MSC titles its "IMPORT DETENTION" for equipment **inside**
the marine terminal. That is demurrage to everyone else and to 46 CFR 545.5.
Normalize on the physical locus in the charge narrative, never on the line item
title.

MSC's only direct US import demurrage tariff is Port Everglades: 4 working days
free, 20 foot $65, 40 foot $110.

MSC's clock: "ALL TERMINALS: Free time will start the **first working day after
individual container discharge**." Discharge-based, not availability-based, and
per container rather than per vessel.

## ONE, the only availability-keyed carrier

| Effective to | Effective from | Clock start | Verbatim from ONE |
|---|---|---|---|
| 2023-02-26 | before | first full day after vessel **discharge** | VERIFIED, `us.one-line.com/DemDetPre2272023` |
| 2024-09-08 | **2023-02-27** | **UNVERIFIED, text not held** | 560-day gap, not interpolated |
| 2026-03-31 | 2024-09-09 | next full **working** day after made **available** | VERIFIED, `us.one-line.com/DemDetPre11032025` |
| present | 2026-04-01 | first full day when the container **is available** | VERIFIED, `us.one-line.com/demurragedetention` |

> **CORRECTION, 2026-09-27, issue 23.** This table was wrong twice, in ways that
> mattered.
>
> The second row dated the availability-keyed language to **2025-11-02**. That is the date
> of a different advisory. **2025-11-03 was the change to the default payer for export
> demurrage and detention**, and the ONE page carrying the clock language is *titled* for
> that later policy while dating itself **2024-09-09** in its own disclaimer. The table had
> picked up the default payer advisory date and attached it to the clock change.
>
> There is also a **560-day gap, not none**, running **2023-02-27 to 2024-09-08**. We do
> not hold the text of ONE's inbound demurrage clock for that window. The regime before it
> is discharge-based and the regime after it is availability-based, so this is a window
> where we cannot say which clock applied. It covers the last ten months of 2023 and the
> first eight of 2024, and a 2024 charge is often still inside a live dispute window. It is
> marked `UNVERIFIED` in `tariffs/one.py` and is not interpolated, because the two candidate
> answers disagree about the thing the whole dispute rests on.
>
> The issue predicted this gap would end 2024-05-27, the OSRA effective date, which would
> have made it 456 days. It is 104 days longer than that, and the extra 104 days are the
> interval between the regulation taking effect and the carrier implementing it.
>
> The 2023-02-27 boundary is also narrower than this table implied. ONE's advisory for that
> date concerns **outbound** demurrage and the Demurrage Free Receiving Date, not the
> inbound availability clock. The table read it as the start of a clock change.

ONE and MSC are on opposite sides of the availability question **in their own
published tariffs**. That is the cleanest available evidence that it is a
contract-term question rather than settled doctrine.

ONE's published invoice schema is eight fields, and field 1 is "Container
Availability: Date the terminal advises the container is available for pickup".
Compare it against the start date of the chargeable days. If demurrage is charged
from a date earlier than the availability date ONE itself certified, that is a
direct 541.6(a) and (b) accuracy and sufficiency failure. **This needs no external
data and it is the most automatable check in the category.**

ONE's partial-shift rule: a closure where the first shift is open and the second
is closed counts as a **full** working day, and as a full **billable** day if free
time has expired.

ONE also issues post-pull demurrage invoices routinely, because it only collects
demurrage prior to release at eModal facilities. That is a 541.6(d) dispute
channel fact and an argument that no payment incentive existed at the gate event.

**ONE's export default payer is UNVERIFIED.** Two tables both dated effective
2025-11-03 disagree, one saying Contract Party and one saying Shipper. Import is
safe: both say Consignee.

## ZIM

Detention free time begins on the day of **interchange**. Rail demurrage free time
begins the **day following discharge**. Two different triggers in one tariff,
which confirms there is no industry norm.

Charge days are calendar including weekends and holidays, for Standard service.
**Expedited and Fast services are calculated in working days.** Service string is
a required input.

Rail demurrage is carrier-only. Rail operators invoice storage separately. Same
double-invoice structure as MSC.

ZIM's calculator disclaims itself: "the final issued invoice shall prevail and
supersede any prior calculations or displayed amounts."

## HMM

Its own demurrage definition concedes the point:

> "Demurrage - The charge related to the use of the equipment, and **compensatory
> against Terminal land use cost (Storage)**."

That admission supports a duplication challenge where the terminal also bills
storage directly, and it engages 541.6(e)(2).

"Detention for Canceled Booking: **No free time is applicable** to canceled
booking and Detention will be invoiced." Zero free time is a distinct case worth
its own check.

## COSCO

Its own FMC answer, Docket 24-01, sets the lowest evidence bar in the category:

> "a trucker or a consignee may obtain a waiver, credit, or refund of per diem for
> a particular day simply by providing **screen shots (or other corroboration)
> showing that the relevant facility(ies) were not available** - including by
> reason of closure, lack of appointments and/or dual move requirements,
> **without even asserting that it actually tried to pick up or return the
> container on that day**."

Worth citing in a charge complaint.

COSCO's published dispute window is **7 days after out-gate** for import
demurrage, against 541.8(a)'s 30 days from invoice issuance. Whether that is a
permissible policy or a non-compliant restriction is genuinely unresolved. Mark
it `arguable`. File on the earlier of the two so both are satisfied.

COSCO wants the **Equipment Interchange Receipt**. That single artifact resolves
the detention clock outright, so collecting it is a hard requirement in the
workflow, not a nice to have.

## Evergreen

Policy document is a pointer with a terminal directory and no rates. Rule 036-I01
import, 036-E01 export.

The directory is the valuable part. It maps terminal location codes such as
USLAXB, USSVNG, USNFKT, USBALT to the operator and the operator's site, which is
exactly the MTO schedule map needed for the MSC pass-through problem and for
building a 541.6(c)(2) terminal-schedule reference.

## Free time benchmark

FMC report to Congress, April 2015:

> "Historically, MTO schedules and VOCC tariffs allowed for **five working days**
> of free time for both import and export containers, and, for most ports in the
> U.S., this remains the standard allowance - the notable exceptions being the
> **Ports of New York/New Jersey, Los Angeles and Long Beach, where four days is
> standard demurrage free time**."

2026 reality: dry import free time is 4 working days almost everywhere, with
reefer and special equipment at 2 to 3. The allowance came down by one working
day. The charge unit changed at the same time, which is where the money is.

The same 2015 report identifies the discharge versus availability problem, so
this is not a new argument: terminals discharge vessels when gates are not open,
which is why free time rules specify a start time.
