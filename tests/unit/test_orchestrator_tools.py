"""Teste les outils de l'agent (Phase 8) : chaque pipeline sous-jacent
(déjà testé par ailleurs, par pipeline - Phases 1-6) est mocké ici. Seul le
comportement propre à la couche outil est vérifié : forme du résumé renvoyé
au modèle, mise à jour de l'état de session, garde-fous de prérequis
("pas de données chargées")."""

from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd

import agent.orchestrator.tools as tools_module
from agent.export.storage import UploadedArtifact
from agent.federation.pipeline import FederatedPipelineResult
from agent.orchestrator.state import SessionState
from agent.python_exec.pipeline import PythonPipelineResult
from agent.sql.pipeline import PipelineResult
from agent.viz.pipeline import ChartPipelineResult
from agent.viz.storage import SavedChart

DF = pd.DataFrame({"category_name": ["Beverages", "Produce"], "n": [10, 5]})


def _fake_bedrock_client() -> MagicMock:
    client = MagicMock()
    client.last_result = MagicMock(input_tokens=100, output_tokens=20)
    client.last_model_id = "fake-model"
    client.last_cost_usd = 0.001
    return client


def _fake_session() -> SessionState:
    return SessionState(bedrock_client=_fake_bedrock_client())


def _fake_ctx() -> MagicMock:
    return MagicMock()


# --------------------------------------------------------------------------
# tool_query_data
# --------------------------------------------------------------------------


def test_tool_query_data_success_updates_session(mocker) -> None:  # type: ignore[no-untyped-def]
    mocker.patch.object(
        tools_module,
        "answer_question",
        return_value=PipelineResult(
            question="q", ok=True, sql="SELECT 1", columns=["n"], rows=[{"n": 1}], row_count=1
        ),
    )
    mocker.patch.object(tools_module, "sql_rows_to_dataframe", return_value=DF)
    mocker.patch.object(tools_module, "append_entry")

    session = _fake_session()
    execution = tools_module.tool_query_data(_fake_ctx(), session, "Combien de produits ?")

    assert execution.llm_summary["ok"] is True
    assert execution.llm_summary["sql"] == "SELECT 1"
    assert execution.llm_summary["row_count"] == 1
    assert session.last_dataframe is DF
    assert session.last_sql == "SELECT 1"
    assert session.last_source == "northwind"


def test_tool_query_data_failure_leaves_session_untouched(mocker) -> None:  # type: ignore[no-untyped-def]
    mocker.patch.object(
        tools_module,
        "answer_question",
        return_value=PipelineResult(question="q", ok=False, sql=None),
    )
    mocker.patch.object(tools_module, "append_entry")

    session = _fake_session()
    execution = tools_module.tool_query_data(_fake_ctx(), session, "question impossible")

    assert execution.llm_summary["ok"] is False
    assert session.last_dataframe is None


# --------------------------------------------------------------------------
# tool_query_federated_data
# --------------------------------------------------------------------------


def test_tool_query_federated_data_success_updates_session(mocker) -> None:  # type: ignore[no-untyped-def]
    ctx = _fake_ctx()
    ctx.federated.return_value = (MagicMock(), {}, {})
    mocker.patch.object(tools_module, "fetch_rates", return_value={"USD": 1.3, "EUR": 1.15})
    mocker.patch.object(
        tools_module,
        "answer_federated_question",
        return_value=FederatedPipelineResult(
            question="q", ok=True, sql="SELECT 1", columns=["n"], rows=[{"n": 1}], row_count=1
        ),
    )
    mocker.patch.object(tools_module, "append_entry")

    session = _fake_session()
    execution = tools_module.tool_query_federated_data(ctx, session, "compare les sources")

    assert execution.llm_summary["ok"] is True
    assert session.last_source == "federated"


