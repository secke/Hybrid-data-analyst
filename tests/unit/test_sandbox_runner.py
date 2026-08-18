"""Teste le sandbox contre le vrai Docker local. Aucun appel LLM. Nécessite
l'image `hybrid-data-analyst-sandbox:latest` (docker build -t
hybrid-data-analyst-sandbox:latest sandbox/)."""

from __future__ import annotations

import pandas as pd
import pytest

from agent.sandbox.runner import check_docker_available, ensure_sandbox_image_exists, run_code

pytestmark = pytest.mark.skipif(
    not check_docker_available() or not ensure_sandbox_image_exists(),
    reason="Docker ou l'image sandbox ne sont pas disponibles",
)


def test_run_code_returns_scalar_result() -> None:
    result = run_code("result = 2 + 2")
    assert result.ok
    assert result.result_value == 4


def test_run_code_returns_dict_result() -> None:
    result = run_code("result = {'a': 1, 'b': 2}")
    assert result.ok
    assert result.result_value == {"a": 1, "b": 2}


def test_run_code_uses_input_dataframe() -> None:
    df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
    result = run_code("result = df.assign(c=df.a + df.b)", input_df=df)
    assert result.ok
    assert result.result_dataframe is not None
    assert result.result_dataframe["c"].tolist() == [5, 7, 9]


def test_run_code_captures_traceback_on_error() -> None:
    result = run_code("result = 1 / 0")
    assert not result.ok
    assert "ZeroDivisionError" in (result.error or "")


def test_run_code_has_no_network_access() -> None:
    code = """
import urllib.request
try:
    urllib.request.urlopen("http://example.com", timeout=3)
    result = "REACHED"
except Exception as e:
    result = f"BLOCKED: {type(e).__name__}"
"""
    result = run_code(code, timeout_seconds=10)
    assert result.ok
    assert result.result_value.startswith("BLOCKED")


def test_run_code_runs_as_non_root() -> None:
    result = run_code("import os\nresult = os.getuid()")
    assert result.ok
    assert result.result_value == 1000


def test_run_code_filesystem_is_read_only_outside_workspace() -> None:
    code = """
try:
    with open("/etc/malicious", "w") as f:
        f.write("x")
    result = "WROTE"
except Exception as e:
    result = f"BLOCKED: {type(e).__name__}"
"""
    result = run_code(code, timeout_seconds=10)
    assert result.ok
    assert result.result_value.startswith("BLOCKED")


def test_run_code_times_out_on_infinite_loop() -> None:
    result = run_code("while True:\n    pass", timeout_seconds=3)
    assert not result.ok
    assert result.timed_out


def test_run_code_reports_missing_result_variable() -> None:
    result = run_code("x = 1")  # ni `result` ni `fig`
    assert not result.ok
    assert "result" in (result.error or "")


CHART_CODE = """
import plotly.express as px
fig = px.bar(df, x="category", y="amount", title="Test")
"""


def test_run_code_exports_chart_and_can_combine_with_result() -> None:
    # Un seul test combinant les deux assertions (plutôt que deux tests
    # séparés) : chaque test qui lance Chrome/kaleido a un coût de démarrage
    # non négligeable, à minimiser dans la suite.
    df = pd.DataFrame({"category": ["A", "B"], "amount": [10, 20]})
    code = CHART_CODE + "\nresult = {'total': int(df['amount'].sum())}"
    result = run_code(code, input_df=df, timeout_seconds=60)
    assert result.ok, result.error
    assert result.result_value == {"total": 30}
    assert result.chart_png_bytes is not None
    assert result.chart_png_bytes[:8] == b"\x89PNG\r\n\x1a\n"  # signature PNG
    assert result.chart_html is not None
    assert "plotly" in result.chart_html.lower()
