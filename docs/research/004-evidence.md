# Evidence operations

Research date 2026-09-27. This is the layer where most disputes are lost, and the
losses are procedural rather than substantive.

The headline finding: **the quality of the evidence packet decides the case, not
the merits.** A UIIA panel held a case solely because the provider supplied a
repair estimate instead of the actual repair bill, and said that with the right
documentation the case would have gone the other way.

## Appointment availability screenshots, the de facto standard

Four carriers publish nearly identical specifications. Hapag D07, ONE, APL and
MSC. Encode this as a capture state machine, because satisfying it exactly
removes the most common reason a dispute dies.

| Requirement | Hapag D07(3) | ONE | APL | MSC |
|---|---|---|---|---|
| Screenshot 1, day before waiver date | **06:00 to 12:00 noon** | 06:00 to 12:00 noon | same | time stamped |
| Screenshot 2, waiver date | **06:00 to 09:00** | 06:00 to 09:00 | same | |
| Time zone | **the applicable terminal's** | terminal local | the relevant terminal's | |
| Coverage | every terminal Hapag uses at the port, or every inland facility in the region | every terminal ONE used | every terminal and relevant inland facility | all shifts, as far into the future as the system allows |
| Entire screen including URL | **Yes** | yes | **Yes** | |
| Timestamp | auto-generated **or** date and time on screen | yes | auto-generated **and** the current date and time at the bottom right of the screen | time stamped |
| Third-party site acceptable | Yes, if widely used and recognized reliable, entire screen plus URL plus all shifts, auto-generated or on-screen date and time, documents the specific basis | yes, a reliable third-party vendor's site may be used | yes, same four criteria | |
| Two-shift terminals | via "all shifts" | **explicit, both shifts** | all shifts | all shifts |
| Apparent available appointment | must state **why the appointment could not be used** | | | |
| Dual transaction failure | requires a motor carrier statement of good-faith attempt | same | same | |
| Consequence of missing evidence | "**The dispute will be denied with respect to any day covered by the dispute for which such evidence is not provided**" | "will not be deemed submitted", rejected as incomplete | same | |

Hapag and APL both carry a decision default that works in our favour: Hapag will
grant unless it investigates and determines in good faith that appointments **were**
reasonably available. Same for APL.

ONE adds a categorical example: a "No Empty Return Location" submission without a
valid screenshot of appointment unavailability taken the working day before the
waiver date means **no dispute was submitted**, rejected as incomplete.

COSCO's bar is the lowest in the industry, from its own answer in Docket 24-01:
screenshots or other corroboration showing the facility was not available,
including closure, lack of appointments and dual move requirements, **without even
asserting that it actually tried to pick up or return the container that day**.

## Equipment Interchange Receipt

Governed by the UIIA, current version effective **2026-06-18**.

> §D.2.a "At the time of Interchange, the Parties or their agents shall execute an
> Equipment Interchange Receipt and/or exchange an electronic receipt equivalent"
>
> §D.2.c "**Each Party shall be entitled to receive a copy and/or an electronic
> receipt equivalent of the Equipment Interchange Receipt as described in D.2.a
> above without charge.**"
>
> §D.2.b The Provider or Facility Operator must provide an electronic system so
> the motor carrier can describe equipment condition electronically without
> substantial burden

**§D.2.c is the right we build the workflow around.** Both the motor carrier and
the equipment provider are entitled to a copy without charge. Ask the motor
carrier for its gate-out EIR and the facility for its gate-in EIR.

Automatic gate system images, the "Recorded Images" under §D.2.d: if recorded
images are taken at interchange, damage is not reported on the gate in or gate out
EIR, the words "Damage is captured on Recorded Images" must be printed on the
EIR, and images are available to each party for **one year** from interchange at no
charge.

How arbitration treats it: panels treat a clean gate-out EIR as an allocation of
liability that shifts the burden to the motor carrier to disprove. They reject
unsupported causation theories with "speculation is not evidence."

**Three failure modes that cost carriers money, and which we can exploit when
the record is thin:**

1. Gate images too dark or obscured, or the "Damage is captured on Recorded Images"
   legend missing. The panel found for the motor carrier.
2. No gate record at all because the terminal system was down. The panel found
   against the **equipment provider** and waived per diem. A missing gate record is
   the terminal's problem.
3. Photos with no date, time or location are rejected.

Provider may not invoice repair items at or below **$50 per unit per interchange
period**, unless a higher addendum threshold applies to both parties.

## Terminal gate logs

Owned by the facility operator, not the carrier and not the shipper. No single
format.

| Source | What you get |
|---|---|
| APM Terminals `GET /container-event-history` | `eventDetails[].performedDateTimeLocal` from the terminal operating system. Best programmatic route |
| TTI `GET api.ttitns.com/api/gateio` | `ioType` IN or OUT, `pickupDeliveryDateTime`, carrier SCACs, `appointmentAvailable`, `overallOnHold`, `holdStatus` for customs, freight, USDA and terminal holds, `demurrageDue`, `locationType` D deck, W wheel, V vessel, G gate, R rail |
| EDI 315 `R4` and status date segments | Carrier's view, weaker than a terminal record |
| project44 | Only `source == "FACILITY"` events count |
| Direct request, or discovery | Slowest, strongest in a contested setting |

The FMC's own fact-finding, Number 28 from 2019, said it plainly:

> "Many marine terminals with appointment systems can determine **how many
> appointments were available on a given day, whether and when a trucker attempted
> to make an appointment or cancelled an appointment, and whether a trucker arrived
> outside an appointment window**."

Cargo interests asked for a "trouble ticket" and appointment log records.
Carriers and OTIs replied that "the only way a trucker could corroborate a lack of
available appointments was to take a screenshot with a mobile phone."

