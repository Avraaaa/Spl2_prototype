"""P0-T2 / EX-05: the committed OpenAPI contract is generated from DRF and stays current."""

from pathlib import Path

import yaml
from django.core.management import call_command

CONTRACT = Path(__file__).resolve().parents[3] / "contracts" / "openapi.yaml"


def _generate(tmp_path: Path) -> str:
    out = tmp_path / "openapi.yaml"
    call_command("spectacular", "--file", str(out), "--validate", "--fail-on-warn")
    return out.read_text(encoding="utf-8")


def test_schema_generates_and_validates(tmp_path: Path) -> None:
    schema = yaml.safe_load(_generate(tmp_path))
    assert schema["openapi"].startswith("3.")
    assert "/api/health/" in schema["paths"]
    # The schema endpoint documents the API but is not itself part of the contract.
    assert "/api/schema/" not in schema["paths"]


def test_committed_contract_is_not_stale(tmp_path: Path) -> None:
    generated = _generate(tmp_path)
    committed = CONTRACT.read_text(encoding="utf-8").replace("\r\n", "\n")
    assert generated.replace("\r\n", "\n") == committed, (
        "contracts/openapi.yaml is stale: run `node scripts/check-contract.mjs --write`"
    )
