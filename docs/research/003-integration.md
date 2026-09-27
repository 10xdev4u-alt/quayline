# Integration surfaces

Research date 2026-09-27. Marked `NOT PUBLIC` where an entity does not publish it.
That label is load bearing. A hole is cheap. A wrong integration is expensive.

## The finding that sets the architecture

**No carrier has a programmatic dispute API. Not one.** Every published ocean D&D
dispute path is a browser form, a ticket system, or email.

The nearest things to automation are all human-in-the-loop file uploads:

- MSC Canada's **Mass Dispute Upload** template
- ONE's **bulk file upload** template for multiple invoice numbers
- CMA CGM's **multi-select** dispute form, up to 35 invoices at once, restricted
  to the same domain and the same reason

So the filing layer is a browser-driven, human-supervised operation, not an API
client. Design the adapter interface around that reality rather than pretending
otherwise.

## Ingestion

### EDI, the correction

Only **310** and **315** are ocean transaction sets. 204, 210, 212 and 214 are
**motor carrier** and do not carry ocean D&D invoices. There is no X12 set for an
ocean D&D invoice as such. D&D rides inside 310 charge lines or arrives as PDF.

| Set | Name | Mode | Use |
|---|---|---|---|
| **310** | Freight Receipt and Invoice, ocean | Ocean | The ocean invoice. `B3` header, `L1` charge lines, `L103` rate qualifier, **`L108` special charge or allowance code** |
| **315** | Status Details, ocean | Ocean | Container status events. Where gate in and gate out timestamps originate |
| 312 | Arrival Notice, ocean | Ocean | Availability notice |
| 300, 301, 303, 304, 309 | Booking family | Ocean | Context |
| **492** | **Miscellaneous Rates** | Any | **The only X12 set built for D&D rates.** Repeatable `DM` demurrage, detention and storage rate segments. This is a structured tariff feed, not an invoice |
| 210 | Motor Carrier Freight Details and Invoice | Motor | `L108` codes include `DEM`, `DET`, `DTU`, `DEL`, `EXM` |

Motor carrier `L108` codes give us a useful charge vocabulary even though we are
ocean-focused.

Maersk's own estimate for EDI setup: "EDI = One-to-One, coding/testing, setup can
take up to a few months per connection." Against "API = One-to-Many, set up in
days via Developer Portal."

No carrier publishes which transaction sets it will emit to which customer. That
is per-customer configuration, not a public fact.

### What D&D invoices actually look like

**Born-digital text-layer PDF, strongly consistent per carrier.** MSC issues a
single USA D&D layout with fixed sections. Scanned images are the exception: small
NVOCCs, faxed forwards, scanned credit notes, and bills from smaller terminals.

Multi-container per invoice is the norm, not the exception. MSC's e-Pay explicitly
handles bills of lading ending in "A" where you must supply the original number
and add containers in the comment field.

Consolidated billing is routine. CMA CGM supports up to 35 invoices per action and
requires them to share the same domain and the same reason.

**Credit notes are a distinct document type, not negative invoices.** ZIM: "Part of
the dispute process is to issue an **invoice crediting you** for the amount." Model
them as first-class objects.

**Terminal-issued D&D is the norm at most US terminals.** Two invoices per
container is common, terminal demurrage plus carrier detention.

CMA CGM adds 2 percent VAT on some D&D. Detention can be billed in the currency of
the inland place. US demurrage generally includes storage.

### Data quality problems to engineer for

| Problem | Why it bites |
|---|---|
| **Availability date equals vessel arrival date** | FMC audit standard says outright that the availability date should not be the vessel arrival date unless the cargo is actually available then. A 545.5(c)(2)(i) defect |
| **No return location offered** | Hapag was charged by FMC, Docket 22-03, over 11 containers at $160 to $1845 each. It said it did not control the appointment system, which the FMC called a rationalization meeting neither purpose of detention charges |
| **Intervening clock-stopping events not disclosed** | 541.6(b) requires the start and end of free time but does not require disclosure of stops in between. Carriers routinely omit them. **Recompute from external truth, not from the invoice, on the availability question** |
| **EDI lag against portal latency** | PayCargo discloses up to one hour lag where terminals rely on EDI, and about 30 minutes on a direct terminal system. The recompute must tolerate event-arrival lag before declaring a missing event a defect |
| **Terminal system outage** | In a UIIA arbitration the terminal admitted its system was down and no interchange record existed. The panel found against the equipment provider and waived per diem. Missing gate record is the terminal's problem |
| **Container invoiced as total loss, then resurfaced** | A UIIA panel found for the claimant on gate-record grounds |
| **Region and lane specific tariff versions** | COSCO publishes separate dated PDFs per lane and effective date. US import demurrage effective 2026-08-14, import detention 2026-07-15, export demurrage 2026-07-02, export detention 2024-05-17. Version the rate engine by tariff document, never by "current" |

