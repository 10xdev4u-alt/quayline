# 46 CFR Part 541 and the surrounding law

Research date 2026-09-27. Every claim here is sourced. Anything I could not
verify from a primary source says so.

## Sources

- eCFR, Title 46, up to date 2026-09-24:
  `https://www.ecfr.gov/current/title-46/chapter-IV/subchapter-B/part-541`
- 89 FR 14330, published 2024-02-26, effective 2024-05-28 (OMB Control No. 3072-0073)
- 89 FR 66990, 2024-09-24 (OCEMA 90-day delay petition denied)
- 46 CFR Part 545, published 2020-05-18 (`reportdemurrage.pdf` context)

## Section map

The two load-bearing sections get swapped constantly, and swapping them inverts
the legal theory. They are laid out here so nobody has to remember.

| Section | Heading | In force |
|---|---|---|
| 541.1 | Purpose | yes |
| 541.2 | Scope and applicability | yes |
| 541.3 | Definitions | yes |
| 541.4 | [Reserved] | **removed 2025-12-29** |
| 541.5 | Failure to include required information | yes. The kill switch |
| 541.6 | Contents of invoice | yes. The twenty field checklist |
| 541.7 | Issuance of demurrage and detention invoices | yes |
| 541.8 | Requests for fee mitigation, refund, or waiver | yes |
| 541.99 | OMB control number 3072-0073 | yes |

## 541.4 is gone

*World Shipping Council v. FMC*, No. 24-1088, 152 F.4th 215 (D.C. Cir. 2025-09-23)
severed and vacated the section. It was removed from the CFR by 90 FR 60580
effective 2025-12-29 (RIN 3072-AD08, Docket FMC-2025-0107).

Two things follow, and the second one matters more than the first.

1. A wrong-party invoice is no longer a per-se non-payable defect. Do not build a
   rule on 541.4.
2. **541.6(a)(4) survived.** It still requires the carrier to state the basis on
   which the billed party is the proper party of interest and thus liable. The
   closed list of who may be invoiced is gone, but the obligation to articulate
   privity, consignee status, or a contractual pass-through is intact. This is the
   strongest post-vacatur hook available and it is under-used.

There are now two cases named *World Shipping Council v. FMC*. The other is No.
24-1298 (D.C. Cir. 2026-03-31), upholding 46 CFR 542.1 on unreasonable refusal of
vessel space. Same party, different rule. A citation engine must not conflate
them.

## 541.5, the kill switch

> "Failure to include any of the required minimum information in this part in a
> demurrage or detention invoice eliminates any obligation of the billed party to
> pay the applicable charge."

| Property | Value |
|---|---|
| Trigger | **Omission** of any required minimum. Conjunctive. One missing field voids the whole charge, not line items |
| Remedy | Automatic. No notice, no cure period, no showing of prejudice |
| Burden | Default common law, on the party asserting the charge |
| Contrast | 541.7(d) **does** permit a corrected invoice within 30 days. The drafters knew how to write a cure right. 541.5 has none, on purpose |
| Retroactivity | Charges incurred after 2024-05-28. Pre-OSRA charges fall under the old 49 CFR 41.1 |

**Limit worth knowing.** 46 U.S.C. 41104(f) cancels the obligation for *that*
invoice, but the carrier may reissue a compliant one. A 541.5 defect is a
per-invoice defense, not a permanent bar. We model it that way.

## 541.6, the twenty fields

Every subsection is bounded by the preamble "must be accurate and contain
sufficient information to enable the billed party to [X] and at a minimum must
include". Those are floors.

### (a) Identifying, four fields

1. Bill of Lading number(s)
2. Container number(s)
3. For imports, the port(s) of discharge
4. **The basis for why the billed party is the proper party of interest and thus liable**

### (b) Timing, eight fields

1. Invoice date
2. Invoice due date
3. The allowed free time in days
4. **The start date of free time**
5. **The end date of free time**
6. For imports, **the container availability date**
7. For exports, the earliest return date
8. **The specific date(s) for which demurrage and/or detention were charged**

Fields (b)(3), (b)(4), (b)(5) and (b)(8) together make the invoice
self-auditing. The charge can be recomputed from the invoice itself. That is the
product.

