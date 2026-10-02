# Required ElevenLabs setup

## 1. Configure the private agent

In the ElevenLabs dashboard:

- Create a private agent and enable authentication.
- Select an available **OpenAI conversation model** and a voice that supports your target language.
- Set the agent's language to your practice language. The UI's target-language variable guides
  the tutor prompt; it does not change the agent's speech-recognition language configuration.
- Copy [tutor_system_prompt.md](../prompts/tutor_system_prompt.md) into the agent's system prompt.
  Ensure these dynamic variables are defined: `target_language`, `native_language`, `level`,
  `topic`, `student_name`. The app supplies all five when connecting.
- Keep agent tools disabled for this app.

## 2. Create the API key

Create an ElevenLabs API key with **ElevenAgents write permission**. Read-only access was
insufficient in this project's setup; enabling write permission was required for the connection
flow. The key also needs access to read conversation details so the backend can retrieve the final
transcript. Use the key with the private agent configured above.

## 3. Configure the local app

After `make setup`, edit the ignored local `.env`:

```dotenv
APP_MODE=live
ELEVENLABS_API_KEY=<your ElevenLabs API key>
ELEVENLABS_AGENT_ID=<your private agent ID>
OPENAI_API_KEY=<your OpenAI API key>
OPENAI_REVIEW_MODEL=<a model supporting Responses structured output>
```

Replace the placeholders locally and keep `.env` private (`chmod 600 .env`). OpenAI settings are
required because the app uses a separate backend OpenAI request for the post-session text review.
Restart `make serve`, open http://localhost:8000, and allow microphone access when you press Start.

References: [agent authentication](https://elevenlabs.io/docs/eleven-agents/customization/authentication),
[dynamic variables](https://elevenlabs.io/docs/eleven-agents/customization/personalization/dynamic-variables),
[signed URLs](https://elevenlabs.io/docs/eleven-agents/api-reference/conversations/get-signed-url).
