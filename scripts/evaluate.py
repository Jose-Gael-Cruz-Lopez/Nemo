"""Run inference first; load evaluator-only labels only for scoring saved outputs."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from apps.estimation.reeftrace_estimation import estimate


def evaluate(profile, observations, truths, *, seed=7):
    start=time.perf_counter()
    # Truth is never passed to estimate, even for synthetic cases.
    predictions=[estimate(profile, observation, seed=seed) for observation in observations]
    elapsed=time.perf_counter()-start
    labels={x['case_id']:x for x in truths['cases']}
    attempts=len(predictions)
    ranked=[p for p in predictions if p['status']=='ranked']
    unknown=[p for p in predictions if p['status']=='unknown']
    invalid=[p for p in predictions if p['status']=='invalid']
    correct=sum(p['ranked_source']==labels[p['case_id']].get('actual_source') for p in ranked)
    status_checks=sum(p['status']==labels[p['case_id']].get('expected_status') for p in predictions)
    # A disclosed trivial baseline; no tuned source-frequency labels are used.
    equal_prior_top1_accuracy=1/len(profile['sources'])
    return {'scope':'SYNTHETIC software behavior only; not physical or marine validation',
        'data_origin':profile['data_origin'],'physical_validation':False,'attempted':attempts,
        'ranked':len(ranked),'unknown':len(unknown),'invalid':len(invalid),
        'ranked_coverage_all_attempts':len(ranked)/attempts if attempts else None,
        'accuracy_among_ranked':correct/len(ranked) if ranked else None,
        'wrong_rankings':len(ranked)-correct,
        'unknown_rate':len(unknown)/attempts if attempts else None,
        'invalid_rate':len(invalid)/attempts if attempts else None,
        'expected_status_checks':{'passed':status_checks,'total':attempts},
        'baseline_uniform_random_source_expected_top1_accuracy':equal_prior_top1_accuracy,
        'baseline_scope':'analytical 1/K for candidate-only labels; not a fitted or measured baseline',
        'runtime_s':elapsed,'seed':seed,'predictions':predictions}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'work/synthetic-evaluation.json')
    args=parser.parse_args()
    folder=ROOT/'data/sample_runs'
    profile=json.loads((folder/'synthetic_profile.json').read_text())
    observations=json.loads((folder/'synthetic_observations.json').read_text())
    truth=json.loads((folder/'evaluation_truth.json').read_text())
    report=evaluate(profile,observations,truth)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='predictions'},indent=2))
    print('Saved',args.output)


if __name__=='__main__':
    main()
