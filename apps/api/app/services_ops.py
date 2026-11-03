from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.crm_file import FileCrmAdapter
from app.adapters.esign_file import FileESignAdapter
from app.adapters.presitepro_file import PreSiteProFileAdapter
from app.domain.ops import (
    DEFAULT_CHECKLIST,
    GATED_STAGES,
    STAGES,
    assert_stage_allowed,
    homeowner_status,
)
from app.models import (
    BuildingModel,
    ContractorProject,
    Home,
    PhotoChecklistItem,
    PhotoRecord,
    PhotoSite,
    ProgramEvaluation,
    ProposalRecord,
    StageEvent,
    WorkOrder,
)
from app.ports.crm import JobDraft
from app.ports.esign import Document, Signer
from app.ports.photos import JobSiteDraft, PhotoIngest

photos = PreSiteProFileAdapter()
crm = FileCrmAdapter()
esign = FileESignAdapter()


def _confirmations(project: ContractorProject) -> dict[str, dict | None]:
    return {
        "program_submission_confirmation": project.program_submission_confirmation,
        "approval_confirmation": project.approval_confirmation,
        "reservation_confirmation": project.reservation_confirmation,
        "final_submission_confirmation": project.final_submission_confirmation,
        "payment_confirmation": project.payment_confirmation,
    }


