"""Tests d'intégration des endpoints principaux et des liaisons inter-modules."""

from datetime import date


def _competitor(client, headers, name="TestCorp", share=0.5):
    r = client.post(
        "/competitors",
        headers=headers,
        json={"name": name, "sector": "IA", "market_share": share, "offers": [], "segments": [], "initiatives": []},
    )
    assert r.status_code == 201, r.text
    return r.json()


class TestAuth:
    def test_token_ok(self, client):
        r = client.post("/auth/token", data={"username": "admin@holistic.local", "password": "Password123!"})
        assert r.status_code == 200
        assert "access_token" in r.json() and "refresh_token" in r.json()

    def test_token_wrong_password(self, client):
        r = client.post("/auth/token", data={"username": "admin@holistic.local", "password": "wrong"})
        assert r.status_code == 401

    def test_protected_requires_token(self, client):
        assert client.get("/competitors").status_code == 401


class TestModule1:
    def test_competitor_crud(self, client, strategist):
        comp = _competitor(client, strategist, "CrudCorp", 0.2)
        r = client.get(f"/competitors/{comp['id']}", headers=strategist)
        assert r.status_code == 200 and r.json()["name"] == "CrudCorp"
        r = client.patch(f"/competitors/{comp['id']}", headers=strategist, json={"market_share": 0.3})
        assert r.status_code == 200 and r.json()["market_share"] == 0.3

    def test_signal_ingest_alert_and_adjustment_link(self, client, contributor, admin):
        comp = _competitor(client, contributor, "SignalCorp", 0.9)
        r = client.post(
            "/signals/batch",
            headers=contributor,
            json={"signals": [{"competitor_id": comp["id"], "type": "investissement", "source": "presse", "date": str(date.today())}]},
        )
        assert r.status_code == 201
        signal = r.json()[0]
        assert signal["relevance_score"] >= 70
        alerts = client.get("/signals/alerts", headers=admin).json()
        assert any(a["signal_id"] == signal["id"] for a in alerts)
        adjs = client.get("/strategy-adjustments?trigger_type=signal", headers=admin).json()
        adj = next(a for a in adjs if a["signal_id"] == signal["id"])
        trace = client.get(f"/strategy-adjustments/{adj['id']}/trace", headers=admin).json()
        assert trace["cause"]["signal"]["id"] == signal["id"]

    def test_signal_filters(self, client, contributor, admin):
        comp = _competitor(client, contributor, "FilterCorp", 0.1)
        client.post(
            "/signals",
            headers=contributor,
            json={"competitor_id": comp["id"], "type": "campagne", "source": "blog", "date": "2020-01-01"},
        )
        r = client.get(f"/signals?competitor_id={comp['id']}&type=campagne&from=2019-01-01&to=2021-01-01", headers=admin)
        assert r.status_code == 200 and len(r.json()) == 1
        r = client.get(f"/signals?competitor_id={comp['id']}&min_relevance=99", headers=admin)
        assert len(r.json()) == 0

    def test_case_study_count_by_keyword(self, client, contributor, admin):
        client.post(
            "/case-studies",
            headers=contributor,
            json={"market": "finance", "strategy": "s", "keywords": ["roi", "finance"]},
        )
        client.post(
            "/case-studies",
            headers=contributor,
            json={"market": "sante", "strategy": "s2", "keywords": ["roi"]},
        )
        counts = client.get("/case-studies/count-by-keyword", headers=admin).json()
        assert counts["roi"] == 2


class TestModule5:
    def test_benchmark_gap_triggers_adjustment(self, client, strategist, admin):
        r = client.post(
            "/benchmark-runs",
            headers=strategist,
            json={
                "solution_evaluated": "Sol X",
                "reference_competitors": ["NeuralCorp"],
                "gap_threshold": 10,
                "axes": [
                    {"axis": "fonctionnalites", "our_score": 40, "best_competitor_score": 90},
                    {"axis": "performance", "our_score": 80, "best_competitor_score": 75},
                ],
            },
        )
        assert r.status_code == 201
        run = r.json()
        r = client.post(f"/benchmark-runs/{run['id']}/evaluate", headers=strategist)
        assert r.status_code == 200
        assert r.json()["differentiation_score"] < 0
        adjs = client.get("/strategy-adjustments?trigger_type=benchmark", headers=admin).json()
        assert any("fonctionnalites" in a["trigger_detail"] for a in adjs)
        trace = client.get(f"/strategy-adjustments/{adjs[0]['id']}/trace", headers=admin).json()
        assert trace["cause"]["trigger_type"] == "benchmark"


