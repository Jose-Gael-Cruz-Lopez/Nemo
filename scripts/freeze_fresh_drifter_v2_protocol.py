"""Preserve v1 and freeze a pre-outcome schema/transport amendment, no network."""
from __future__ import annotations
import hashlib
import json
from datetime import UTC,datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT/'data/public/noaa-fresh-drifter-v1'
DIRECTORY=ROOT/'data/public/noaa-fresh-drifter-v2'


def digest(raw):return hashlib.sha256(raw).hexdigest()


def save(path,doc):
    raw=(json.dumps(doc,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    with path.open('xb') as stream:stream.write(raw)
    with path.with_suffix('.sha256').open('x') as stream:stream.write(digest(raw)+'\n')
    return digest(raw)


def freeze():
    p=json.loads((PARENT/'protocol.json').read_text()); m=json.loads((PARENT/'manifest.json').read_text())
    if m['trajectories'] or m['evaluation_outcomes_computed'] is not False:
        raise ValueError('Pre-outcome amendment cannot follow trajectory/model outcomes')
    DIRECTORY.mkdir(exist_ok=False)
    for name in ('exclusions.json','exclusions.sha256'):
        with (DIRECTORY/name).open('xb') as stream:stream.write((PARENT/name).read_bytes())
    p.update(study_id='noaa-fresh-gdp-id-study-v2',frozen_at_utc=datetime.now(UTC).isoformat())
    p['selection']['metadata_units']=['','UTC','degrees_north','degrees_east','','count','']
    p['budgets'].update(timeout_s=45,wall_time_s=300)
    p['pre_outcome_amendment']={
        'parent_protocol_sha256':digest((PARENT/'protocol.json').read_bytes()),
        'parent_selection_sha256':digest((PARENT/'selection.json').read_bytes()),
        'parent_manifest_sha256':digest((PARENT/'manifest.json').read_bytes()),
        'parent_directory':'data/public/noaa-fresh-drifter-v1',
        'reason':['Two v1 metadata streams reached HTTP200 but ReadTimeout before body bytes.',
                  'One complete v1 metadata snapshot declared expno unit count; a new-parser empty-unit expectation rejected it.'],
        'parent_trajectory_payloads':0,'parent_model_outcomes':0,
        'preserved':'Original223exclusions, blocks, fixed models, strict alias/selection gates and all v1 raw/failure receipts.',
        'exposure':'V1 exposed selection-origin metadata and an identifier-only global ID/WMO registry, never trajectories or forecast truth/outcomes.',
        'registry_exemption':'Fresh-study v1/v2 metadata registries are not training evidence or new exclusion universes. Re-derive the unchanged original28-fixture/223-ID snapshot excluding both lineage directories.',
        'claim':'Previously unscored GDP-ID groups with known-alias exclusions and unseen future positions at selection; not IDs never appearing in selection metadata.'}
    h=save(DIRECTORY/'protocol.json',p)
    print(json.dumps({'protocol_sha256':h,'study_id':p['study_id'],'acquisition_or_scores_computed':False},indent=2))


if __name__=='__main__':freeze()
