from app.domain.programs import (
    Application,
    SavingsSnapshot,
    evaluate,
    flag_pack_change,
    get_pack,
    list_pack_summaries,
    load_packs,
    site_energy_savings_percent,
)


def test_four_state_packs_load_with_sources():
    packs = load_packs()
    assert set(packs) >= {
        "nc-homes-v2.0-2026-02",
        "nc-hear-v2.0-2026-02",
        "ga-her-2026-11-02",
        "ga-hear-limited-2026-11-02",
    }
    for pack in packs.values():
        assert pack["sources"]
        assert pack["this_product_doe_approved"] is False
        assert all(item.get("url") for item in pack["sources"])
    summaries = list_pack_summaries()
    assert all(row["this_product_doe_approved"] is False for row in summaries)


def test_nc_above_150_ineligible_for_homes_and_hear():
    snapshot = SavingsSnapshot()
    homes = evaluate(
        Application(
            pack_id="nc-homes-v2.0-2026-02",
            ami_band="above_150",
            measures=["attic_insulation"],
            existing_home=True,
            bills_twelve_months_all_fuels=True,
        ),
        snapshot,
    )
    hear = evaluate(
        Application(
            pack_id="nc-hear-v2.0-2026-02",
            ami_band="above_150",
            measures=["heat_pump_water_heater"],
            first_time_appliance={"heat_pump_water_heater": True},
        ),
        snapshot,
    )
    assert homes.overall_status == "ineligible"
    assert hear.overall_status == "ineligible"
    assert any(item.code == "income_band" and item.status == "fail" for item in homes.checks)


def test_ga_her_has_no_income_ceiling():
    result = evaluate(
        Application(
            pack_id="ga-her-2026-11-02",
            ami_band="above_150",
            measures=["attic_insulation"],
            existing_home=True,
            georgia_resident=True,
            blower_door_pre=True,
            blower_door_post=True,
        ),
        SavingsSnapshot(),
    )
    income = next(item for item in result.checks if item.code == "income_band")
    assert income.status == "pass"
    assert result.overall_status == "incomplete"  # no EnergyPlus pair


def test_ga_hear_requires_her_pairing_and_limits_measures():
    snapshot = SavingsSnapshot()
    no_pair = evaluate(
        Application(
            pack_id="ga-hear-limited-2026-11-02",
            ami_band="below_80",
            measures=["wiring"],
            georgia_resident=True,
            paired_homes_screen="none",
        ),
        snapshot,
    )
    assert no_pair.overall_status == "ineligible"
    heat_pump = evaluate(
        Application(
            pack_id="ga-hear-limited-2026-11-02",
            ami_band="below_80",
            measures=["heat_pump_space"],
            georgia_resident=True,
            paired_homes_screen="screen_passed_not_submittable",
        ),
        snapshot,
    )
    assert heat_pump.overall_status == "ineligible"
    ok = evaluate(
        Application(
            pack_id="ga-hear-limited-2026-11-02",
            ami_band="below_80",
            measures=["wiring", "panel"],
            georgia_resident=True,
            paired_homes_screen="screen_passed_not_submittable",
            docs_present={"income_docs_or_categorical": True, "id_residency_ownership_or_landlord_authorization": True, "invoice": True},
        ),
        snapshot,
    )
    assert ok.overall_status == "screen_passed_not_submittable"
    assert ok.portal_status == "not_submitted"
    assert ok.reservation_status == "not_reserved"
    assert ok.payment_status == "not_paid"
    assert ok.compliance_claim == "not_doe_approved_not_submitted"


def test_missing_energyplus_does_not_invent_percent():
    percent, check = site_energy_savings_percent(SavingsSnapshot())
    assert percent is None
    assert check.status == "not_evaluable"
    result = evaluate(
        Application(
            pack_id="nc-homes-v2.0-2026-02",
            ami_band="below_80",
            measures=["attic_insulation"],
            existing_home=True,
            bills_twelve_months_all_fuels=True,
            docs_present={
                "income_docs_or_categorical_letter": True,
                "invoice_with_address_dates_cost_rebate": True,
                "weatherization_photos": True,
                "pre_existing_insulation_levels": True,
            },
        ),
        SavingsSnapshot(),
    )
    assert result.savings_percent is None
    assert result.overall_status == "incomplete"
    assert result.this_product_doe_approved is False


def test_stored_totals_screen_is_preliminary_not_bpi():
    snapshot = SavingsSnapshot(
        both_jobs_succeeded=True,
        baseline_total_mbtu=100.0,
        upgrade_total_mbtu=70.0,
        baseline_job_id="b",
        upgrade_job_id="u",
    )
    result = evaluate(
        Application(
            pack_id="nc-homes-v2.0-2026-02",
            ami_band="below_80",
            measures=["attic_insulation"],
            existing_home=True,
            bills_twelve_months_all_fuels=True,
            docs_present={
                "income_docs_or_categorical_letter": True,
                "invoice_with_address_dates_cost_rebate": True,
                "weatherization_photos": True,
                "pre_existing_insulation_levels": True,
            },
        ),
        snapshot,
    )
    assert result.savings_percent == 30.0
    assert result.savings_band == "20_to_34"
    assert result.savings_method == "preliminary_site_energy_from_stored_energyplus_totals"
    assert result.rebate_cap_usd == 16000
    assert result.overall_status == "screen_passed_not_submittable"
    assert any(item.code == "doe_software_approval" and item.status == "not_submittable" for item in result.checks)
    assert "Not DOE-approved" in result.notes


