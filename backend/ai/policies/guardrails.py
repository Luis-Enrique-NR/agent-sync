"""Fail-closed deterministic checks applied before an outbound turn is emitted."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from ai.domain.models import (
    AgentProfile,
    AgentTurn,
    NumericLimit,
    NumericOperator,
    SensitiveDataCategory,
    ToolFactVisibility,
)


@dataclass(frozen=True, slots=True)
class Violation:
    code: str
    detail: str


@dataclass(frozen=True, slots=True)
class GuardrailResult:
    allowed: bool
    violations: tuple[Violation, ...] = ()


class GuardrailPipeline:
    """Validate structured actions plus defensive patterns in public text."""

    _email_pattern = re.compile(
        r"(?<![\w.+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}(?![\w.-])",
        re.IGNORECASE,
    )
    _phone_pattern = re.compile(
        r"(?<!\d)(?:\+?\d{1,3}[ .-]?)?(?:\(?\d{2,3}\)?[ .-])"
        r"\d{3}[ .-]?\d{3,4}(?!\d)"
    )
    _coordinates_pattern = re.compile(
        r"(?<!\d)[+-]?(?:90(?:\.0+)?|[0-8]?\d(?:\.\d+)?),\s*"
        r"[+-]?(?:180(?:\.0+)?|(?:1[0-7]\d|\d?\d)(?:\.\d+)?)(?!\d)"
    )
    _address_pattern = re.compile(
        r"\b(?:calle|carrera|avenida|diagonal|transversal|cra\.?|av\.?|"
        r"street|road|avenue|st\.?|rd\.?|ave\.?)\s+\d+[A-Z]?"
        r"(?:\s*(?:#|nro\.?|no\.?)\s*\d+(?:[-\s]\d+)?)?",
        re.IGNORECASE,
    )
    _currency_pattern = re.compile(
        r"(?:(?P<symbol>[$€£])\s*(?P<symbol_value>\d+(?:[.,]\d+)?)|"
        r"(?P<code_value>\d+(?:[.,]\d+)?)\s*(?P<code>USD|COP|EUR|GBP))",
        re.IGNORECASE,
    )

    def evaluate(self, profile: AgentProfile, turn: AgentTurn) -> GuardrailResult:
        violations: list[Violation] = []
        violations.extend(self._numeric_violations(profile, turn))
        violations.extend(self._unstructured_currency_violations(turn))
        violations.extend(self._disclosure_violations(profile, turn))
        violations.extend(self._public_text_violations(profile, turn))
        return GuardrailResult(
            allowed=not violations,
            violations=tuple(violations),
        )

    def _numeric_violations(
        self, profile: AgentProfile, turn: AgentTurn
    ) -> list[Violation]:
        violations: list[Violation] = []
        terms_by_key: dict[str, list] = {}
        for term in turn.numeric_terms:
            terms_by_key.setdefault(term.key.casefold(), []).append(term)

        for limit in profile.hard_limits:
            matching_terms = terms_by_key.get(limit.key.casefold(), [])
            if not matching_terms and limit.unit:
                # A model cannot evade a monetary limit merely by renaming the key.
                matching_terms = [
                    term
                    for term in turn.numeric_terms
                    if term.unit
                    and term.unit.casefold() == limit.unit.casefold()
                    and turn.intent.value in {"OFFER", "COUNTER_OFFER", "ACCEPT"}
                ]
            for term in matching_terms:
                if limit.unit and (term.unit or "").casefold() != limit.unit.casefold():
                    violations.append(
                        Violation(
                            code="NUMERIC_UNIT_MISMATCH",
                            detail=f"{term.key} must use unit {limit.unit}",
                        )
                    )
                    continue
                if not self._satisfies(term.value, limit):
                    violations.append(
                        Violation(
                            code="HARD_NUMERIC_LIMIT",
                            detail=f"{term.key} violates configured {limit.operator.value}",
                        )
                    )
        return violations

    def _unstructured_currency_violations(
        self, turn: AgentTurn
    ) -> list[Violation]:
        represented = {
            (Decimal(str(term.value)), (term.unit or "").upper())
            for term in turn.numeric_terms
        }
        violations: list[Violation] = []
        for match in self._currency_pattern.finditer(turn.public_message):
            raw_value = match.group("symbol_value") or match.group("code_value")
            if raw_value is None:
                continue
            value = Decimal(raw_value.replace(",", "."))
            code = (match.group("code") or "").upper()
            if code:
                is_represented = (value, code) in represented
            else:
                is_represented = any(term_value == value for term_value, _ in represented)
            if not is_represented:
                violations.append(
                    Violation(
                        code="UNSTRUCTURED_CURRENCY_AMOUNT",
                        detail="currency amounts in public text require a numeric term",
                    )
                )
        return violations

    @staticmethod
    def _satisfies(candidate_value: float, limit: NumericLimit) -> bool:
        candidate = Decimal(str(candidate_value))
        expected = Decimal(str(limit.value))
        comparisons = {
            NumericOperator.GREATER_THAN: candidate > expected,
            NumericOperator.GREATER_THAN_OR_EQUAL: candidate >= expected,
            NumericOperator.LESS_THAN: candidate < expected,
            NumericOperator.LESS_THAN_OR_EQUAL: candidate <= expected,
            NumericOperator.EQUAL: candidate == expected,
        }
        return comparisons[limit.operator]

    @staticmethod
    def _disclosure_violations(
        profile: AgentProfile, turn: AgentTurn
    ) -> list[Violation]:
        private_facts = {
            fact.value_ref: fact
            for fact in profile.tool_facts
            if fact.visibility is ToolFactVisibility.PRIVATE_REFERENCE
        }
        violations: list[Violation] = []
        for disclosure in turn.disclosure_requests:
            fact = private_facts.get(disclosure.value_ref)
            if fact is None:
                violations.append(
                    Violation(
                        code="UNKNOWN_PRIVATE_REFERENCE",
                        detail="disclosure references data not owned by the speaker",
                    )
                )
                continue
            if fact.category is not disclosure.category:
                violations.append(
                    Violation(
                        code="PRIVATE_CATEGORY_MISMATCH",
                        detail="disclosure category differs from its protected fact",
                    )
                )
            if disclosure.category in profile.never_disclose:
                violations.append(
                    Violation(
                        code="NEVER_DISCLOSE",
                        detail=f"{disclosure.category.value} is forbidden by a hard limit",
                    )
                )
        return violations

    def _public_text_violations(
        self, profile: AgentProfile, turn: AgentTurn
    ) -> list[Violation]:
        text = turn.public_message
        violations: list[Violation] = []
        pattern_checks = (
            (self._email_pattern, "RAW_EMAIL_IN_PUBLIC_TEXT"),
            (self._phone_pattern, "RAW_PHONE_IN_PUBLIC_TEXT"),
            (self._coordinates_pattern, "RAW_LOCATION_IN_PUBLIC_TEXT"),
            (self._address_pattern, "RAW_ADDRESS_IN_PUBLIC_TEXT"),
        )
        for pattern, code in pattern_checks:
            if pattern.search(text):
                violations.append(
                    Violation(code=code, detail="public message contains protected data")
                )

        for fact in profile.tool_facts:
            if (
                fact.visibility is ToolFactVisibility.PRIVATE_REFERENCE
                and fact.value_ref
                and fact.value_ref.casefold() in text.casefold()
            ):
                violations.append(
                    Violation(
                        code="PRIVATE_REFERENCE_IN_PUBLIC_TEXT",
                        detail="opaque references are internal and cannot be spoken",
                    )
                )
        return violations
