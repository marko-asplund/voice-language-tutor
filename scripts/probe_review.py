"""Compatibility shortcut for one potentially paid synthetic OpenAI review diagnostic."""

from voice_tutor.diagnostics import cli

if __name__ == "__main__":
    raise SystemExit(cli(["--provider", "openai", "--live"]))
