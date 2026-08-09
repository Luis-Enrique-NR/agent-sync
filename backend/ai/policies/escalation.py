"""User-configurable and mandatory human approval rules."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from ai.domain.models import (
    AgentProfile,
    AgentTurn,
    CommitmentKind,
    DecisionReason,
    EscalationRule,
    EscalationRuleType,
    MANDATORY_APPROVAL_CATEGORIES,
    TurnIntent,
)


@dataclass(frozen=True, slots=True)
class EscalationResult:
    required: bool
    reasons: tuple[DecisionReason, ...] = ()
    matched_rule_ids: tuple[str, ...] = ()


class EscalationEvaluator:
    def evaluate(self, profile: AgentProfile, turn: AgentTurn) -> EscalationResult:
        reasons: set[DecisionReason] = set()
        matched_rule_ids: list[str] = []

        if any(
            disclosure.category in MANDATORY_APPROVAL_CATEGORIES
            for disclosure in turn.proposed_disclosures
        ):
            reasons.add(DecisionReason.MANDATORY_PERSONAL_DATA)

        for rule in profile.escalation_rules:
            if rule.enabled and self._matches(rule, turn):
                reasons.add(DecisionReason.USER_RULE)
                matched_rule_ids.append(rule.rule_id)

        return EscalationResult(
            required=bool(reasons),
            reasons=tuple(sorted(reasons, key=lambda reason: reason.value)),
            matched_rule_ids=tuple(matched_rule_ids),
        )

    @staticmethod
    def _matches(rule: EscalationRule, turn: AgentTurn) -> bool:
        if rule.rule_type is EscalationRuleType.ANY_FINAL_PRICE:
            return turn.intent is TurnIntent.ACCEPT and any(
                "price" in term.key.casefold() for term in turn.numeric_terms
            )

        if rule.rule_type is EscalationRuleType.AMOUNT_ABOVE:
            threshold = Decimal(str(rule.threshold))
            return any(
                term.key.casefold() == (rule.key or "").casefold()
                and Decimal(str(term.value)) > threshold
                for term in turn.numeric_terms
            )

        if rule.rule_type is EscalationRuleType.SHARE_PERSONAL_DATA:
            return any(
                disclosure.category in rule.categories
                for disclosure in turn.proposed_disclosures
            )

        if rule.rule_type is EscalationRuleType.COMMIT_DATE:
            return any(
                commitment.kind is CommitmentKind.DATE
                for commitment in turn.commitments
            )

        if rule.rule_type is EscalationRuleType.FINAL_AGREEMENT:
            return turn.intent is TurnIntent.ACCEPT

        return False


class InboundEscalationEvaluator:
    """Evaluate counterpart requests against the receiving agent's rules."""

    def evaluate(self, profile: AgentProfile, turn: AgentTurn) -> EscalationResult:
        matched_rule_ids = [
            rule.rule_id
            for rule in profile.escalation_rules
            if rule.enabled and self._matches(rule, turn)
        ]
        if not matched_rule_ids:
            return EscalationResult(required=False)
        return EscalationResult(
            required=True,
            reasons=(DecisionReason.INBOUND_ACTION, DecisionReason.USER_RULE),
            matched_rule_ids=tuple(matched_rule_ids),
        )

    @staticmethod
    def _matches(rule: EscalationRule, turn: AgentTurn) -> bool:
        if rule.rule_type is EscalationRuleType.REQUEST_ACTION:
            return any(
                action.action_type in rule.action_types
                for action in turn.requested_actions
            )
        return False