### Document extraction, measured

Generic invoice parsers are the wrong primary tool. The failure mode is documented
and it is exactly our shape:

> "Receipts structured as invoices **lacked line-item data**. Textract still
> extracted summary fields (vendor, total, date) but left item arrays empty."

That is a D&D invoice with a summary header and a buried charge table.

Measured field-level accuracy on scanned invoices: Azure Document Intelligence 93
percent, AWS Textract 78 percent. On 2026 models: Gemini 3 Pro 94.75, Azure AI DI
90.52, Claude Sonnet 4.5 90.27, GPT 5 Mini 87.94, Amazon Analyze Expense 82.87.
Table extraction: Gemini 2.5 Pro 94.2 percent TEDS against Textract 82.1 and Azure
81.5.

Line-item accuracy is the inverse of field accuracy and it is the metric that
matters here: Azure 87 percent, Textract 82, GPT-4o image 63, GPT-4o plus OCR 57,
Google 40. The best field extractor is the worst line-item extractor.

Freight-specific: OCR character accuracy 98 to 99.5 percent on clean digital, 90 to
96 on degraded. Field level 96 to 99 clean, 88 to 93 challenging. And character
accuracy is a misleading metric, which the vendor making the point says plainly.

**Extraction order that follows the evidence:**

1. Text-layer PDF parse first. Major carriers are digital, so this is near 100
   percent and free.
2. Azure AI Document Intelligence prebuilt layout for tables.
3. A schema-constrained frontier vision model pass.
4. X12 492 `DM` segments and 310 EDI as ground truth where available.
5. A deterministic validation layer: invoice total equals the sum of lines; free
   time start plus allowed days equals end; chargeable days times rate equals the
   amount; container and bill of lading present per line.

**The validation layer, not the extractor, is where the recovery dollars are.** A
parser that gets 87 percent of line items right and a validator that catches the
13 percent is a working system. A parser at 100 percent with no validator is a
liability.

## Carrier dispute channels

| Carrier | Intake | Deadline | Evidence spec | Programmatic |
|---|---|---|---|---|
| MSC | Online case, or regional email. US demurrage `US038-nydetention@msc.com`. Canada has a Dynamics 365 tool at eservices.msccanada.ca | 30 days | **Yes**, and specific | Canada portal only. No API |
| CMA CGM | My CMA CGM to Invoice Dashboard, redirects to MyCS. US `usa.disputes@usa.cma-cgm.com`. **Netherlands went portal-only 2026-04-20** | 30 days | Yes | No API |
| Hapag-Lloyd | Online Business Suite. Hapag waiver and RNOPS forms | 30 days | **Yes, rules D06 and D07** | No API |
| ONE | `us.one-line.com/invoice-disputes`, plus a Charge Inquiry tool accepting the last 12 characters of the bill | 30 days, later is **invalid** | **Yes, enumerated** | Web form with bulk upload. No API |
| ZIM | myZIM Finance, or per-domain email | 30 days | Yes | No API |
| COSCO | **Freshdesk portals** per area. Path is a structured category tree | 30 days | Procedural | Ticket. Structurally the most automatable of the email flows |
| Evergreen | Dispute Registration Form plus evidence, to the issuing office. Dallas, NYC, LAX per diem mailboxes | 30 days | Form only | No portal |
| HMM | e-service inquiry, requires login | 30 days | Policy statement only | No API. NOT PUBLIC |
| Maersk | **No US dispute portal found.** NOT PUBLIC | unknown | NOT PUBLIC | See the D&D read API below |

MSC requires the per diem invoice number ending in P, the bill of lading number,
the container number, and a comprehensive explanation. Response in 7 business
days, which is stricter than the 30 day rule.

MSC's appointment-unavailability evidence spec, encoded:

- One screenshot per day, time stamped
- Day before the waiver date, between 06:00 and 12:00 noon
- Waiver date, between 06:00 and 09:00
- Terminal's local time zone
- Entire screen including the URL
- All shifts
- As far into the future as the terminal system allows

## Carrier developer portals

| Carrier | Portal | Auth | Billing or disputes covered |
|---|---|---|---|
| **Maersk** | developer.maersk.com | **Consumer-Key header plus OAuth 2.0 client_credentials.** Token at `api.maersk.com/customer-identity/oauth/v2/access_token`, 7199 second lifetime | **Charges: read, yes. Disputes: no** |
| Hapag-Lloyd | API Portal PDF. "Most available APIs in compliance with DCSA standards" | NOT PUBLIC | NOT PUBLIC |
| MSC | myMSC, Dynamics 365 | Account | NOT PUBLIC |
| CMA CGM | eBusiness, MyCS | Account | NOT PUBLIC |
| ONE | eCommerce, ONE Finance | Account | NOT PUBLIC |
| ZIM | myZIM | Account | NOT PUBLIC |
| COSCO | eLines, Freshdesk | Account | NOT PUBLIC |
| Evergreen, HMM | None | | NOT PUBLIC |

