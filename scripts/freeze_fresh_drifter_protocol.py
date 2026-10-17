"""Freeze a metadata-only new-GDP-ID study before acquisition; never fits models."""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'data/public/noaa-fresh-drifter-v1'
KEYS = {'ID', 'drifter_id', 'drifter_ids', 'excluded_entire_drifter_ids',
        'development_only_drifter_ids', 'development_only', 'excluded_drifter_ids'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def existing_fixture_inventory(root=ROOT):
    """Include exposed metadata IDs as well as scored trajectories; no network."""
    identifiers, files = set(), []
    def add(value):
        if isinstance(value, str) and value.isascii() and value.isdigit() and int(value) > 0:
            identifiers.add(str(int(value)))
        elif isinstance(value, list):
            for item in value: add(item)
    def walk(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in KEYS: add(item)
                walk(item)
        elif isinstance(value, list):
            for item in value: walk(item)
    for path in sorted((root / 'data/public').rglob('*')):
        if not path.is_file() or path.suffix not in {'.csv', '.json'} or 'noaa-fresh-drifter-v1' in path.parts:
            continue
        raw = path.read_bytes()
        files.append({'path': path.relative_to(root).as_posix(), 'sha256': digest(raw), 'bytes': len(raw)})
        if path.suffix == '.json': walk(json.loads(raw))
        else:
            with path.open(newline='') as stream:
                rows = csv.reader(stream); header = next(rows, [])
                if 'ID' in header:
                    index = header.index('ID')
                    for row in rows:
                        if len(row) > index: add(row[index])
    return {'schema_version': 1, 'scope': 'ALL_EXISTING_PUBLIC_CSV_JSON_INCLUDING_EXPOSED_METADATA',
            'reserved_gdp_ids': sorted(identifiers, key=int), 'fixture_files': files}


def save_json(path, value):
    raw = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()
    with path.open('xb') as stream: stream.write(raw)
    with path.with_suffix('.sha256').open('x') as stream: stream.write(digest(raw) + '\n')
    return digest(raw)


def freeze():
    DIRECTORY.mkdir(exist_ok=True)
    if (DIRECTORY / 'protocol.json').exists(): raise ValueError('Never overwrite a frozen protocol')
    snapshot = existing_fixture_inventory()
    snapshot_hash = save_json(DIRECTORY / 'exclusions.json', snapshot)
    old_models = ['apps/ocean/reeftrace_ocean/' + name for name in ('benchmark.py', 'ablation.py', 'data.py', 'kalman.py')]
    blocks=[]
    for name, day, a,b,c,d in [('atlantic-2021','2021-06-01',0,45,-80,-20),
                              ('indian-2021','2021-06-01',-40,20,40,100),
                              ('north-pacific-2022','2022-06-01',0,45,-180,-120)]:
        blocks.append({'id':name,'start_utc':day+'T00:00:00Z','end_utc':day+'T23:00:00Z',
                       'latitude_min':a,'latitude_max':b,'longitude_min':c,'longitude_max':d})
    protocol = {
        'schema_version':1,'study_id':'noaa-fresh-gdp-id-study-v1','frozen_at_utc':datetime.now(UTC).isoformat(),
        'purpose':'Fixed algorithms on new previously unscored GDP-ID groups with known-alias exclusions; not proven statistically independent or alias-complete physical drifters.',
        'design_status':'FROZEN_NEW_GDP_ID_GROUP_EVALUATION_WITH_KNOWN_ALIAS_EXCLUSIONS',
        'acquisition_or_scores_computed':False,
        'source':{'provider':'NOAA AOML Global Drifter Program','dataset_id':'drifter_hourly_qc',
                  'base_url':'https://erddap.aoml.noaa.gov/gdp/erddap/tabledap/drifter_hourly_qc.csv',
                  'metadata_url':'https://erddap.aoml.noaa.gov/gdp/erddap/info/drifter_hourly_qc/index.json',
                  'license_name':'CC-BY-4.0','license_url':'https://creativecommons.org/licenses/by/4.0/',
                  'product_doi':'10.25921/x46c-3620'},
        'exclusions':{'snapshot_path':'exclusions.json','snapshot_sha256':snapshot_hash,
                      'reserved_gdp_id_count':len(snapshot['reserved_gdp_ids']),
                      'rule':'Re-derive from every pinned existing public CSV/JSON, including unscored metadata candidates; do not alter the snapshot or pre-existing fixtures.'},
        'alias_policy':{'identity_query':'ID,WMO&distinct()',
                        'new_candidate':'One positive canonical WMO per ID, one canonical GDP ID per WMO in frozen global metadata; candidate snapshot WMO must agree.',
                        'exclude':'Every reserved GDP ID; every known positive reserved WMO; every already selected GDP ID/WMO. No replacement after selection.',
                        'missing_reserved_alias':'Retain exact unresolved reserved IDs and counts; do not block new candidates solely because old aliases are unresolved.',
                        'claim':'New unscored GDP-ID groups with known-alias exclusions; physical_alias_resolution_verified=false if any reserved alias unresolved; statistical_independence=false.'},
        'selection':{'blocks':blocks,'target_per_block':2,'target_groups':6,
                     'metadata_columns':['ID','time','latitude','longitude','WMO','expno','location_type'],
                     'method':'First two eligible canonical GDP IDs in ascending numeric order per ordered block; exclude reserved/known-alias/shared-selected/ambiguous IDs before sorting.',
                     'no_replacements':True,'selection_frozen_before_trajectory_requests':True},
        'assignment':{'unit':'ENTIRE_CANONICAL_GDP_ID_WITH_KNOWN_WMO_EXCLUSIONS',
                      'development':'All existing exposed IDs are development/excluded only. No shared model is fitted from them in this study.',
                      'evaluation':'Every selected whole GDP ID and its complete day remain evaluation-group data.',
                      'prefix_adaptation':'Each fixed algorithm can estimate its state/parameters only from its own first18 positions. These are allowed observation context, not cross-ID training.',
                      'global_training':False,'heldout_tuning':False},
        'origin':{'training_count':18,'heldout_count':6,'cadence_s':3600,'origins_per_drifter':1,'forecast_hours':[1,2,3,4,5,6]},
        'models':{'ids':['stationary','last_drift','mean_drift','ridge_ar1','kalman_cv'],
                  'implementation_sha256':{path:digest((ROOT/path).read_bytes()) for path in old_models},
                  'ridge_alpha':1.0,'maximum_ar_spectral_radius':.98,
                  'position_std_m':100.0,'acceleration_spectral_density_m2_s3':1e-6,
                  'kalman_noise_fitting':False,'all_model_tracks_before_any_future_coordinate':True,
                  'forecast_anchor':'Kalman filtered final prefix state; other models raw final prefix position.'},
        'preprocessing':{'csv_columns':['ID','time','latitude','longitude','ve','vn','err_ve','err_vn'],
                         'units':['','UTC','degrees_north','degrees_east','m/s','m/s','m/s','m/s'],
                         'interpolation':False,'velocity_features':False,'maximum_local_position_m':50000,
                         'projection':'spherical_azimuthal_equidistant','earth_mean_radius_m':6371008.8,
                         'eligibility':'Exact requested ID/24 hourly UTC rows. Prefix map domain failures retained, never replaced. Do not exclude future truth by displacement/error.'},
        'metrics':{'ade_m':'Mean six great-circle errors; primary equal-GDP-ID macro mean.',
                   'fde_m':'Sixth-hour great-circle error; primary equal-GDP-ID macro mean.',
                   'vector_rmse_m_s':'RMS local interval displacement residual / actual interval seconds; first predicted anchor filtered for Kalman, raw for others.',
                   'primary':'Withhold every common-target model metric if any of 180 target model/horizon outcomes is missing/failed; successful per-group rows remain visible.',
                   'uncertainty':'Kalman observed ellipse uses Pxy+assumedR; nominal50/90 per-group counts only, never calibrated confidence.',
                   'failure_policy':'Preserve every six-slot group/model/horizon cell; acquisition/model/missing truth failures stay failed or unfilled. No silent successful subset ranking.'},
        'budgets':{'requests_max':11,'metadata_info_bytes':1048576,'identity_bytes':2097152,
                   'metadata_bytes_per_block':262144,'trajectory_bytes':32768,'total_bytes':4194304,
                   'timeout_s':20,'connect_timeout_s':5,'wall_time_s':180,'retries':0,'redirects':False,'fallback_endpoints':False},
        'limitations':['QC/interpolated historical NOAA positions may use future raw fixes upstream: operational_causality=false.',
                       'Same-date nearby drifters and unresolved old WMO aliases prevent claims of statistical independence.',
                       'No current forcing, observed plastic identity, physical tank trial, ecological benefit or source attribution.',
                       'No model promotion, significance claim, hyperparameter tuning, camera/provider/message actions.']}
    h=save_json(DIRECTORY/'protocol.json',protocol)
    print(json.dumps({'protocol_sha256':h,'exclusions_sha256':snapshot_hash,'reserved_ids':len(snapshot['reserved_gdp_ids']),
                      'fixture_files':len(snapshot['fixture_files']),'acquisition_or_scores_computed':False},indent=2))


if __name__ == '__main__': freeze()