**The terminal already has the appointment availability history and the closure
verification. The gap is contractual access, not data existence.** That is why
the standing data feed ask matters more than any single dispute.

## Customs hold evidence

**A third party cannot query ACE directly.** CBP safeguards prohibit access to
entry summary data unless the requester is the original filer, a Post Summary
Correction filer, a NILS filer authorized by the importer of record, or a surety
agent with an obligated bond.

So customs hold evidence arrives as a feed or export from the importer of record
or the broker. **Do not build an ACE integration dependency.**

If we are the filer, the query is Cargo Manifest, In-Bond and Entry Status, `CQ`,
input record `WR1`, output records including `WR2` which carries entry processing
status, entry release status, and cargo location. Queries by entry number only
support entries up to six months old. Release status `1AN` carries 0 not
released, 1 released, 2 information not permitted.

Disposition codes that prove a hold: **`04` entry detained**, `29` not released,
`51` manifest hold CBP, `55` CBP manifest hold removed, **`56` CBP hold removed**,
`76` active entry summary not found.

The artifact a shipper hands over is one of: an ACE report pulled by the filer, an
ACE portal screen printout showing the disposition history, broker-saved DIS upload
confirmions, or for non-automated facilities a filer-presented screen printout
showing at minimum the shipment ID, quantity released, type of release, and who
presented it.

**The indemnity argument against the broker:** CBP "will seek remedy from the party
providing the information" if a held shipment is released in error. That is a lever
worth naming in correspondence.

Carrier-facing requirements: Hapag D06 considers waiver in good faith where
customs authorities put a hold on cargo. MSC requires, for government-hold
disputes, "a statement validating the customs hold was not a result of any action
by the shipper, their agent, or any party to the bill of lading."

Regulatory support: 46 CFR 545.5(c)(2)(iv) gives government inspections their own
factor, and the FMC has stated that "the imposition of any demurrage or detention
charge, regardless of cause, is subject to the general prohibition contained in 46
U.S.C. 41102(c). **This includes charges resulting from government holds.**"

## Admissibility of digital evidence

**The standard is low and the tooling is cheap. Use it.**

| Rule | Content | Application |
|---|---|---|
| **Fed. R. Evid. 902(13)** | Certified records generated by an electronic process. Requires reasonable written notice to the adverse party and inspection availability | **The certified recomputation report is a textbook 902(13) exhibit.** Certify engine version, input document hash, tariff table version, and the derivation for each disputed day |
| **Fed. R. Evid. 902(14)** | Certified data copied from an electronic device, file or storage medium, authenticated by digital identification, meaning a **hash value** | **Every** screenshot, EIR, ACE report and terminal event export gets a SHA-256 at capture time, written to an append-only log. Highest value engineering decision in the evidence layer |
| **902(11), 902(12)** | Certified domestic and **foreign** records of a regularly conducted activity. Foreign requires signature "in a manner that, if falsely made, would subject the maker to a criminal penalty in the country where the certification is signed" | 902(12) is the route for foreign carrier documents. Document the signatory's authority |
| **901(b)(4)** | Distinctive characteristics, taken with all circumstances | Screenshots: terminal name, date grid, shift labels, URL bar. *Konell v. Allied Prop. & Cas.* required the printout show it reflects the page as of a specified date and identify the website. Hapag, ONE and APL requiring the entire screen including URL **is** that checklist |
| **901(b)(9)** | A process or system showing it produces an accurate result | The recompute engine |
| **902(13) limit** | A certification establishes **only authenticity**. Admissibility on hearsay, relevance and best evidence is separate | Do not conflate authenticated with admitted |
| **Business records limit** | Authenticating third-party content as a business record covers "the timestamps, metadata, etc. maintained by the owner. **The content of the messages themselves will not qualify**" | If we ingest broker email as customs-hold evidence, keep the envelope and headers as the business record, not the body |
| **Fallback** | Certifications are not mandatory. Testimony from the person who took the screenshots is valid, per *Rivera v. Village of Farmingdale* | Maintain the identity of the person who captured each item |
| **Non-conclusory requirement** | The 902(13) certification must contain information sufficient to establish authenticity if given by a witness, and "should not be conclusory" | Name the terminal, the timezone, the capture tool and version, and the exact URL or endpoint |

## UIIA arbitration, the reference standard we borrow from

UIIA administers the container and chassis interchange agreement. It is not our
primary forum. It is where equipment-side facts get adjudicated and where the
evidence standard is published and consistent.

Panels include a motor carrier member and an ocean carrier member, with appeals
to a senior panel. Every decision ends with an explicit list headed "UIIA
PROVISIONS RELIED UPON BY BINDING ARBITRATION PANEL", quoting the section and its
revision date.

**Model our evidence packets the same way.** Cite the provision, the revision
date, and the item number. It is the house style of the tribunal and it persuades
both the FMC and the carriers.

The invoice-validity standard, §E.3.a(2), is the part worth copying: to be valid
an invoice must detail the work, include a copy of the actual source document,
and include the factual documentation supporting the determination. Where the
actual document is unavailable, documentation with the vendor name, date,
location and a control number that ties it to the invoice is acceptable. For a
gate transaction using recorded images, that documentation must include images of
the equipment condition at interchange.

## What we will not conflate

**TIA**, the Transport Intermediary Association, formerly NITL, runs a separate
freight-intermediary arbitration program for broker and forwarder claims. Its
mechanics and evidence standards were **not verified in this research pass**.
Treat as unresearched. The UIIA is the container equipment instrument.

A citation engine must never emit "TIA" where it means UIIA.