### The Maersk D&D API, the one that matters

`GET /demurrage-detention/v1/charges?equipmentReference=<csv containers>&transportDocumentReference=<BL>`

Per container it returns `type` of Demurrage, Detention or Combined, plus
`clockStart`, `freeDays`, `elapsedDays`, **`chargeableDays`**, `amount`,
`currency`, and `tariffReference`.

**The carrier publishes its own recomputation inputs.** That is a gift: we can
compare their own `chargeableDays` against our gate-calendar arithmetic and
dispute any divergence, quoting their API as the source.

Rate limit 60 requests per minute and 1000 per hour per consumer key.

**Provenance caveat.** This specification was read from a third-party mirror
citing developer.maersk.com. The path, parameter names and response schema are
consistent across the mirror's files, but verify against the portal directly
before building. Note the security block declares only `ConsumerKey`, which is
inconsistent with the portal-wide OAuth pattern. Confirm which is enforced.

## TMS and freight audit platform surfaces

| Platform | API | Auth | Rate limits | Sandbox | Embed surface |
|---|---|---|---|---|---|
| **project44** | Full v4 ocean. Shipments, statuses, event history, position history | OAuth 2.0 client_credentials, roles then access groups | 600 rpm per org on `/api/**`. **5 rpm per Client on one category** | **NOT PUBLIC.** Carrier connections configured by p44 support | None documented |
| **Descartes** | api.descartes.com. MacroPoint, CustomsInfo, Datamyne, GLN B2B | HTTP Basic for MacroPoint. CustomsInfo and Datamyne by contract | NOT PUBLIC | NOT PUBLIC | Broker and Forwarder Enterprise Systems API, details not public |
| **Loop** | 14 published APIs including shipment jobs, invoices, exceptions, artifacts | HTTP Bearer | Not published as a number. Guidance: ask your contact to relax limits for bulk sync | See docs.loop.com | None documented. **"Order Hub" is a product name, not an integration contract** |
| **Freehand** | **NOT PUBLIC.** "All capabilities via API" is marketing without published docs | | | | Partner program with three tracks. No API-for-partners spec |
| **Navix, Kaleris** | NOT PUBLIC. Intake via API, EDI, email. 16 plus TMS integrations | NOT PUBLIC | NOT PUBLIC | NOT PUBLIC | |
| MercuryGate, Blue Yonder, Oracle TMS, McLeod, SAP, e2open | Named connector targets. NOT PUBLIC | | | | |
| CargoSmart, FourKites | NOT PUBLIC for D&D | | | | |

Freehand's stated connectors: Oracle TMS, Blue Yonder, MercuryGate, Manhattan,
e2open. ERP via SAP ECC and S4, Oracle Cloud ERP, Oracle JDE, NetSuite, BAPI,
REST, OData, Dynamics 365. Go live 12 to 14 weeks. SOC 2 Type II, ISO 27001.

Freehand claims "dispute notifications and evidence delivered to carrier portals
**via API**" with no carrier named and no endpoint given. That claim is either
true and unpublished, or marketing. Verify before believing it.

Loop raised $210 million. Its `charge.category` taxonomy and its `qid` plus
`RawEntityTag` identifier model are worth adopting wholesale for interoperability.

### The project44 trap, and the fix

`events[].dateTimes[]` is an array of candidate timestamps. Each has a `source` of
`CARRIER`, `FFW`, `NVOCC`, `BROKER`, `FACILITY`, **`GEOFENCE`**, `CONTRACT`,
**`P44`**, `USER`, or `UNKNOWN`, and a `selected` boolean. project44 "chooses the
most reliable source using certain rules and heuristics" and exposes only the
winner at the top level.

**A D&D recompute needs the gate-out timestamp. The selected value may be a
GEOFENCE, which is AIS-derived, or a P44 computation. Neither is a gate record.**

The fix, and it is cheap:

1. Filter `dateTimes[]` for `source == "FACILITY"` or `"CARRIER"`. Those are the
   asserted, disputable facts.
2. Use `selected` only as a cross-check.
3. Where `selected` is `GEOFENCE` or `P44` and a `FACILITY` or `CARRIER` candidate
   exists with a different value, raise a materiality flag. **That divergence set
   is the dispute queue.**

