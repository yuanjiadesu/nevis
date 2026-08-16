import uuid

from nevis.domain.authorization import MEMBERSHIP_POLICY, AuthorizationAction, AuthorizationDecision


def test_membership_policy_decision_keeps_tenant_and_advisor_scope() -> None:
    tenant_id = uuid.uuid4()
    advisor_id = uuid.uuid4()
    decision = AuthorizationDecision(tenant_id, advisor_id, AuthorizationAction.DOCUMENT_INGEST)

    assert decision.policy == MEMBERSHIP_POLICY
    assert decision.result == "allow"
    assert decision.tenant_id == tenant_id
