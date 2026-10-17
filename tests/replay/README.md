# Replay evidence

Committed computational fixtures are in `data/sample_runs/`; they explicitly say SYNTHETIC. `scripts/evaluate.py` reads observation inputs separately from evaluator-only truth and reports abstention/invalidity separately from accuracy among ranked cases. The local API `/demo/load` exercises the actual stored-case/model path. Real USB recordings require independent measured profiles and a separate held-out experiment; no real tank recording is bundled.
