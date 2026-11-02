from pathlib import Path

from app.adapters.crm_file import FileCrmAdapter
from app.adapters.esign_file import FileESignAdapter
from app.adapters.presitepro_file import PreSiteProFileAdapter
from app.domain.ops import assert_stage_allowed, homeowner_status
from app.ports.crm import ContactDraft
from app.ports.esign import Document, Signer
from app.ports.photos import JobSiteDraft, PhotoIngest


def test_gated_stage_blocked_without_confirmation():
    try:
        assert_stage_allowed("reservation", {"reservation_confirmation": None})
        raise AssertionError("should have blocked")
    except ValueError as exc:
        assert "does not submit, reserve, approve, or pay" in str(exc)


def test_homeowner_status_does_not_claim_unconfirmed_payment():
    status = homeowner_status("payment", {"payment_confirmation": None})
    assert status["claims_payment"] is False
    assert status["claims_reservation"] is False
    assert status["claims_approval"] is False
    assert status["claims_portal_submission"] is False


def test_homeowner_status_claims_only_with_confirmation():
    status = homeowner_status(
        "reservation",
        {"reservation_confirmation": {"source": "Neighborly", "reference": "RSV-1"}},
    )
    assert status["claims_reservation"] is True
    assert status["claims_payment"] is False


def test_file_crm_never_claims_vendor(tmp_path: Path):
    adapter = FileCrmAdapter(tmp_path)
    ref = adapter.upsert_contact(ContactDraft(name="Pat", email="pat@example.com"))
    assert ref.provider == "file"
    assert ref.status == "pending_vendor"
    assert "Zoho" in ref.note or "not called" in ref.note.lower()


def test_file_esign_never_claims_signed(tmp_path: Path):
    adapter = FileESignAdapter(tmp_path)
    envelope = adapter.send_for_signature(
        Document(title="Proposal", text="draft", our_document_id="p1"),
        [Signer(name="Pat", email="pat@example.com")],
    )
    assert envelope.status == "pending_vendor"
    assert envelope.completed_pdf_uri is None
    try:
        adapter.download_completed(envelope.id)
        raise AssertionError("should not download")
    except FileNotFoundError:
        pass


def test_presite_sidecar_schema(tmp_path: Path):
    adapter = PreSiteProFileAdapter(tmp_path)
    site = adapter.create_job_site(JobSiteDraft(name="12 Pine", our_job_id="job-1"))
    photo = adapter.add_photo(
        site.id,
        PhotoIngest(filename="attic.jpg", content_type="image/jpeg", data=b"jpeg-bytes", tags=["attic"]),
    )
    assert photo.provider == "presitepro_file"
    sidecar = Path(photo.sidecar_uri).read_text(encoding="utf-8")
    assert "presitepro.photo/v1" in sidecar
    assert adapter.get_photo_bytes(photo.id) == b"jpeg-bytes"


def test_api_project_board_and_gated_stage(client):
    home = client.post("/api/v1/homes", json={"name": "Ops house", "state_code": "NC", "postal_code": "27601"}).json()
    created = client.post("/api/v1/projects", json={"home_id": home["id"], "name": "Pine job"})
    assert created.status_code == 200, created.text
    project = created.json()
    assert project["stage"] == "lead"
    assert project["crm_ref"]["status"] == "pending_vendor"
    assert project["confirmations"]["reservation"] is None
    assert project["checklist"]
    assert project["homeowner"]["claims_payment"] is False

    moved = client.post(f"/api/v1/projects/{project['id']}/stage", json={"stage": "audit"})
    assert moved.status_code == 200
    assert moved.json()["stage"] == "audit"

    blocked = client.post(f"/api/v1/projects/{project['id']}/stage", json={"stage": "reservation"})
    assert blocked.status_code == 400
    assert "does not submit" in blocked.json()["detail"]

    confirm = client.post(
        f"/api/v1/projects/{project['id']}/confirmations",
        json={"kind": "reservation", "source": "state portal", "reference": "RSV-99"},
    )
    assert confirm.status_code == 200
    reserved = client.post(f"/api/v1/projects/{project['id']}/stage", json={"stage": "reservation"})
    assert reserved.status_code == 200
    assert reserved.json()["homeowner"]["claims_reservation"] is True
    assert reserved.json()["homeowner"]["claims_payment"] is False

    board = client.get("/api/v1/projects/board")
    assert board.status_code == 200
    assert any(item["id"] == project["id"] for item in board.json()["columns"]["reservation"])


def test_api_photo_proposal_work_order_links_model_and_eval(client):
    home = client.post("/api/v1/homes", json={"name": "Link house", "state_code": "GA", "postal_code": "30301"}).json()
    model = client.get(f"/api/v1/homes/{home['id']}/model").json()
    evaluation = client.post(
        f"/api/v1/homes/{home['id']}/program-evaluations",
        json={"pack_id": "ga-her-2026-11-02", "ami_band": "below_80", "measures": ["attic_insulation"]},
    ).json()
    project = client.post("/api/v1/projects", json={"home_id": home["id"]}).json()
    photo = client.post(
        f"/api/v1/projects/{project['id']}/photos",
        data={"tags": "attic,nameplate", "stage": "before"},
        files={"file": ("attic.jpg", b"not-a-real-jpeg", "image/jpeg")},
    )
    assert photo.status_code == 200, photo.text
    assert photo.json()["provider"] == "presitepro_file"
    refreshed = client.get(f"/api/v1/projects/{project['id']}").json()
    assert any(item["code"] == "attic" and item["completed"] for item in refreshed["checklist"])

    proposal = client.post(
        f"/api/v1/projects/{project['id']}/proposals",
        json={
            "title": "Attic package",
            "measures": ["attic_insulation"],
            "building_model_id": model["id"],
            "program_evaluation_id": evaluation["id"],
        },
    )
    assert proposal.status_code == 200, proposal.text
    body = proposal.json()
    assert body["building_model_id"] == model["id"]
    assert body["program_evaluation_id"] == evaluation["id"]
    assert body["program_evaluation_pack_version"] == evaluation["pack_version"]
    sent = client.post(
        f"/api/v1/proposals/{body['id']}/send",
        json={"signer_name": "Pat", "signer_email": "pat@example.com"},
    )
    assert sent.status_code == 200
    assert sent.json()["envelope_status"] == "pending_vendor"
    assert sent.json()["status"] != "signed"

    order = client.post(
        f"/api/v1/projects/{project['id']}/work-orders",
        json={"title": "Install attic", "scope": "R-49", "proposal_id": body["id"]},
    )
    assert order.status_code == 200
    assert order.json()["program_evaluation_pack_version"] == evaluation["pack_version"]
    assert order.json()["building_model_id"] == model["id"]


def test_homeowner_endpoint_has_next_step(client):
    home = client.post("/api/v1/homes", json={"name": "Owner view", "state_code": "NC", "postal_code": "27601"}).json()
    project = client.post("/api/v1/projects", json={"home_id": home["id"]}).json()
    view = client.get(f"/api/v1/projects/{project['id']}/homeowner")
    assert view.status_code == 200
    assert "what_to_do_next" in view.json()
    assert view.json()["claims_portal_submission"] is False
