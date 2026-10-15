from app import create_app


def test_health():
    client = create_app("").test_client()
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_co2_calculation():
    client = create_app("").test_client()
    resp = client.get("/api/co2?km=100&l_per_100km=7")
    assert resp.status_code == 200
    assert resp.get_json()["co2_kg"] == 16.17


def test_bad_input():
    client = create_app("").test_client()
    assert client.get("/api/co2?km=abc").status_code == 400


def test_prefix_routing():
    client = create_app("/pr-42").test_client()
    assert client.get("/pr-42/health").status_code == 200
    assert client.get("/health").status_code == 404


def test_links_use_prefix():
    client = create_app("/pr-42").test_client()
    body = client.get("/pr-42/").get_data(as_text=True)
    assert "/pr-42/health" in body
