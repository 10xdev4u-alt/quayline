"""Resolving a declared rate rule to a dated rate block.

541.6(c)(2) makes the carrier name the rule the daily rate is based on, and the
clause lists what that name can be:

    the tariff name and rule number, terminal schedule, applicable service
    contract number and section, or applicable negotiated arrangement

So when a carrier complies, the lookup is possible, and any divergence between the
looked up schedule and the demand is a dispute rather than an opinion. That is the
condition the whole product depends on and it is worth saying plainly: the engine
cannot check a charge whose carrier did not say which rule it charged under.

The registry is nearly empty, and that is the honest state of it

Four issues in and we hold a handful of transcribed schedules. A tariff is
per cluster, per equipment type and per date, Maersk alone publishes several dozen
combinations, and a service contract can override all of it at a named section.

An entry that is not held is a resolution failure with a message naming what was
asked for, not a nearest match. Returning the closest block we happen to hold
would produce a comparison against a rate the carrier never said applied, and the
difference would then be presented as a dispute. That is the failure mode this
whole repository has spent seven issues auditing out of itself, and a fuzzy
tariff lookup would reintroduce all of it in one line.
"""

from __future__ import annotations

from dataclasses import dataclass

from quayline.tariffs.blocks import RateBlock
from quayline.tariffs.resolution import (
    RateQuery,
    Requirement,
    Resolution,
    resolve,
)


class UnresolvedRuleError(LookupError):
    """The declared rule is not one we hold. The message says what was asked for."""


@dataclass(frozen=True, slots=True)
class Registry:
    """Blocks indexed by a normalised rule reference.

    Normalisation is case and whitespace only. It does not fuzzy match, does not
    strip punctuation that might be significant, and does not fall back. A caller
    that wants a looser match has to say so explicitly, and nothing does yet.
    """

    blocks: tuple[RateBlock, ...]
    #: Rules that cannot be resolved without a further input. Empty by default,
    #: so a registry with no dimension indexed rules needs no declaration.
    requirements: tuple[Requirement, ...] = ()

    @staticmethod
    def normalise(reference: str) -> str:
        return " ".join(reference.split()).casefold()

    def keys(self) -> tuple[str, ...]:
        """Normalised lookup keys, for comparing against a caller supplied reference."""
        return tuple(sorted(self.normalise(b.rule) for b in self.blocks))

    def held(self) -> tuple[str, ...]:
        """The rule references as written, for showing a human.

        A person reading a resolution failure wants the carrier's own name for a
        schedule, not our case folded version of it.
        """
        return tuple(sorted(b.rule for b in self.blocks))

    def resolve(self, query: RateQuery) -> Resolution:
        """The block for a declared rule reference on a date, or why there is not one.

        Issue 28 changed this from raising to returning. Resolution failure is a
        normal, frequent answer, because coverage is not uniform across carriers, and
        an exception is a control flow event that leaves a caller nowhere to put a
        warning for the letter. See ``tariffs/resolution.py`` for the three refusals:
        no approximation, no UNVERIFIED block, and no guess at a missing dimension.
        """
        return resolve(query, self.blocks, self.requirements)


__all__ = ["RateBlock", "Registry", "UnresolvedRuleError"]
