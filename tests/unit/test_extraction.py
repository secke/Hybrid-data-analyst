from __future__ import annotations

from agent.llm.extraction import extract_fenced_code


def test_extract_fenced_code_with_language_tag() -> None:
    text = "Voici:\n```python\nresult = 1\n```\nFin."
    assert extract_fenced_code(text) == "result = 1"


def test_extract_fenced_code_with_sql_tag() -> None:
    text = "```sql\nSELECT 1\n```"
    assert extract_fenced_code(text) == "SELECT 1"


def test_extract_fenced_code_without_language_tag() -> None:
    text = "```\nSELECT 1\n```"
    assert extract_fenced_code(text) == "SELECT 1"


def test_extract_fenced_code_falls_back_to_raw_text() -> None:
    assert extract_fenced_code("  result = 1  ") == "result = 1"


def test_extract_fenced_code_takes_first_block_when_multiple() -> None:
    text = "```python\nresult = 1\n```\nsome text\n```python\nresult = 2\n```"
    assert extract_fenced_code(text) == "result = 1"


def test_extract_fenced_code_preserves_internal_newlines() -> None:
    text = "```python\nimport pandas as pd\nresult = pd.DataFrame()\n```"
    assert extract_fenced_code(text) == "import pandas as pd\nresult = pd.DataFrame()"
