# Gemini investigator and local evaluation

`agent.py` calls the Gemini OpenAI-compatible endpoint directly with explicit
`GeminiSettings`, a case-bound backend and bounded request/turn deadlines.
Scientific scores come from frozen estimator reports; the model cannot restate
numerical scores, upgrade Unknown, approve recovery, or operate hardware.

`evaluate.py` preserves the incoming frozen policy fixtures and offline scoring.
Run `python -m adapters.gemini.evaluate --mode local` for scripted rehearsal,
or add `--live-model` for explicit Gemini requests. Hosted Chalk deployments
and the Chalk SDK are removed from this branch.
