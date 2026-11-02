from app.domain.building import apply_attic_insulation, default_payload
from app.domain.packages import apply_measures, baseline_post_consistency, enumerate_packages

from .report import write_artifact


def test_every_package_is_ecm_only():
    baseline = default_payload()
    reports = []
    for spec in enumerate_packages():
        upgraded = apply_measures(baseline, spec.measures)
        report = baseline_post_consistency(baseline, upgraded, list(spec.measures))
        assert report.ok, (spec.name, report.unexpected)
        reports.append({"name": spec.name, "changed": report.changed, "ok": report.ok})
    attic_only = apply_attic_insulation(baseline, 49.0)
    attic_report = baseline_post_consistency(baseline, attic_only, ["attic_insulation"])
    assert attic_report.ok
    write_artifact(
        "baseline-post",
        {"packages": reports, "attic_insulation_slice": {"ok": attic_report.ok, "changed": attic_report.changed}},
    )
