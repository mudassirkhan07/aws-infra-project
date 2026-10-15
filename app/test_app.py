from app import QUESTIONS, create_app


def client(prefix=""):
    return create_app(prefix).test_client()


def test_health():
    resp = client().get("/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_prefix_routing():
    c = client("/pr-42")
    assert c.get("/pr-42/health").status_code == 200
    assert c.get("/health").status_code == 404


def test_page_urls_use_prefix():
    body = client("/pr-42").get("/pr-42/").get_data(as_text=True)
    assert "/pr-42/api/estimate" in body
    assert "/pr-42/health" in body


def test_estimate_ec2_only():
    resp = client().get("/api/estimate?ec2_type=t3.micro&ec2_count=1&ec2_hours=730")
    assert resp.status_code == 200
    assert resp.get_json()["total"] == 7.59


def test_estimate_defaults_are_zero():
    data = client().get("/api/estimate").get_json()
    assert data["total"] == 0.0
    assert data["runway_months"] is None


def test_estimate_rejects_bad_input():
    c = client()
    assert c.get("/api/estimate?ec2_hours=-5").status_code == 400
    assert c.get("/api/estimate?ec2_type=x1.huge").status_code == 400
    assert c.get("/api/estimate?alb_hours=abc").status_code == 400


def test_quiz_returns_requested_count():
    data = client().get("/api/quiz?n=5").get_json()
    assert len(data["questions"]) == 5


def test_quiz_hides_answers():
    data = client().get("/api/quiz?n=14").get_json()
    assert all("answer" not in q for q in data["questions"])


def test_quiz_answer_correct_and_wrong():
    c = client()
    right = QUESTIONS[0]["answer"]
    wrong = (right + 1) % len(QUESTIONS[0]["options"])
    assert c.get("/api/quiz/answer?id=0&choice=" + str(right)).get_json()["correct"] is True
    assert c.get("/api/quiz/answer?id=0&choice=" + str(wrong)).get_json()["correct"] is False


def test_quiz_answer_invalid():
    c = client()
    assert c.get("/api/quiz/answer?id=999&choice=0").status_code == 404
    assert c.get("/api/quiz/answer?id=0&choice=9").status_code == 400
    assert c.get("/api/quiz/answer?id=x&choice=0").status_code == 400


def test_practices():
    cats = client().get("/api/practices").get_json()["categories"]
    assert len(cats) > 0
    assert all(len(c["items"]) > 0 for c in cats)
