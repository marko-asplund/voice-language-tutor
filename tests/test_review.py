import pytest
from pydantic import ValidationError

from voice_tutor.config import Settings
from voice_tutor.domain import AppError, Mistake, Review
from voice_tutor.services.review import normalize, validate_evidence


@pytest.fixture
def turns():
    return normalize(
        [
            {"role": "agent", "message": "I went to the market."},
            {"role": "user", "message": "Yesterday I go to the market."},
            {"role": "user", "message": None},
        ]
    )


def review(**kwargs):
    return Review(
        schema_version="1",
        summary="Practice review.",
        mistakes=[],
        new_vocabulary=[],
        suggested_next_topics=["Food", "Family", "Travel"],
        **kwargs,
    )


def test_normalization_and_zero_errors(turns):
    assert [t.turn_id for t in turns] == ["t1", "t2"]
    assert validate_evidence(review(), turns).mistakes == []


@pytest.mark.parametrize(
    "turn_id,original", [("t1", "went"), ("t2", "invented"), ("missing", "go")]
)
def test_correction_requires_learner_quote(turns, turn_id, original):
    result = review()
    result.mistakes = [
        Mistake(
            turn_id=turn_id,
            original=original,
            corrected="went",
            explanation="Past tense.",
            category="grammar",
        )
    ]
    with pytest.raises(AppError, match="review_incomplete"):
        validate_evidence(result, turns)


def test_vocabulary_attestation_and_example_label(turns):
    from voice_tutor.domain import Vocabulary

    result = review()
    result.new_vocabulary = [
        Vocabulary(
            turn_id="t1",
            term="market",
            translation="mercado",
            example="I like this market.",
            example_kind="generated",
        )
    ]
    validate_evidence(result, turns)
    result.new_vocabulary[0].example_kind = "conversation"
    with pytest.raises(AppError):
        validate_evidence(result, turns)
    result.new_vocabulary[0].term = "unattested"
    with pytest.raises(AppError):
        validate_evidence(result, turns)


@pytest.mark.parametrize(
    "raw", [[], [{"role": "agent", "message": "Hello"}], [{"role": "user", "message": "  "}]]
)
def test_empty_learner_speech(raw):
    with pytest.raises(AppError, match="no_learner_speech"):
        normalize(raw)


def test_oversized_transcript():
    with pytest.raises(AppError, match="transcript_too_large"):
        normalize([{"role": "user", "message": "a" * 1001}])


def test_live_configuration_hides_inputs():
    with pytest.raises(ValidationError) as exc:
        Settings(_env_file=None, app_mode="live", openai_api_key="synthetic-test-secret")
    assert "synthetic-test-secret" not in str(exc.value)
    assert "ELEVENLABS_API_KEY" in str(exc.value)
