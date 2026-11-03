"""Contractor job stages and homeowner next-step copy.

Portal, reservation, approval, and payment stages stay unreachable unless
an external confirmation record is stored. This module never invents kWh
or rebate outcomes.
"""

from __future__ import annotations

from typing import Literal

Stage = Literal[
    "lead",
    "intake",
    "audit",
    "modeling",
    "package_optimization",
    "proposal",
    "signature",
    "program_submission",
    "approval",
    "reservation",
    "scheduling",
    "installation",
    "qa",
    "inspection",
    "final_submission",
    "payment",
]

STAGES: tuple[str, ...] = (
    "lead",
    "intake",
    "audit",
    "modeling",
    "package_optimization",
    "proposal",
    "signature",
    "program_submission",
    "approval",
    "reservation",
    "scheduling",
    "installation",
    "qa",
    "inspection",
    "final_submission",
    "payment",
)

GATED_STAGES: dict[str, str] = {
    "program_submission": "program_submission_confirmation",
    "approval": "approval_confirmation",
    "reservation": "reservation_confirmation",
    "final_submission": "final_submission_confirmation",
    "payment": "payment_confirmation",
}

HOMEOWNER_NEXT: dict[str, str] = {
    "lead": "Share your address and a time for intake. No rebate has been filed.",
    "intake": "Provide occupancy, income band (if using a program screen), and utility access. This is not a program application.",
    "audit": "Be home for the audit. Photos are stored for the job file; they are not a reservation.",
    "modeling": "Wait while the contractor models the home. Energy use appears only if EnergyPlus actually ran.",
    "package_optimization": "Review measure packages. Deltas are EnergyPlus differences, not approved rebate savings.",
    "proposal": "Read the proposal. Signing happens only through the e-sign provider, not a click in this app.",
    "signature": "Complete the e-sign envelope if one was sent by a connected provider. This app does not notarize.",
    "program_submission": "A state-portal confirmation has been recorded, or this stage is blocked until one exists. This app does not submit.",
    "approval": "An external approval reference must be recorded before this stage is used. This app does not approve rebates.",
    "reservation": "A reservation confirmation must be recorded. This app does not reserve funds.",
    "scheduling": "Confirm an install window with the contractor.",
    "installation": "Keep the work area accessible. Photos document the install; they are not QA sign-off.",
    "qa": "Walk through punch-list items with the crew.",
    "inspection": "Be available if an inspector visits.",
    "final_submission": "A final-filing confirmation must be recorded. This app does not file closeout.",
    "payment": "A payment confirmation must be recorded. This app does not issue rebate payments.",
}

CONTRACTOR_NEXT: dict[str, str] = {
    "lead": "Collect contact and site address.",
    "intake": "Complete intake fields and optional program application draft.",
    "audit": "Run the photo checklist. Attach PreSite Pro file sidecars.",
    "modeling": "Validate the canonical model and run EnergyPlus when the engine is present.",
    "package_optimization": "Re-run packages on the real model. Do not add percentages.",
    "proposal": "Attach the proposal to a building model and, if used, a pinned compliance evaluation.",
    "signature": "Send via ESignPort. File adapter stays pending_vendor until a completed PDF is ingested.",
    "program_submission": "Record the state-portal confirmation reference, or stay off this stage.",
    "approval": "Record the external approval reference, or stay off this stage.",
    "reservation": "Record the reservation confirmation reference, or stay off this stage.",
    "scheduling": "Book crew time. SchedulingPort is not in this slice.",
    "installation": "Execute the work order. Capture during/after photos.",
    "qa": "Close punch list.",
    "inspection": "Record inspector outcome as notes, not as a program approval.",
    "final_submission": "Record the closeout confirmation reference, or stay off this stage.",
    "payment": "Record the payment confirmation reference, or stay off this stage.",
}

DEFAULT_CHECKLIST = (
    ("exterior", "Exterior elevations"),
    ("attic", "Attic / ceiling"),
    ("nameplate", "HVAC nameplate"),
    ("electrical_panel", "Electrical panel"),
    ("existing_hvac", "Existing heating and cooling equipment"),
    ("ducts", "Ducts / distribution"),
    ("foundation", "Foundation / rim / slab"),
)


def homeowner_status(stage: str, confirmations: dict[str, dict | None]) -> dict[str, str | bool]:
    gated = stage in GATED_STAGES
    field = GATED_STAGES.get(stage)
    confirmed = bool(field and confirmations.get(field))
    if gated and not confirmed:
        label = "Stage not active — waiting for an external confirmation record"
        claim = False
    else:
        label = HOMEOWNER_NEXT[stage]
        claim = confirmed
    return {
        "stage": stage,
        "what_to_do_next": label,
        "contractor_next": CONTRACTOR_NEXT[stage],
        "claims_portal_submission": stage in {"program_submission", "final_submission"} and confirmed,
        "claims_approval": stage == "approval" and confirmed,
        "claims_reservation": stage == "reservation" and confirmed,
        "claims_payment": stage == "payment" and confirmed,
    }


def assert_stage_allowed(stage: str, confirmations: dict[str, dict | None]) -> None:
    if stage not in STAGES:
        raise ValueError(f"unknown stage {stage}")
    field = GATED_STAGES.get(stage)
    if field and not confirmations.get(field):
        raise ValueError(
            f"{stage} requires a recorded {field} from an external system. "
            "This product does not submit, reserve, approve, or pay."
        )