### (c) Rate, three fields

1. Total amount due
2. The applicable rule, by identifier: tariff name and rule number, terminal
   schedule, service contract number and section, or applicable negotiated
   arrangement
3. The specific rate or rates per that rule

Part 541 does not pick a winner between tariff and contract. It requires the
invoice to name which one, with an identifier sufficient to look it up. A
carrier billing a negotiated rate without disclosing the arrangement fails both
(c)(2) and (c)(3). This is the highest yield mechanical rule in the regulation.

### (d) Dispute, three fields

1. Contact information
2. Digital means, a URL, QR code, or watermark, pointing at a public page
   describing **what documentation the billed party must provide**
3. Defined timeframes that comply with Part 541

(d)(2) is a documentation disclosure mandate, not a find-our-website rule. A bare
homepage fails it.

### (e) Certifications, two fields

1. Charges are consistent with FMC rules, including Part 541 and 46 CFR 545.5
2. **The billing party's performance did not cause or contribute to the underlying invoiced charges**

(e)(2) is a factual representation by the carrier. A false one is a 541.5
failure, because the required statement is inaccurate and every subsection is
bounded by "must be accurate", and it is a 46 U.S.C. 41102(c) violation, which is
the FMC's primary enforcement hook and carries civil penalties under 46 U.S.C.
41107 plus refund. Check whether the statement is present first. Challenge its
truth second.

## 541.7, the deadlines

| Para | Applies to | Measured from | Days | Consequence |
|---|---|---|---|---|
| (a) | All billing parties | the date the charge was **last incurred** | 30 | not required to pay |
| (b) | NVOCC only | issuance date of the invoice the NVOCC received | 30 | not required to pay |
| (c) | NVOCC as both parties | NVOCC notifies its billing party that its own billed party disputed | +30 | extends, does not extinguish |
| (d) | Wrong party billed | date the charge was last incurred | 30 | not required to pay |

Three things that get implemented wrong:

**"Date on which the charge was last incurred" is not the out-gate date and not
the invoice date.** It is the final day of the accruing charge period. Deadline
equals last chargeable day plus 30 calendar days. The tariff's inclusive or
exclusive gate-out rule has to be resolved first.

**The NVOCC chain runs to about 90 days and it delays your clock.** 541.8(a) runs
the dispute window from the invoice issuance date **on the document**, so a late
re-bill starts your 30 days late. Never compute your own deadline from cargo
dates.

**541.7(d) is the only cure right in Part 541.** One misdirected invoice may be
reissued within 30 days of last charge incurred. Miss that and it is dead.

## 541.8, process only

> 541.8(a) "The billing party must allow the billed party at least thirty (30)
> calendar days from the invoice issuance date to request mitigation, refund, or
> waiver of fees."
>
> 541.8(b) "...must **attempt to resolve** the request within thirty (30) calendar
> days of receiving such a request or at a later date as agreed upon by both
> parties."

Attempt to resolve is not resolve. There is no requirement that the carrier pay
anything. 541.8 gives a compliant channel and a deadline, and zero substantive
entitlement. The money comes from 541.5, 541.7, 541.6 accuracy, or 41102(c).

(a) is a floor. (b) is a ceiling with a bilateral escape hatch. A carrier
publishing a 7-day window violates (a), is arguably a 541.6(d)(3) failure, and
therefore a 541.5 failure.

## Burden of proof, the asymmetry that matters

| Forum | Who bears it |
|---|---|
| FMC charge complaint, 46 U.S.C. 41310(b)(2) | **The common carrier**, on establishing reasonableness |
| Private dispute | Not set by statute. The carrier must prove entitlement as an incorporated tariff or contract term. Tariff-filed rates are incorporated by reference into the B/L |

In front of the FMC the carrier justifies the charge. In a private dispute you
argue an exception to an incorporated term. The postures reverse. Model them as
two engines with different priors, because evidence that wins one often loses
the other.

## 46 CFR 545.5, the reasonableness standard

The carrier defends the charge against this. (c)(1) is the incentive principle.
(c)(2) covers cargo availability, empty container return, notice of availability,
and government inspections. (d) covers policies, including dispute resolution
policies with points of contact, timeframes, and corroboration requirements. (e)
is transparent terminology. (f) is non-preclusion.

