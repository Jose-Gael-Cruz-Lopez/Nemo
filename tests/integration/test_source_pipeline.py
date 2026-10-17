import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apps.api.reeftrace_api.core.settings import Settings
from apps.api.reeftrace_api.main import create_app


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(Settings(data_dir=tmp_path,local_token='test-token'))) as c:
        yield c


HEADERS={'Authorization':'Bearer test-token'}


def test_demo_api_evidence_unknown_invalid_and_disabled_chalk(client):
    assert client.post('/api/v1/demo/load',json={}).status_code==401
    r=client.post('/api/v1/demo/load',json={},headers=HEADERS)
    assert r.status_code==200,r.text
    cases=r.json()['cases']
    assert [x['evidence']['status'] for x in cases]==['ranked','unknown','invalid']
    assert cases[1]['evidence']['reason_codes']==['AMBIGUOUS_SOURCES']
    assert cases[0]['evidence']['confidence_kind']=='relative_support_not_probability'
    for item in cases:
        cid=item['case']['id'];eid=item['evidence']['id']
        assert client.get(f'/api/v1/cases/{cid}/evidence').json()['id']==eid
        assert client.post('/api/v1/actions/propose',json={'case_id':cid,'evidence_id':eid},headers=HEADERS).status_code==409
    cid=cases[0]['case']['id']
    result=client.post(f'/api/v1/cases/{cid}/investigate',json={'text':'What does this evidence support?'},headers=HEADERS)
    assert result.status_code==200,result.text
    assert result.json()['live_model_response'] is False
    assert result.json()['source_report']['id']==cases[0]['evidence']['id']
    client.post(f'/api/v1/cases/{cid}/stop',json={},headers=HEADERS)
    assert client.post(f'/api/v1/cases/{cid}/estimate',json={},headers=HEADERS).status_code==409


def test_truth_injection_is_not_an_observation_field(client):
    fixture=json.loads(Path('data/sample_runs/synthetic_observations.json').read_text())[0]
    clean={k:v for k,v in fixture.items() if k in {'profile_id','calibration_id','token_class','points'}}
    clean['true_source']='C'
    result=client.post('/api/v1/cases',json=clean,headers=HEADERS)
    assert result.status_code==422


def test_health_and_status_do_not_expose_credentials(client):
    assert client.get('/api/v1/health').json()=={'status':'ok'}
    status=client.get('/api/v1/status').json()
    assert not status['hardware_actuation']
    assert 'api_key' not in status['gemini'] and 'api_key' not in status['photon']
    assert 'test-token' not in json.dumps(status)
    assert status['gemini']['connection_verified'] is False


def test_independent_api_instances_persist_immutable_evidence(tmp_path):
    settings=Settings(data_dir=tmp_path,local_token='test-token')
    with TestClient(create_app(settings)) as c:
        first=c.post('/api/v1/demo/load',json={},headers=HEADERS).json()['cases'][0]
    with TestClient(create_app(settings)) as c:
        old=c.get(f"/api/v1/cases/{first['case']['id']}/evidence").json()
        assert old['id']==first['evidence']['id']
        assert old['relative_support']==first['evidence']['relative_support']
