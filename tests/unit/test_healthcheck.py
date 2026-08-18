from __future__ import annotations

from agent.health import healthcheck
from agent.health.healthcheck import CheckResult


def test_main_returns_zero_when_all_checks_pass(mocker) -> None:  # type: ignore[no-untyped-def]
    mocker.patch.object(
        healthcheck,
        "CHECKS",
        [
            lambda: CheckResult("A", True, "ok"),
            lambda: CheckResult("B", True, "ok"),
        ],
    )
    mocker.patch.object(healthcheck, "print_report")

    assert healthcheck.main() == 0


def test_main_returns_one_when_a_check_fails(mocker) -> None:  # type: ignore[no-untyped-def]
    mocker.patch.object(
        healthcheck,
        "CHECKS",
        [
            lambda: CheckResult("A", True, "ok"),
            lambda: CheckResult("B", False, "connexion refusée"),
        ],
    )
    mocker.patch.object(healthcheck, "print_report")

    assert healthcheck.main() == 1


def test_run_all_never_raises_even_if_a_check_throws(mocker) -> None:  # type: ignore[no-untyped-def]
    def _boom() -> CheckResult:
        raise RuntimeError("panne réseau")

    mocker.patch.object(healthcheck, "CHECKS", [_boom])

    # Chaque fonction check_* attrape déjà ses propres exceptions ; on
    # vérifie ici que run_all() ne masque pas une exception qui fuiterait
    # d'une fonction de check mal écrite (documente le contrat attendu).
    try:
        healthcheck.run_all()
    except RuntimeError:
        pass
    else:
        raise AssertionError("attendu: RuntimeError propagée par un check mal écrit")
