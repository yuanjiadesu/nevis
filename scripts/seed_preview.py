"""Seed a fictional corpus for preview and search-relevance testing."""

import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Iterator

BASE_URL = os.getenv("NEVIS_SEED_URL", "http://127.0.0.1:8001").rstrip("/")
TENANT = os.getenv("NEVIS_SEED_TENANT", "nevis-global")
ADVISOR = os.getenv("NEVIS_SEED_ADVISOR", "local-advisor")
IDENTITY = {"X-Nevis-Tenant": TENANT, "X-Nevis-Advisor": ADVISOR}
SEED_VERSION = "search-demo-v2"

# Each anchor represents a behaviour worth testing. The first case deliberately uses
# different wording for the query ("address proof") and the evidence ("utility bill").
ANCHORS = (
    (
        "John",
        "Doe",
        "john.doe@neviswealth.com",
        "NevisWealth client preparing for retirement and consolidating household records.",
        "Household electricity statement",
        """This fictional record was supplied during the annual review. It is retained only as
        demonstration data and contains no real account details. The document is a utility bill
        from an electricity supplier. It shows the account holder's name and current residential
        address and may therefore be used as evidence of where the client lives.""",
    ),
    (
        "Maya",
        "Patel",
        "maya.patel@greenharbour.example",
        "Founder interested in responsible investing and climate-aware portfolios.",
        "Responsible investment preference",
        """The client wants investments aligned with environmental and social goals. She prefers
        a sustainable portfolio that excludes thermal coal and considers carbon intensity while
        retaining broad diversification. Performance and fees remain important constraints.""",
    ),
    (
        "Arthur",
        "Clarke",
        "arthur.clarke@familyoffice.example",
        "Family wealth and succession planning across two generations.",
        "Legacy and beneficiary discussion",
        """The family discussed passing wealth to children and grandchildren. The adviser should
        coordinate the will, trust arrangements, beneficiary nominations, and potential
        inheritance-tax exposure with the client's solicitor before any recommendation.""",
    ),
    (
        "Elena",
        "Rossi",
        "elena.rossi@northbridge.example",
        "Planning for two children to attend university.",
        "Future education costs",
        """The planning objective is to meet school and university fees without disrupting
        retirement saving. A monthly investment plan and a separate education fund were modelled
        against tuition inflation and the dates each child is expected to begin studying.""",
    ),
    (
        "Owen",
        "Hughes",
        "owen.hughes@oldmill.example",
        "Several workplace pensions accumulated after changing employers.",
        "Workplace pension consolidation",
        """The client is considering moving old employer pension pots into one arrangement.
        Before any pension transfer, compare charges, guarantees, safeguarded benefits, investment
        choices, and access terms. No transfer should proceed until the comparison is complete.""",
    ),
    (
        "Priya",
        "Shah",
        "priya.shah@oakledger.example",
        "Tax-efficient investing after the sale of company shares.",
        "Share disposal planning",
        """The client expects to sell a concentrated holding of company shares. Review the base
        cost, available losses, disposal timing, annual exemption, and likely capital-gains-tax
        liability. Coordinate calculations with the client's accountant.""",
    ),
    (
        "Marcus",
        "Chen",
        "marcus.chen@harbourworks.example",
        "Self-employed client with uneven monthly income.",
        "Short-term cash reserve",
        """Income varies through the year, so the client needs readily accessible savings before
        investing further. Build an emergency fund covering six months of essential spending and
        keep it in cash rather than exposing this rainy-day reserve to market volatility.""",
    ),
    (
        "Sofia",
        "Laurent",
        "sofia.laurent@atelier.example",
        "New investor concerned about losses during market falls.",
        "Downside tolerance assessment",
        """The discussion tested how the client would react to a severe market decline. Although
        her stated attitude to risk is balanced, limited spare income reduces her capacity for
        loss. The recommended allocation must reflect both measures.""",
    ),
    (
        "Noah",
        "Williams",
        "noah.williams@cityutility.example",
        "Researches listed energy and water infrastructure companies.",
        "Utility sector investment outlook",
        """This is an investment research note, not evidence of residence. It reviews regulated
        electricity networks, water utilities, interest-rate sensitivity, dividend coverage, and
        infrastructure valuations. It must not be treated as a household bill.""",
    ),
    (
        "Amara",
        "Okafor",
        "amara.okafor@willowcare.example",
        "Planning for possible care costs and delegated decision-making.",
        "Later-life legal arrangements",
        """The client wants trusted relatives to make decisions if she loses capacity. She will
        ask a solicitor about lasting powers of attorney for property, financial affairs, health,
        and welfare, while the adviser models a reserve for long-term care costs.""",
    ),
    (
        "Liam",
        "Evans",
        "liam.evans@meadow.example",
        "Retiring soon and wants predictable monthly spending money.",
        "Guaranteed retirement income",
        """The client values a dependable payment for life more than full investment flexibility.
        Compare an annuity with pension drawdown, including inflation protection, spouse's
        benefits, health-based enhancements, death benefits, and the effect of provider rates.""",
    ),
    (
        "Isla",
        "Martin",
        "isla.martin@stonegate.example",
        "Recently moved home and is updating correspondence details.",
        "Change of correspondence address",
        """The client asked the firm to update the address used for letters after moving home.
        This workflow note records the request but is not supporting evidence: no bank statement,
        council-tax notice, tenancy agreement, or household bill was supplied with it.""",
    ),
)

