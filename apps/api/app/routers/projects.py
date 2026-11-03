from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db import get_db
from app.domain.ops import STAGES
from app.models import ContractorProject, Home, ProposalRecord
from app.schemas import ConfirmationIn, ProjectCreate, ProposalIn, SignIn, StagePatch, WorkOrderIn
from app import services_ops as ops

router = APIRouter(prefix="/api/v1")


def _project(db: Session, project_id: str) -> ContractorProject:
    project = db.get(ContractorProject, project_id)
    if project is None:
        raise HTTPException(404, "project not found")
    return project


def _project_out(db: Session, project: ContractorProject) -> dict:
    status = ops.project_status(project)
    home = db.get(Home, project.home_id)
    return {
        "id": project.id,
        "home_id": project.home_id,
        "home_name": None if home is None else home.name,
        "name": project.name,
        "stage": project.stage,
        "stages": list(STAGES),
        "homeowner": status,
        "building_model_id": project.building_model_id,
        "program_evaluation_id": project.program_evaluation_id,
        "program_evaluation_pack_version": project.program_evaluation_pack_version,
        "crm_ref": project.crm_ref,
        "confirmations": {
            "program_submission": project.program_submission_confirmation,
            "approval": project.approval_confirmation,
            "reservation": project.reservation_confirmation,
            "final_submission": project.final_submission_confirmation,
            "payment": project.payment_confirmation,
        },
        "checklist": [
            {
                "id": item.id,
                "code": item.code,
                "label": item.label,
                "required": item.required,
                "completed": item.completed,
                "photo_id": item.photo_id,
            }
            for item in ops.checklist(db, project.id)
        ],
        "proposals": [
            {
                "id": record.id,
                "title": record.title,
                "status": record.status,
                "building_model_id": record.building_model_id,
                "program_evaluation_id": record.program_evaluation_id,
                "program_evaluation_pack_version": record.program_evaluation_pack_version,
                "envelope_status": record.envelope_status,
            }
            for record in ops.list_proposals(db, project.id)
        ],
        "work_orders": [
            {
                "id": order.id,
                "title": order.title,
                "status": order.status,
                "proposal_id": order.proposal_id,
                "building_model_id": order.building_model_id,
                "program_evaluation_id": order.program_evaluation_id,
                "program_evaluation_pack_version": order.program_evaluation_pack_version,
            }
            for order in ops.list_work_orders(db, project.id)
        ],
    }


@router.get("/projects/board")
def project_board(db: Session = Depends(get_db)) -> dict:
    return {"columns": ops.board_payload(db), "stages": list(STAGES)}


@router.get("/projects")
def list_projects(db: Session = Depends(get_db)) -> list[dict]:
    return [_project_out(db, project) for project in ops.list_projects(db)]


@router.post("/projects")
def create_project(body: ProjectCreate, db: Session = Depends(get_db)) -> dict:
    home = db.get(Home, body.home_id)
    if home is None:
        raise HTTPException(404, "home not found")
    return _project_out(db, ops.create_project(db, home, body.name))


@router.get("/projects/{project_id}")
def get_project(project_id: str, db: Session = Depends(get_db)) -> dict:
    return _project_out(db, _project(db, project_id))


@router.get("/projects/{project_id}/homeowner")
def homeowner_view(project_id: str, db: Session = Depends(get_db)) -> dict:
    project = _project(db, project_id)
    home = db.get(Home, project.home_id)
    status = ops.project_status(project)
    return {
        "project_id": project.id,
        "home_name": None if home is None else home.name,
        **status,
    }


@router.post("/projects/{project_id}/stage")
def change_stage(project_id: str, body: StagePatch, db: Session = Depends(get_db)) -> dict:
    project = _project(db, project_id)
    try:
        return _project_out(db, ops.set_stage(db, project, body.stage, body.reason))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/projects/{project_id}/confirmations")
def add_confirmation(project_id: str, body: ConfirmationIn, db: Session = Depends(get_db)) -> dict:
    project = _project(db, project_id)
    try:
        return _project_out(db, ops.record_confirmation(db, project, body.kind, body.source, body.reference))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/projects/{project_id}/photos")
async def upload_photo(
    project_id: str,
    tags: str = Form("audit"),
    stage: str = Form("audit"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    project = _project(db, project_id)
    home = db.get(Home, project.home_id)
    assert home is not None
    data = await file.read()
    row = ops.add_photo(
        db,
        project,
        home,
        file.filename or "photo.bin",
        file.content_type or "application/octet-stream",
        data,
        [part.strip() for part in tags.split(",") if part.strip()],
        stage,
    )
    return {
        "id": row.id,
        "provider": row.provider,
        "tags": row.tags,
        "sidecar_uri": row.sidecar_uri,
        "sha256": row.sha256,
    }


@router.post("/projects/{project_id}/proposals")
def create_proposal(project_id: str, body: ProposalIn, db: Session = Depends(get_db)) -> dict:
    project = _project(db, project_id)
    try:
        record = ops.create_proposal(
            db,
            project,
            body.title,
            body.measures,
            body.building_model_id,
            body.program_evaluation_id,
            body.notes,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {
        "id": record.id,
        "status": record.status,
        "building_model_id": record.building_model_id,
        "program_evaluation_id": record.program_evaluation_id,
        "program_evaluation_pack_version": record.program_evaluation_pack_version,
        "measures": record.measures,
        "notes": record.notes,
        "envelope_status": record.envelope_status,
    }


@router.post("/proposals/{proposal_id}/send")
def send_proposal(proposal_id: str, body: SignIn, db: Session = Depends(get_db)) -> dict:
    proposal = db.get(ProposalRecord, proposal_id)
    if proposal is None:
        raise HTTPException(404, "proposal not found")
    record = ops.send_proposal(db, proposal, body.signer_name, body.signer_email)
    return {
        "id": record.id,
        "status": record.status,
        "envelope_id": record.envelope_id,
        "envelope_status": record.envelope_status,
        "note": "ESignPort file adapter is pending_vendor. Not a Dropbox Sign or Acrobat Sign send.",
    }


@router.post("/projects/{project_id}/work-orders")
def create_work_order(project_id: str, body: WorkOrderIn, db: Session = Depends(get_db)) -> dict:
    project = _project(db, project_id)
    proposal = db.get(ProposalRecord, body.proposal_id) if body.proposal_id else None
    order = ops.create_work_order(db, project, proposal, body.title, body.scope)
    return {
        "id": order.id,
        "status": order.status,
        "proposal_id": order.proposal_id,
        "building_model_id": order.building_model_id,
        "program_evaluation_id": order.program_evaluation_id,
        "program_evaluation_pack_version": order.program_evaluation_pack_version,
        "scope": order.scope,
    }
