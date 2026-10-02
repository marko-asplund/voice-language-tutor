from typing import Any

from voice_tutor.domain import AppError, Review, Turn


def normalize(raw: list[dict[str, Any]]) -> list[Turn]:
    turns = []
    for i, item in enumerate(raw):
        role, text = item.get("role"), item.get("message")
        if role not in ("user", "agent") or not isinstance(text, str) or not text.strip():
            continue
        if len(text) > 1000:
            raise AppError("transcript_too_large", "A transcript turn exceeds the v1 input limit.")
        turns.append(
            Turn(
                turn_id=f"t{i + 1}",
                sequence=i,
                speaker="learner" if role == "user" else "tutor",
                text=text,
            )
        )
    if not any(t.speaker == "learner" for t in turns):
        raise AppError("no_learner_speech", "No learner speech was found.", 409)
    if sum(len(t.text) for t in turns) > 24000:
        raise AppError("transcript_too_large", "Transcript exceeds the v1 input limit.")
    return turns


def validate_evidence(review: Review, turns: list[Turn]) -> Review:
    by_id = {t.turn_id: t for t in turns}
    for mistake in review.mistakes:
        turn = by_id.get(mistake.turn_id)
        if not turn or turn.speaker != "learner" or mistake.original not in turn.text:
            raise AppError(
                "review_incomplete",
                "Review corrections failed evidence validation.",
                retryable=True,
            )
    for vocab in review.new_vocabulary:
        turn = by_id.get(vocab.turn_id)
        if (
            not turn
            or vocab.term.casefold() not in turn.text.casefold()
            or (vocab.example_kind == "conversation" and vocab.example not in turn.text)
        ):
            raise AppError(
                "review_incomplete", "Review vocabulary failed evidence validation.", retryable=True
            )
    return review