def create_project(db: Session, home: Home, name: str | None = None) -> ContractorProject:
    model = db.scalars(
        select(BuildingModel).where(BuildingModel.home_id == home.id).order_by(BuildingModel.version.desc())
    ).first()
    evaluation = db.scalars(
        select(ProgramEvaluation)
        .where(ProgramEvaluation.home_id == home.id)
        .order_by(ProgramEvaluation.created_at.desc())
    ).first()
    project = ContractorProject(
        home_id=home.id,
        name=name or f"{home.name} job",
        stage="lead",
        building_model_id=None if model is None else model.id,
        program_evaluation_id=None if evaluation is None else evaluation.id,
        program_evaluation_pack_version=None if evaluation is None else evaluation.pack_version,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    ref = crm.upsert_job(
        JobDraft(our_job_id=project.id, name=project.name, stage=project.stage, home_id=home.id)
    )
    project.crm_ref = {
        "provider": ref.provider,
        "external_id": ref.external_id,
        "status": ref.status,
        "note": ref.note,
    }
    db.add(StageEvent(project_id=project.id, from_stage=None, to_stage="lead", reason="created"))
    for code, label in DEFAULT_CHECKLIST:
        db.add(PhotoChecklistItem(project_id=project.id, code=code, label=label, required=True, completed=False))
    db.commit()
    db.refresh(project)
    return project


def list_projects(db: Session) -> list[ContractorProject]:
    return list(db.scalars(select(ContractorProject).order_by(ContractorProject.updated_at.desc())))


def set_stage(db: Session, project: ContractorProject, stage: str, reason: str | None = None) -> ContractorProject:
    assert_stage_allowed(stage, _confirmations(project))
    previous = project.stage
    project.stage = stage
    db.add(StageEvent(project_id=project.id, from_stage=previous, to_stage=stage, reason=reason))
    if project.crm_ref and project.crm_ref.get("external_id"):
        from app.ports.crm import ExternalRef

        crm.update_stage(
            ExternalRef(
                provider=project.crm_ref.get("provider") or "file",
                external_id=project.crm_ref["external_id"],
                status=project.crm_ref.get("status") or "pending_vendor",
                scopes_granted=[],
                note=project.crm_ref.get("note") or "",
            ),
            stage,
        )
    db.commit()
    db.refresh(project)
    return project


def record_confirmation(
    db: Session, project: ContractorProject, kind: str, source: str, reference: str
) -> ContractorProject:
    field = GATED_STAGES.get(kind) or f"{kind}_confirmation"
    if field not in GATED_STAGES.values():
        raise ValueError("confirmation kind must be a gated stage")
    payload = {"source": source, "reference": reference, "recorded_by": "operator"}
    setattr(project, field, payload)
    db.commit()
    db.refresh(project)
    return project


def project_status(project: ContractorProject) -> dict:
    return homeowner_status(project.stage, _confirmations(project))


def ensure_photo_site(db: Session, project: ContractorProject, home: Home) -> PhotoSite:
    existing = db.scalars(select(PhotoSite).where(PhotoSite.project_id == project.id)).first()
    if existing:
        return existing
    site = photos.create_job_site(
        JobSiteDraft(
            name=project.name,
            our_job_id=project.id,
            address={"city": home.city, "state": home.state_code, "postal_code": home.postal_code},
        )
    )
    record = PhotoSite(
        id=site.id,
        project_id=project.id,
        home_id=home.id,
        name=site.name,
        provider=site.provider,
        sidecar_uri=site.sidecar_uri,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def add_photo(
    db: Session,
    project: ContractorProject,
    home: Home,
    filename: str,
    content_type: str,
    data: bytes,
    tags: list[str],
    stage: str = "audit",
) -> PhotoRecord:
    site = ensure_photo_site(db, project, home)
    photo = photos.add_photo(
        site.id,
        PhotoIngest(filename=filename, content_type=content_type, data=data, stage=stage, tags=tags),
    )
    row = PhotoRecord(
        id=photo.id,
        site_id=site.id,
        project_id=project.id,
        stage=photo.stage,
        tags=photo.tags,
        sidecar_uri=photo.sidecar_uri,
        bytes_uri=photo.bytes_uri,
        sha256=photo.sha256,
        provider=photo.provider,
    )
    db.add(row)
    items = db.scalars(select(PhotoChecklistItem).where(PhotoChecklistItem.project_id == project.id)).all()
    for item in items:
        if item.code in photo.tags and not item.completed:
            item.completed = True
            item.photo_id = photo.id
    db.commit()
    db.refresh(row)
    return row


def checklist(db: Session, project_id: str) -> list[PhotoChecklistItem]:
    return list(db.scalars(select(PhotoChecklistItem).where(PhotoChecklistItem.project_id == project_id)))


def list_proposals(db: Session, project_id: str) -> list[ProposalRecord]:
    return list(db.scalars(select(ProposalRecord).where(ProposalRecord.project_id == project_id)))


def list_work_orders(db: Session, project_id: str) -> list[WorkOrder]:
    return list(db.scalars(select(WorkOrder).where(WorkOrder.project_id == project_id)))


def create_proposal(
    db: Session,
    project: ContractorProject,
    title: str,
    measures: list[str],
    building_model_id: str | None,
    program_evaluation_id: str | None,
    notes: str = "",
) -> ProposalRecord:
    pack_version = None
    if program_evaluation_id:
        evaluation = db.get(ProgramEvaluation, program_evaluation_id)
        if evaluation is None or evaluation.home_id != project.home_id:
            raise ValueError("program evaluation is not on this home")
        pack_version = evaluation.pack_version
    if building_model_id:
        model = db.get(BuildingModel, building_model_id)
        if model is None or model.home_id != project.home_id:
            raise ValueError("building model is not on this home")
    record = ProposalRecord(
        project_id=project.id,
        building_model_id=building_model_id or project.building_model_id,
        program_evaluation_id=program_evaluation_id or project.program_evaluation_id,
        program_evaluation_pack_version=pack_version or project.program_evaluation_pack_version,
        title=title,
        measures=measures,
        status="draft",
        notes=notes
        or "Proposal is a work record, not a rebate award. Energy figures must come from stored EnergyPlus jobs.",
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def send_proposal(db: Session, proposal: ProposalRecord, signer_name: str, signer_email: str) -> ProposalRecord:
    envelope = esign.send_for_signature(
        Document(title=proposal.title, text=proposal.notes, our_document_id=proposal.id),
        [Signer(name=signer_name, email=signer_email)],
    )
    proposal.envelope_id = envelope.id
    proposal.envelope_status = envelope.status
    proposal.status = "sent_pending_vendor"
    db.commit()
    db.refresh(proposal)
    return proposal


def create_work_order(
    db: Session, project: ContractorProject, proposal: ProposalRecord | None, title: str, scope: str
) -> WorkOrder:
    order = WorkOrder(
        project_id=project.id,
        proposal_id=None if proposal is None else proposal.id,
        building_model_id=project.building_model_id if proposal is None else proposal.building_model_id,
        program_evaluation_id=project.program_evaluation_id if proposal is None else proposal.program_evaluation_id,
        program_evaluation_pack_version=(
            project.program_evaluation_pack_version if proposal is None else proposal.program_evaluation_pack_version
        ),
        title=title,
        scope=scope,
        status="draft",
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def board_payload(db: Session) -> dict[str, list[dict]]:
    columns = {stage: [] for stage in STAGES}
    for project in list_projects(db):
        home = db.get(Home, project.home_id)
        status = project_status(project)
        columns[project.stage].append(
            {
                "id": project.id,
                "home_id": project.home_id,
                "name": project.name,
                "home_name": None if home is None else home.name,
                "stage": project.stage,
                "homeowner_next": status["what_to_do_next"],
                "contractor_next": status["contractor_next"],
                "claims_portal_submission": status["claims_portal_submission"],
                "claims_approval": status["claims_approval"],
                "claims_reservation": status["claims_reservation"],
                "claims_payment": status["claims_payment"],
                "building_model_id": project.building_model_id,
                "program_evaluation_id": project.program_evaluation_id,
                "program_evaluation_pack_version": project.program_evaluation_pack_version,
                "crm_ref": project.crm_ref,
            }
        )
    return columns
