# Chalk investigator and evaluations

Implemented in `agent.py`: a bounded, case-bound shared investigator over Chalk Model Gateway. It accepts explicit settings and an injected evidence backend; scientific scores come from the immutable local source report. `evaluate.py` defaults to offline policy rehearsal; real local model calls and remote Chalk Functions runs are explicit modes. `evaluation_tasks.py` is imported only for a requested remote evaluation because the vendor decorator can deploy functions. See `docs/integrations.md` for provisioning, exact verified contracts and test scope.
