# Chalk v3

Live gateway: `apps/core/reeftrace_core/agent.py`. Configure `.env` variables
CHALK_ROUTER_API_KEY, CHALK_ENV_ID, CHALK_MODEL, CHALK_ROUTER_BASE_URL. Calls use
bearer authentication and X-Chalk-Env-Id. Tool arithmetic remains local Python.

Fixture-only local evaluation: `python -m eval.run_replay data/replay/agent.synthetic.jsonl`.
It uses actual Chalk requests only when explicitly run with configured credentials.
Hosted Chalk evaluations still need remote package provisioning and account access;
no managed evaluation was deployed during implementation.
