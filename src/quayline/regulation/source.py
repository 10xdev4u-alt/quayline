"""Where the regulatory text in this package came from, and as of when.

Every clause in ``checklist.py`` is generated from the eCFR XML. This module
records which snapshot, so a future change can tell a real regulatory change
apart from a transcription error, and so a dispute letter can cite a dated
source rather than a URL that has since moved.
"""

from __future__ import annotations

from dataclasses import dataclass

ECFR_SECTION_URL = "https://www.ecfr.gov/current/title-46/section-541.6"
ECFR_PART_URL = "https://www.ecfr.gov/current/title-46/part-541"


@dataclass(frozen=True, slots=True)
class Provenance:
    """A dated, citable record of one regulatory section.

    ``as_of`` is the eCFR currency date the text was taken from, not the date
    someone read the page. The difference matters when a dispute is filed two
    years after the fact, which is the normal case here.
    """

    cite: str
    heading: str
    as_of: str
    federal_register: str
    effective: str
    url: str

    def __str__(self) -> str:
        return f"{self.cite} {self.heading}, {self.federal_register}, as of {self.as_of}"


# The eCFR currency date the clause text was extracted from, and the Federal
# Register citation the eCFR itself prints in its CITA element for 541.6.
#
# Note on the effective date. The Federal Register citation above is
# [89 FR 14363, Feb. 26, 2024]. The implementing rule took effect 2024-05-28.
# Both are recorded, because a dispute letter needs the publication reference
# and an auditor needs to know which text was in force on the invoice date.
SECTION_541_6 = Provenance(
    cite="46 CFR 541.6",
    heading="Contents of invoice",
    as_of="2026-09-24",
    federal_register="89 FR 14363, Feb. 26, 2024",
    effective="2024-05-28",
    url=ECFR_SECTION_URL,
)

SECTION_541_5 = Provenance(
    cite="46 CFR 541.5",
    heading="Failure to include required information",
    as_of="2026-09-24",
    federal_register="89 FR 14363, Feb. 26, 2024",
    effective="2024-05-28",
    url="https://www.ecfr.gov/current/title-46/section-541.5",
)

SECTION_541_7 = Provenance(
    cite="46 CFR 541.7",
    heading="Issuance of demurrage and detention invoices",
    as_of="2026-09-24",
    federal_register="89 FR 14363, Feb. 26, 2024",
    effective="2024-05-28",
    url="https://www.ecfr.gov/current/title-46/section-541.7",
)

SECTION_541_8 = Provenance(
    cite="46 CFR 541.8",
    heading="Requests for fee mitigation, refund, or waiver",
    as_of="2026-09-24",
    federal_register="89 FR 14363, Feb. 26, 2024",
    effective="2024-05-28",
    url="https://www.ecfr.gov/current/title-46/section-541.8",
)

# The whole of Part 541, as of the same currency date. Held because the claim
# that 541.7(d) is the only cure right in the part is a claim about the whole
# part, and a claim about a whole is not supportable from one section of it.
#
# Section inventory, for the record:
#   541.1  purpose
#   541.2  scope and applicability
#   541.3  definitions
#   541.4  [Reserved]
#   541.5  failure to include required information
#   541.6  contents of invoice
#   541.7  issuance of demurrage and detention invoices
#   541.8  requests for fee mitigation, refund, or waiver
#   541.9 - 541.98  [Reserved]
#   541.99  OMB control number
PART_541 = Provenance(
    cite="46 CFR Part 541",
    heading="Demurrage and detention invoicing",
    as_of="2026-09-24",
    federal_register="89 FR 14363, Feb. 26, 2024",
    effective="2024-05-28",
    url=ECFR_PART_URL,
)
