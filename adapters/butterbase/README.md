# Butterbase AI integration

The investigator uses Butterbase's documented AI gateway via
`apps/core/reeftrace_core/butterbase.py`. Dashboard, Photon and local replay share
this adapter and the bounded local tool loop.

Runtime `.env`:

- `BUTTERBASE_API_URL=https://api.butterbase.ai` (origin only, no `/v1`).
- `BUTTERBASE_API_KEY`: personal API key with `ai:gateway` scope.
- `BUTTERBASE_MODEL`: exact ID from authenticated model discovery.
- `BUTTERBASE_ACCOUNT_ID`: local account metadata; never used as credentials.

No app ID, provider connection, environment ID or additional SDK is needed.
`httpx` is already installed. Authenticated calls use bearer authentication at
`/v1/models` and `/v1/chat/completions`. Credentials remain server-side.

```sh
python scripts/check_butterbase.py --public
python scripts/check_butterbase.py
python scripts/check_butterbase.py --test
python -m eval.run_replay data/replay/agent.synthetic.jsonl
```

The public catalog requires no key; it does not verify account permissions. Test
and replay requests consume the account's AI credits. Missing configuration fails
closed. Status-code guidance never prints raw vendor error bodies or secrets.

Source evidence and approval state remain in local SQLite. No database sync or
external upload is enabled. A remote storage implementation would require a
separately verified app ID/schema and deliberate data-sharing configuration.

Reference: https://docs.butterbase.ai/api-reference/ai-api/