FIRST_NAMES = (
    "Avery",
    "Jordan",
    "Sam",
    "Riley",
    "Casey",
    "Morgan",
    "Taylor",
    "Cameron",
    "Drew",
    "Jamie",
)
LAST_NAMES = ("Bennett", "Campbell", "Foster", "Lee", "Morgan", "Rivera")
PRIORITIES = (
    "retirement income",
    "mortgage repayment",
    "estate planning",
    "tax efficiency",
    "accessible savings",
    "portfolio diversification",
)
STYLES = ("balanced", "growth", "income", "sustainable", "capital-preservation")


def request(path: str, payload: dict[str, object], key: str) -> dict[str, object]:
    value = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=json.dumps(payload).encode(),
        method="POST",
        headers={**IDENTITY, "Content-Type": "application/json", "Idempotency-Key": key},
    )
    try:
        with urllib.request.urlopen(value, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace")
        raise RuntimeError(f"{value.method} {path} failed: {error.code} {detail}") from error


def read(path: str) -> dict[str, object]:
    value = urllib.request.Request(f"{BASE_URL}{path}", headers=IDENTITY)
    with urllib.request.urlopen(value, timeout=30) as response:
        return json.load(response)


def clients() -> Iterator[tuple[int, str, str, str, str, str, str]]:
    for index, anchor in enumerate(ANCHORS, start=1):
        yield index, *anchor
    for index in range(len(ANCHORS) + 1, 51):
        first_name = FIRST_NAMES[(index - 1) % len(FIRST_NAMES)]
        last_name = f"{LAST_NAMES[(index - 1) % len(LAST_NAMES)]}{index}"
        priority = PRIORITIES[(index - 1) % len(PRIORITIES)]
        yield (
            index,
            first_name,
            last_name,
            f"{first_name.lower()}.{last_name.lower()}@preview.nevis.test",
            f"Fictional household focused on {priority}.",
            f"{priority.title()} planning note",
            (
                f"The annual planning meeting for {first_name} {last_name} focused on {priority}. "
                "The record summarises current objectives, agreed constraints, and actions for the "
                "next review. It contains fictional demonstration data only."
            ),
        )


def supporting_documents(
    index: int, first_name: str, last_name: str
) -> tuple[tuple[str, str], tuple[str, str]]:
    priority = PRIORITIES[(index + 1) % len(PRIORITIES)]
    style = STYLES[(index + 2) % len(STYLES)]
    subject = f"{first_name} {last_name}"
    return (
        (
            "Annual suitability review",
            f"The fictional annual review for {subject} confirms a {style} investment approach. "
            f"The adviser reviewed objectives, time horizon, knowledge, risk, costs, and the need "
            f"to retain funds for {priority}. The next review is due in twelve months.",
        ),
        (
            "Meeting actions",
            f"Actions agreed with {subject}: confirm current balances, update regular "
            "contributions, "
            f"check beneficiary details, and revisit {priority}. No recommendation or transaction "
            "is authorised by this fictional note.",
        ),
    )


def wait_until_indexed(version_ids: list[str], timeout_seconds: int = 180) -> None:
    deadline = time.monotonic() + timeout_seconds
    pending = set(version_ids)
    while pending and time.monotonic() < deadline:
        completed: set[str] = set()
        for version_id in pending:
            status = read(f"/v1/document-versions/{version_id}")
            if status["indexing_status"] == "failed":
                raise RuntimeError(f"indexing failed for document version {version_id}")
            if status["indexing_status"] == "completed":
                completed.add(version_id)
        pending -= completed
        if pending:
            time.sleep(1)
    if pending:
        raise RuntimeError(f"timed out waiting for {len(pending)} document versions")


def main() -> None:
    version_ids: list[str] = []
    for index, first_name, last_name, email, description, title, content in clients():
        client_key = f"{SEED_VERSION}-client-{index}"
        client = request(
            "/v1/clients",
            {
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "description": description,
                "social_links": [],
                "source_type": "preview-seed",
                "source_reference": client_key,
            },
            client_key,
        )
        documents = ((title, content), *supporting_documents(index, first_name, last_name))
        for document_number, (document_title, document_content) in enumerate(documents, start=1):
            document_key = f"{SEED_VERSION}-document-{index}-{document_number}"
            result = request(
                f"/v1/clients/{client['id']}/documents",
                {
                    "source_reference": "preview-seed",
                    "external_document_id": document_key,
                    "title": document_title,
                    "content": document_content,
                },
                document_key,
            )
            version_ids.append(str(result["document_version_id"]))

    wait_until_indexed(version_ids)
    print(
        f"Seeded {len(tuple(clients()))} fictional clients and {len(version_ids)} searchable "
        f"documents at {BASE_URL}."
    )


if __name__ == "__main__":
    main()
