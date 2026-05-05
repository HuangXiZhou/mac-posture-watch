# Privacy

`mac-posture-watch` is designed to keep sensitive camera data local by default.

## Local Data

The app stores runtime files under:

```text
~/Library/Application Support/posture-watch/
```

Baseline data is stored as JSON and contains normalized geometry, not images. It is still personal biometric-adjacent data, so treat it as private.

## Network Behavior

No network call is made for posture detection unless all of the following are true:

- `ENABLE_LLM_VERIFY=1`;
- `OPENAI_API_KEY` and `OPENAI_MODEL` are configured;
- the local rolling window has already crossed the verification threshold;
- LLM rate limits allow another call.

Bark notification uses the configured Bark endpoint if present.

## Git Safety

The repository ignores:

- `.env` and `.env.*`;
- baseline files;
- logs;
- debug frames;
- common image and video capture formats.

Before committing, run:

```bash
git status --short
```

Do not commit real API keys, Bark keys, camera captures, debug frames, or local calibration files.

