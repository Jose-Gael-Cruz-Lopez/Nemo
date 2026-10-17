# Optional legacy Butterbase adapter

The active workspace uses direct Gemini inference and Neon Postgres (or SQLite
when DATABASE_URL is empty). The earlier `/v1` investigator retains Butterbase
as an explicit alternative through `REEFTRACE_AI_PROVIDER=butterbase`.
The new `/api/v1` workspace and Photon worker use Gemini; no Chalk key is needed.
