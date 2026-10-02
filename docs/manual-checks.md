# Local checks

Automated checks are offline. Real acceptance checks below are pending, not claimed complete.

## Simulation

Run `make setup`, `make check`, `make serve`. Open http://localhost:8000 in the Windows browser.
The simulation banner must be visible. Start displays two sample turns without requesting a mic;
End shows the finalized synthetic transcript and a clearly simulated review. Repeated button clicks
must not create duplicate calls. Refresh loses the UI session; restart clears all in-memory sessions.

## Live voice first

Configure the private agent using `elevenlabs-setup.md`; edit `.env` locally and set `APP_MODE=live`.
Never paste keys into chat. Restart using `make serve`.

- Deny mic permission: clear error, Start available afterward, no conversation minted.
- Start, speak, and confirm ordered live learner/tutor transcript and listening/speaking state.
- Mute/unmute, pause for several seconds, code-switch, stay silent, and interrupt the tutor.
- End: browser mic indicator disappears, playback stops, finalized transcript replaces live events.
- Disconnect: partial-review label, bounded waiting, clear failure/retry if necessary.
- Repeat Start/End rapidly: only one active conversation and one review task.
- Have a five-minute session; confirm appropriate A2/B1/C1 complexity and relevant follow-ups.
- Copy tuned prompt/settings from the dashboard back into the prompt/setup documentation.

## Grounded review

- Confirm review model supports Responses structured output using a synthetic transcript first
  (`make probe-review`, a deliberate paid text request; no voice call).
- Confirm real review explanations use the native language and examples use the target language.
- Every correction's original is an excerpt of the cited learner turn. Zero errors is valid.
- Vocabulary terms are attested; generated examples are labeled. No pronunciation claims.
- Try empty learner speech and failed provider access/credits. No endless spinner or raw payload.
- Review refusal is terminal; explicit retry for transient failure can repeat an upstream request.
- Measure End -> transcript ready -> review ready; aim for under 60 seconds after finalization.

Record actual results in PROGRESS.md and docs/elevenlabs-setup.md without private speech or keys.