**Do not treat AIS or geofence as gate evidence.** A gate-in timestamp
reconstructed from a vessel position is not a terminal record and will not survive
a carrier's credible evidence standard or a charge complaint.

Rate limit reality: 5 requests per minute per client is the binding constraint for
polling container clocks. Batch, cache hard, and prefer webhooks. project44
recommends webhooks over running GET requests.

## Terminal data

| Terminal | Portal | Auth | Endpoints | Cost |
|---|---|---|---|---|
| **APM Terminals** | developer.apmterminals.com | **OAuth 2.0 client_credentials only.** Token TTL 30 minutes | `GET /container-event-history`, `GET /import-availability`, `GET /vessel-visits`, `GET /empty-container-returns`, Truck Appointments API | **Credit metered.** Pricing NOT PUBLIC, commercial negotiation |
| **TTI** | third-party docs | Per customer access token in header | `GET api.ttitns.com/api/containers`, `GET api.ttitns.com/api/gateio` | NOT PUBLIC |
| **LBCT** | announced 2019-07-30 | **API key embedded in the URL path** | `GET http://api.lbct.com/<KEY>/API/LBCTCargoSearchWebService/cargo-numbers/{ids}`, active vessel visits | Customer based |
| **Port Houston** | porthouston.com | Client ID and secret to a token | Vessel, Inventory, Appointment, Orders, Event, Road services | Approval based, no pricing published |
| SSA, Matson, Hutchison, ITS, Trapac, Maher, Seagirt, Garden City, PSA, WBCT, ETS, PNCT, MAT, OMNI, Tampa, JAXPORT | **NOT PUBLIC** | | | |

**APM Terminals is the only genuinely self-service terminal API.** Signup, accept
a prepaid plan, register the app, get a consumer key and secret. A 403 means
inadequate credits or no rate plan selected. Twenty UN/LOCODEs including USLAX,
USMOB, USNWK, USMIA, plus Rotterdam, Felixstowe, Singapore, Durban, Hamburg,
Jebel Ali, Colombo, Buenos Aires.

**There is no published price list for any US marine terminal API.** APMT is
self-service for the plan but the credit pricing is not published. Everything else
is bilateral commercial negotiation.

### The APM endpoints that matter

`GET /container-event-history?facilityCode=USLAX&assetId=MRSU3638119,TCNU6736993`

```json
[{"containerId":"...","shippingLine":"MAE","eventDetails":[
  {"performedDateTimeLocal":"2020-...","eventType":"...","positionNotes":"..."}]}]
```

`performedDateTimeLocal` is a local-time timestamp straight from the terminal
operating system. **This is gate-log-grade evidence**, the terminal's own
contemporaneous record rather than a carrier's reconstruction.

`GET /vessel-visits` returns `vesselStatus`, `scheduledEtaDateTimeLocal`,
`latestEtaDateTimeLocal`, `actualEtaDateTimeLocal`, `cargoCutOffDateTimeLocal`,
and the shipping lines served. Updated ETA is vessel-schedule dispute evidence.

Truck Appointment API performs the manual task: view available slots, create,
update and cancel appointments, list by time frame. It needs system-level consumer
key **plus** user-level authorization through TERMPoint. Available at LA, Mobile,
Gothenburg, Vado Ligure, Port Elizabeth.

### Which terminals have nothing

Pierpass and WCMTOA member terminals. At POLA: APMT, FMS, WBCT, ETS, TraPac, Yusen.
At POLB: LBCT, TTI, ITS, PCT, Pier A and C60. **Only LBCT and TTI publish APIs.
The rest do not.**

### The TraPac lesson

TraPac is a top 5 US marine terminal operator with no public API. PayCargo and
Gnosis provide a container payment portal with real time status, last free day
management, pro-forma invoicing and integrated dispute resolution, through a
commercial agreement with TraPac.

**Aggregators get terminal data through bilateral commercial deals, not
self-service.** That is the template.

PayCargo discloses the latency honestly: up to one hour where the terminal relies
on EDI, about 30 minutes on a direct terminal system.

### The three layer model

| Layer | Contents | Who owns it |
|---|---|---|
| 1. Shipment and master data | Bookings, bills of lading, containers, route, dates, service contract reference | Read from the customer's TMS or forwarder network |
| 2. Carrier truth | Gate in and out, availability, holds, free-day clock, appointments, vessel schedule | Read from carrier APIs, terminal APIs, aggregators. **Nobody sells this as a clean feed** |
| 3. Dispute and money | Form submission, evidence packet, credit note tracking, charge complaint filing | **Ours end to end. No carrier sells this** |

Layers 1 and 2 are commoditized and contested. **Layer 3 is the surface worth
owning**, and it is where the 2026 charge complaint procedures land.
