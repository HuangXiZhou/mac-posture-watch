# Security Policy

## Sensitive Data

Do not include real API keys, Bark endpoints, camera captures, debug frames, logs, or baseline data in issues, pull requests, or commits.

Use `.env.example` for placeholders only. Real `.env` files are ignored by Git.

Before pushing:

```bash
git status --short
rg -n --hidden --glob '!.git/**' --glob '!.venv/**' \
  "sk-[A-Za-z0-9_-]{20,}|BEGIN (RSA|OPENSSH|PRIVATE) KEY|api\\.day\\.app/[A-Za-z0-9_-]{12,}" .
```

Enable GitHub secret scanning and push protection for the repository when available.

## Reporting

If you find a privacy or security issue, open a GitHub issue without sensitive payloads. If reproduction requires secrets or images, describe the minimal steps and redact all private data.