class TestModule6:
    def test_insight_apply_creates_traced_adjustment(self, client, contributor, strategist, admin):
        board = client.post("/advisory-boards", headers=contributor, json={"theme": "Gouvernance", "scope": "produit"}).json()
        advisor = client.post(
            "/advisors", headers=contributor, json={"profile": "Expert éthique", "notability": 5}
        ).json()
        client.put(f"/advisory-boards/{board['id']}/members/{advisor['id']}", headers=contributor)
        insight = client.post(
            "/advisory-insights",
            headers=contributor,
            json={"advisor_id": advisor["id"], "board_id": board["id"], "recommendation": "Certifier avant publication", "domain": "gouvernance"},
        ).json()
        r = client.post(f"/advisory-insights/{insight['id']}/apply", headers=strategist, json={"decision": "Rendre la certification obligatoire"})
        assert r.status_code == 200
        adj_id = r.json()["adjustment_id"]
        trace = client.get(f"/strategy-adjustments/{adj_id}/trace", headers=admin).json()
        assert trace["cause"]["advisory_insight"]["id"] == insight["id"]


class TestModule4AndEthics:
    def test_publish_blocked_without_ethics_then_allowed(self, client, contributor, strategist, admin):
        sol = client.post(
            "/sector-solutions",
            headers=contributor,
            json={"sector": "finance", "use_cases": ["fraude"], "privacy_impact_level": "high", "privacy_measures": ["pseudonymisation"], "fairness_status": "done"},
        ).json()
        r = client.post(f"/sector-solutions/{sol['id']}/publish", headers=strategist)
        assert r.status_code == 409
        assert r.json()["error"]["code"] == "error.ethics_review_required"
        r = client.post(
            f"/sector-solutions/{sol['id']}/ethics-review",
            headers=strategist,
            json={"status": "validated", "date": str(date.today())},
        )
        assert r.status_code == 200
        r = client.post(f"/sector-solutions/{sol['id']}/publish", headers=strategist)
        assert r.status_code == 200 and r.json()["status"] == "published"
        dash = client.get("/responsible-ai/dashboard", headers=admin).json()
        assert dash["ethics_validated"] >= 1

    def test_roi_calculate(self, client, admin):
        r = client.post(
            "/roi/calculate",
            headers=admin,
            json={"initial_cost": 100000, "annual_cost": 20000, "annual_gain": 60000, "horizon_months": 36},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["roi_percent"] == 12.5
        assert body["payback_months"] == 30.0

    def test_pilot_lifecycle(self, client, contributor, admin):
        st = client.post(
            "/stakeholders", headers=contributor, json={"name": "Pilot Stake", "role": "CIO", "organization": "Org", "decision_level": 5, "budget_authority": True}
        ).json()
        sol = client.post(
            "/sector-solutions",
            headers=contributor,
            json={"sector": "transport", "privacy_impact_level": "low", "privacy_measures": ["m"], "fairness_status": "done"},
        ).json()
        pilot = client.post(
            "/pilots",
            headers=contributor,
            json={
                "stakeholder_id": st["id"],
                "solution_id": sol["id"],
                "scope": "pilote",
                "ethics_review_status": "validated",
                "privacy_impact_level": "low",
                "privacy_measures": ["m"],
                "fairness_status": "done",
            },
        ).json()
        r = client.post(f"/pilots/{pilot['id']}/transition", headers=contributor, json={"to": "completed"})
        assert r.status_code == 409
        r = client.post(f"/pilots/{pilot['id']}/transition", headers=contributor, json={"to": "running"})
        assert r.status_code == 200 and r.json()["status"] == "running"


class TestModule8:
    def test_kpi_gap_closes_loop_to_adjustment(self, client, strategist, admin):
        kpi = client.post("/kpis", headers=strategist, json={"type": "part de marche", "value": 5, "target": 20, "period": "2025-Q2"}).json()
        r = client.post(f"/kpis/{kpi['id']}/evaluate", headers=strategist)
        assert r.status_code == 200
        body = r.json()
        assert body["alert_created"] is True
        adj_id = client.get("/strategy-adjustments?trigger_type=kpi_gap", headers=admin).json()[0]["id"]
        trace = client.get(f"/strategy-adjustments/{adj_id}/trace", headers=admin).json()
        assert trace["cause"]["feedback_item"]["id"] == body["feedback_item_id"]


class TestModule9:
    def test_consume_blocked_without_contingency_then_allowed(self, client, strategist, admin):
        line = client.post("/budget-lines", headers=strategist, json={"pillar": 5, "allocated": 1000, "consumed": 900, "fiscal_year": 2025}).json()
        r = client.post(f"/budget-lines/{line['id']}/consume", headers=strategist, json={"amount": 200})
        assert r.status_code == 409
        assert r.json()["error"]["code"] == "error.budget_exceeded"
        client.post("/contingencies", headers=strategist, json={"risk_scenario": "pic concurrentiel", "provision": 500, "trigger_conditions": ["signal fort"]})
        r = client.post(f"/budget-lines/{line['id']}/consume", headers=strategist, json={"amount": 200, "justification": "campagne urgente"})
        assert r.status_code == 200
        assert r.json()["contingency_drawn"] == 100.0
        reserve = client.get("/contingency/reserve", headers=admin).json()
        assert reserve["remaining"] == 400.0
        report = client.get("/budget/report?fiscal_year=2025", headers=admin).json()
        line_report = next(l for l in report["lines"] if l["budget_line_id"] == line["id"])
        assert line_report["alert"] == "over_budget"