def test_tool_query_federated_data_currency_failure_is_not_blocking(mocker) -> None:  # type: ignore[no-untyped-def]
    ctx = _fake_ctx()
    ctx.federated.return_value = (MagicMock(), {}, {})
    mocker.patch.object(tools_module, "fetch_rates", side_effect=RuntimeError("API indisponible"))
    mocker.patch.object(
        tools_module,
        "answer_federated_question",
        return_value=FederatedPipelineResult(question="q", ok=True, sql="SELECT 1", row_count=0),
    )
    mocker.patch.object(tools_module, "append_entry")

    execution = tools_module.tool_query_federated_data(ctx, _fake_session(), "compare les sources")

    assert execution.llm_summary["ok"] is True


# --------------------------------------------------------------------------
# tool_compute
# --------------------------------------------------------------------------


def test_tool_compute_requires_existing_dataframe() -> None:
    execution = tools_module.tool_compute(_fake_ctx(), _fake_session(), "moyenne ?")

    assert execution.llm_summary["ok"] is False
    assert "query_data" in execution.llm_summary["error"]


def test_tool_compute_success_with_dataframe_result(mocker) -> None:  # type: ignore[no-untyped-def]
    result_df = pd.DataFrame({"total": [15]})
    mocker.patch.object(
        tools_module,
        "answer_with_computation",
        return_value=PythonPipelineResult(
            question="q", ok=True, code="result = df", result_dataframe=result_df
        ),
    )
    mocker.patch.object(tools_module, "append_entry")

    session = _fake_session()
    session.last_dataframe = DF
    execution = tools_module.tool_compute(_fake_ctx(), session, "somme totale ?")

    assert execution.llm_summary["ok"] is True
    assert execution.llm_summary["result_type"] == "dataframe"
    assert execution.display["result_dataframe"] is result_df


def test_tool_compute_success_with_scalar_result(mocker) -> None:  # type: ignore[no-untyped-def]
    mocker.patch.object(
        tools_module,
        "answer_with_computation",
        return_value=PythonPipelineResult(
            question="q", ok=True, code="result = {'total': 15}", result_value={"total": 15}
        ),
    )
    mocker.patch.object(tools_module, "append_entry")

    session = _fake_session()
    session.last_dataframe = DF
    execution = tools_module.tool_compute(_fake_ctx(), session, "somme totale ?")

    assert execution.llm_summary["result_type"] == "value"
    assert execution.llm_summary["result"] == {"total": 15}


# --------------------------------------------------------------------------
# tool_visualize
# --------------------------------------------------------------------------


def test_tool_visualize_requires_existing_dataframe() -> None:
    execution = tools_module.tool_visualize(_fake_ctx(), _fake_session(), "trace un graphique")

    assert execution.llm_summary["ok"] is False


def test_tool_visualize_success_updates_session(mocker, tmp_path) -> None:  # type: ignore[no-untyped-def]
    mocker.patch.object(
        tools_module,
        "generate_chart",
        return_value=ChartPipelineResult(
            question="q",
            ok=True,
            code="fig = ...",
            chart_png_bytes=b"PNGDATA",
            chart_html="<html/>",
        ),
    )
    mocker.patch.object(
        tools_module,
        "save_chart",
        return_value=SavedChart(png_path=tmp_path / "c.png", html_path=tmp_path / "c.html"),
    )
    mocker.patch.object(tools_module, "comment_on_chart", return_value="Le graphique montre...")
    mocker.patch.object(tools_module, "append_entry")

    session = _fake_session()
    session.last_dataframe = DF
    execution = tools_module.tool_visualize(_fake_ctx(), session, "trace un graphique")

    assert execution.llm_summary["ok"] is True
    assert execution.llm_summary["commentary"] == "Le graphique montre..."
    assert session.last_chart_png == b"PNGDATA"
    assert session.last_chart_question == "trace un graphique"


# --------------------------------------------------------------------------
# tool_export_files
# --------------------------------------------------------------------------


