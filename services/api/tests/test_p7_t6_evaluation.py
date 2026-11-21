"""P7-T6 Banglish preprocessing and local model matrix checks."""

from domains.search.banglish import NORMALIZATION_VERSION, normalize_banglish
from domains.search.evaluation import lexical_hit_rate_at_5, model_matrix


def test_banglish_normalization_is_idempotent_and_preserves_technical_tokens():
    value = "  OTP E105 RTGS BEFTN NPSB LoginModule ashche, hocche; partesi na!  "
    normalized = normalize_banglish(value)

    assert "OTP" in normalized
    assert "E105" in normalized
    assert "RTGS" in normalized
    assert "BEFTN" in normalized
    assert "NPSB" in normalized
    assert "LoginModule" in normalized
    assert normalize_banglish(normalized) == normalized
    assert NORMALIZATION_VERSION


def test_normalized_lexical_ranking_does_not_hurt_banglish_fixture():
    fixture = {
        "queries": [
            {
                "language": "Banglish",
                "incident": "transfer-timeout",
                "text": "transfer confirm korle timeout ashche",
                "candidates": [
                    {
                        "incident": "transfer-timeout",
                        "text": "transfer confirm korar por timeout hocche",
                        "grade": 2,
                    },
                    {
                        "incident": "fee-display",
                        "text": "same E105 transfer module e fee vul",
                        "grade": 0,
                    },
                ],
            }
        ]
    }

    assert lexical_hit_rate_at_5(fixture, normalize=False) == 1.0
    assert lexical_hit_rate_at_5(fixture, normalize=True) >= lexical_hit_rate_at_5(
        fixture, normalize=False
    )


def test_model_matrix_skips_absent_local_checkpoints(tmp_path):
    matrix, skipped = model_matrix(
        model_ids=["gte-multilingual-base"],
        models_dir=tmp_path,
        embedder_factory=lambda _path, _model_id: None,
        configurations=[{"name": "lexical", "mode": "lexical"}],
    )

    assert matrix
    assert skipped == ["gte-multilingual-base: missing local checkpoint"]


def test_model_matrix_uses_injected_fake_embedder_for_present_checkpoint(tmp_path):
    checkpoint = tmp_path / "fake-local-model"
    checkpoint.mkdir()
    fake = object()

    matrix, skipped = model_matrix(
        model_ids=["fake-local-model"],
        models_dir=tmp_path,
        embedder_factory=lambda _path, _model_id: fake,
    )

    assert matrix[-1]["embedder"] is fake
    assert skipped == []
