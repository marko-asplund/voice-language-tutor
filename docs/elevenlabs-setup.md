# Private ElevenLabs agent

Live verification is pending. No agent or paid calls were created during implementation.

1. Create an ElevenLabs private agent and enable authentication. Keep agent tools disabled.
2. Choose an available **OpenAI** conversation model in the ElevenLabs dashboard, and one
   multilingual voice that supports your target language. This model runs through ElevenLabs.
3. Copy `prompts/tutor_system_prompt.md` into the agent prompt. Define the five dynamic variables:
   `target_language`, `native_language`, `level`, `topic`, `student_name`.
4. Suggested first message: "Let's practice {{target_language}}. What would you like to say about {{topic}}?"
   Adapt it into your target language for your initial agent. Configure the agent's language to
   match your initial practice language; changing the UI variable alone does not change ASR settings.
5. Start with patient turn taking: approximately 10 seconds for learner pauses, normal interruption
   enabled, short responses. These are proposed values, not tested settings. Tune with real pauses.
6. Put the key and agent ID only in the ignored `.env`. The key needs signed-URL and conversation
   read permissions. Keep the agent private; configure vendor retention to your preference.
7. Set `APP_MODE=live` and supply `OPENAI_API_KEY` and `OPENAI_REVIEW_MODEL`. Restart the server.

The backend requests `include_conversation_id=true`, keeps the issued ID if returned, and compares
it with the SDK's `getId()`. If absent, it verifies the SDK ID against the configured agent before
binding it. Final transcript retrieval checks both conversation and agent IDs.
Signed URLs only travel in the no-store connection response and are not saved in browser storage.

## Record after live verification

- Agent ID: pending (local `.env`; do not record keys here)
- OpenAI conversation model selected in ElevenLabs: pending
- Voice ID/name: pending
- Actual ASR language and turn-taking settings: pending
- Working backend OpenAI review model: pending
- Five-minute conversation / End / finalized transcript: pending

## Verified implementation contracts, 2026-10-01

- Node 24.21.0, Python 3.12.13, ElevenLabs client 1.26.0, Solid 1.9.15.
- OpenAI SDK 3.22.1 (uses httpx2), FastAPI 0.142.2; exact packages in lockfiles.
- Installed ElevenLabs declarations support `signedUrl`, `connectionType: 'websocket'`,
  `dynamicVariables`, transcript/mode/status callbacks, `getId`, `setMicMuted`, `endSession`.
- Installed SDK End path closes microphone input and audio output; browser confirmation is pending.
- OpenAI uses `responses.parse(text_format=Review)`, `store=false`, no SDK retries.

Sources: [ElevenLabs JavaScript SDK](https://elevenlabs.io/docs/eleven-agents/libraries/java-script),
[signed URL](https://elevenlabs.io/docs/eleven-agents/api-reference/conversations/get-signed-url),
[conversation details](https://elevenlabs.io/docs/eleven-agents/api-reference/conversations/get),
[OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs).