def test_tool_export_files_requires_existing_dataframe() -> None:
    execution = tools_module.tool_export_files(_fake_ctx(), _fake_session(), ["csv"])

    assert execution.llm_summary["ok"] is False


def test_tool_export_files_success_builds_urls(mocker, tmp_path) -> None:  # type: ignore[no-untyped-def]
    mocker.patch.object(tools_module, "EXPORT_DIR", tmp_path)
    mocker.patch.object(tools_module, "write_csv", return_value=tmp_path / "export.csv")
    mocker.patch.object(
        tools_module,
        "upload_artifact",
        return_value=UploadedArtifact(object_name="export.csv", url="http://minio/export.csv"),
    )

    session = _fake_session()
    session.last_dataframe = DF
    execution = tools_module.tool_export_files(_fake_ctx(), session, ["csv"])

    assert execution.llm_summary["ok"] is True
    assert execution.llm_summary["files"] == {"csv": "http://minio/export.csv"}


# --------------------------------------------------------------------------
# tool_generate_report
# --------------------------------------------------------------------------


def test_tool_generate_report_requires_existing_dataframe() -> None:
    execution = tools_module.tool_generate_report(_fake_ctx(), _fake_session(), "rapport ?")

    assert execution.llm_summary["ok"] is False


def test_tool_generate_report_success(mocker, tmp_path) -> None:  # type: ignore[no-untyped-def]
    mocker.patch.object(tools_module, "REPORT_DIR", tmp_path)
    mocker.patch.object(tools_module, "generate_narrative", return_value="Analyse narrative.")
    mocker.patch.object(
        tools_module, "write_traceable_report_pdf", return_value=tmp_path / "rapport.pdf"
    )
    mocker.patch.object(
        tools_module,
        "upload_artifact",
        return_value=UploadedArtifact(object_name="rapport.pdf", url="http://minio/rapport.pdf"),
    )
    mocker.patch.object(tools_module, "append_entry")

    session = _fake_session()
    session.last_dataframe = DF
    session.last_sql = "SELECT 1"
    execution = tools_module.tool_generate_report(_fake_ctx(), session, "rapport sur les ventes")

    assert execution.llm_summary["ok"] is True
    assert execution.llm_summary["report_url"] == "http://minio/rapport.pdf"
    assert execution.llm_summary["narrative"] == "Analyse narrative."


# --------------------------------------------------------------------------
# tool_synthesize_reviews
# --------------------------------------------------------------------------


def test_tool_synthesize_reviews_no_data_available(mocker) -> None:  # type: ignore[no-untyped-def]
    mocker.patch.object(tools_module, "reviews_available", return_value=False)

    execution = tools_module.tool_synthesize_reviews(_fake_ctx(), _fake_session())

    assert execution.llm_summary["ok"] is False


def test_tool_synthesize_reviews_success(mocker) -> None:  # type: ignore[no-untyped-def]
    mocker.patch.object(tools_module, "reviews_available", return_value=True)
    mocker.patch.object(
        tools_module, "sample_reviews", return_value=pd.DataFrame({"review": ["top"]})
    )
    mocker.patch.object(tools_module, "synthesize_reviews", return_value="Globalement positif.")
    mocker.patch.object(tools_module, "append_entry")

    execution = tools_module.tool_synthesize_reviews(_fake_ctx(), _fake_session())

    assert execution.llm_summary["ok"] is True
    assert execution.llm_summary["synthesis"] == "Globalement positif."


# --------------------------------------------------------------------------
# TOOL_SPECS
# --------------------------------------------------------------------------


def test_tool_specs_names_match_tool_functions() -> None:
    names = {spec["toolSpec"]["name"] for spec in tools_module.TOOL_SPECS}

    assert names == {
        "query_data",
        "query_federated_data",
        "compute",
        "visualize",
        "export_files",
        "generate_report",
        "synthesize_reviews",
    }