def test_below_twenty_percent_fails_homes_screen():
    result = evaluate(
        Application(
            pack_id="ga-her-2026-11-02",
            ami_band="below_80",
            measures=["air_sealing"],
            existing_home=True,
            georgia_resident=True,
            blower_door_pre=True,
            blower_door_post=True,
        ),
        SavingsSnapshot(both_jobs_succeeded=True, baseline_total_mbtu=100.0, upgrade_total_mbtu=90.0),
    )
    assert result.savings_percent == 10.0
    assert result.overall_status == "ineligible"
    assert result.savings_band == "below_minimum"


def test_evaluation_pins_pack_version_and_flags_change_without_mutation():
    pack = get_pack("nc-hear-v2.0-2026-02")
    result = evaluate(
        Application(
            pack_id="nc-hear-v2.0-2026-02",
            ami_band="80_to_150",
            measures=["heat_pump_water_heater", "wiring"],
            first_time_appliance={"heat_pump_water_heater": True},
            existing_home=True,
            docs_present={"income_docs_or_categorical_letter": True, "invoice_with_address_dates_cost_rebate": True},
            existing_equipment_photo=True,
        ),
        SavingsSnapshot(),
    )
    assert result.pack_version == pack["pack_version"]
    original = result.pack_version
    flagged = flag_pack_change(result, {**pack, "pack_version": "9.9.9", "pack_id": pack["pack_id"]})
    assert flagged.rule_pack_changed is True
    assert flagged.pack_version == original
    assert flagged.current_pack_version == "9.9.9"


def test_qep_rejects_heat_pump_for_heat_pump():
    result = evaluate(
        Application(
            pack_id="nc-hear-v2.0-2026-02",
            ami_band="below_80",
            measures=["heat_pump_space"],
            replacing_fuel={"heat_pump_space": "electricity"},
            manual_j_uploaded=True,
            docs_present={
                "income_docs_or_categorical_letter": True,
                "invoice_with_address_dates_cost_rebate": True,
                "limited_assessment_if_heat_pump_space": True,
            },
            existing_equipment_photo=True,
        ),
        SavingsSnapshot(),
    )
    assert result.overall_status == "ineligible"
    assert any(item.code.startswith("qep_timing") and item.status == "fail" for item in result.checks)


def test_same_measure_stacking_blocked():
    result = evaluate(
        Application(
            pack_id="nc-homes-v2.0-2026-02",
            ami_band="below_80",
            measures=["attic_insulation"],
            existing_home=True,
            bills_twelve_months_all_fuels=True,
            also_applying_homes=True,
            also_applying_hear=True,
            same_measure_on_both_programs=True,
        ),
        SavingsSnapshot(),
    )
    assert any(item.code == "same_measure_stacking" and item.status == "fail" for item in result.checks)


def test_evaluate_does_not_mutate_application_measures():
    app = Application(
        pack_id="nc-hear-v2.0-2026-02",
        ami_band="below_80",
        measures=["heat_pump_water_heater", "panel"],
        first_time_appliance={"heat_pump_water_heater": True},
    )
    original = list(app.measures)
    evaluate(app, SavingsSnapshot())
    assert app.measures == original


def test_api_lists_packs_and_evaluates_without_inventing_kwh(client):
    packs = client.get("/api/v1/programs")
    assert packs.status_code == 200
    ids = {row["pack_id"] for row in packs.json()}
    assert "nc-homes-v2.0-2026-02" in ids
    home = client.post("/api/v1/homes", json={"name": "NC screen", "state_code": "NC", "postal_code": "27601"}).json()
    body = {
        "pack_id": "nc-homes-v2.0-2026-02",
        "ami_band": "below_80",
        "measures": ["attic_insulation"],
        "existing_home": True,
        "bills_twelve_months_all_fuels": True,
    }
    evaluation = client.post(f"/api/v1/homes/{home['id']}/program-evaluations", json=body)
    assert evaluation.status_code == 200, evaluation.text
    data = evaluation.json()
    assert data["savings_percent"] is None
    assert data["portal_status"] == "not_submitted"
    assert data["reservation_status"] == "not_reserved"
    assert data["payment_status"] == "not_paid"
    assert data["this_product_doe_approved"] is False
    assert data["pack_version"] == "2.0.0"
    listed = client.get(f"/api/v1/homes/{home['id']}/program-evaluations")
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == data["id"]
    assert listed.json()[0]["rule_pack_changed"] is False


def test_api_ga_hear_without_pair_is_ineligible(client):
    home = client.post("/api/v1/homes", json={"name": "GA HEAR", "state_code": "GA", "postal_code": "30301"}).json()
    evaluation = client.post(
        f"/api/v1/homes/{home['id']}/program-evaluations",
        json={"pack_id": "ga-hear-limited-2026-11-02", "ami_band": "below_80", "measures": ["wiring"], "georgia_resident": True},
    )
    assert evaluation.status_code == 200
    assert evaluation.json()["overall_status"] == "ineligible"
    assert evaluation.json()["compliance_claim"] == "not_doe_approved_not_submitted"