Two sub-points earn money:

**545.5(c)(2)(ii) is the highest yield defect class.** Detention charged where
containers could not be returned is likely to be found unreasonable absent
extenuating circumstances.

**545.5(c)(2)(iii)**: the FMC's own audit standard says that providing information
to contact the terminal for availability does not satisfy the notice requirement.
The date of cargo availability should not be the date of vessel arrival unless
the cargo is actually available that day.

**545.5(d) is a claim in its own right.** A carrier with no published corroboration
specification scores as unreasonable.

## The three element per-day test

*Evergreen Shipping Agency v. FMC*, 106 F.4th 1113 (D.C. Cir. 2024). For each
shipment, each date, and each charge, the complainant must show:

1. Unable to pick up or return on that specific date
2. The reason was outside their control
3. The charge could not have incentivized earlier return

**Element three is the one shippers skip.** The court held the incentive principle
is not a bright-line rule and does not replace the general reasonableness
standard.

## File every dispute

*Visual Comfort & Co. v. COSCO*, FMC Docket 24-01. COSCO argued the complainant
willfully declined to use its dispute procedures and that its actions were per se
reasonable.

The operative lesson: never let a claim age out of the 30-day carrier window on
the assumption you will arbitrate later. File it, even if the amount is small.

## Charge complaints, effective 2026-09-01

FMC "Charge Complaint Procedures", 91 FR 56053, Docket FMC-2026-0331, RIN
3072-AD00.

| Attribute | Value |
|---|---|
| Statute of limitations | **None.** The charge must have been assessed on or after 2022-06-16 |
| Burden | Carrier bears it, per 41310(b)(2) |
| Filing fee, interim | $0 currently |
| Filing fee, Subpart E formal | $387 |
| Filing fee, Subpart S small claims | $176 |
| Small claims ceiling | $50,000, decided by a Small Claims Officer, both parties must consent |
| Civil penalty | FMC must apply a penalty under 46 U.S.C. 41107 on a finding of non-compliance |
| Intake | chargecomplaints@fmc.gov |
| Speed | Discovery and oral argument are waived. The complainant is not expected to testify |
| Mixed filings | Portions meeting 41310(a) become Charge Complaints by operation of law; the rest proceeds under 41301 |
| Exclusivity | Interim and traditional routes may not run at the same time |

**There is no statute of limitations and the reach goes back to 2022-06-16.**
That is a four year recovery tail, and the filing fee is currently zero. This is
a revenue line the market has not priced.

## Adjacent regimes we must not conflate

| Cite | Subject |
|---|---|
| 46 CFR 541 | Ocean D&D invoice content, deadlines, dispute process |
| 46 CFR 545.5 | The substantive billing practices, referenced by 541.6(e)(1) |
| 46 U.S.C. 41102(c) | Just and reasonable practices. Primary enforcement hook. Penalties under 41107 |
| 46 U.S.C. 41104(f) | Cancellation of the payment obligation for a non-conforming invoice |
| 46 U.S.C. 41310 | Charge complaint. Burden on the carrier |
| 46 U.S.C. 41301 | Reparations. Three year limit. Do not confuse with 41310 |
| 46 U.S.C. 13710 | Motor carrier overcharges. 180 day contest deadline from receipt |
| 46 U.S.C. 14705 | 18 month civil action limit for cargo claims |
| 46 U.S.C. 14706 | Carmack Amendment. Different regime entirely, different evidence chain |
| 46 U.S.C. 80109 | Motor carrier bond. The escalation a carrier-side collector uses |
| 49 CFR Part 378 | Billing and collecting. Claims must be filed in writing with the **collecting** carrier. 60 day response |
| UIIA | Container and chassis interchange. The evidence standard reference, not our forum |
| TIA | Transport Intermediary Association, a separate arbitration program for broker claims. **Unresearched. Do not conflate with UIIA** |

**Ocean is the hard 30 day case. Truck detention is 180 days** under 49 U.S.C.
13710(b)(3)(B), with 90 to 180 per most master agreements. That asymmetry in
difficulty is why most competitors sit in truck audit and few are in ocean D&D.
Ocean D&D, done right, is less contested than the field's composition suggests.
