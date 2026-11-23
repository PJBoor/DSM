"""Tests du bilinguisme (Accept-Language) et du contrôle d'accès par rôle."""


class TestI18n:
    def test_error_message_in_french_by_default(self, client, admin):
        r = client.get("/competitors/99999", headers=admin)
        assert r.status_code == 404
        assert r.json()["error"]["message"] == "Concurrent introuvable"

    def test_error_message_in_english_with_header(self, client, admin):
        r = client.get("/competitors/99999", headers={**admin, "Accept-Language": "en-US,en;q=0.9"})
        assert r.status_code == 404
        assert r.json()["error"]["message"] == "Competitor not found"

    def test_unknown_language_falls_back_to_french(self, client, admin):
        r = client.get("/competitors/99999", headers={**admin, "Accept-Language": "de-DE"})
        assert r.json()["error"]["message"] == "Concurrent introuvable"

    def test_health_localized(self, client):
        assert client.get("/health").json()["status"] == "OK"
        assert client.get("/health", headers={"Accept-Language": "en"}).json()["status"] == "OK"


class TestRbac:
    def test_reader_cannot_write(self, client, reader):
        r = client.post(
            "/competitors",
            headers=reader,
            json={"name": "Forbidden", "sector": "IA", "market_share": 0.1},
        )
        assert r.status_code == 403

    def test_contributor_can_ingest_signals(self, client, contributor, admin):
        comp = client.post(
            "/competitors",
            headers=contributor,
            json={"name": "RbacCorp", "sector": "IA", "market_share": 0.2},
        ).json()
        r = client.post(
            "/signals",
            headers=contributor,
            json={"competitor_id": comp["id"], "type": "campagne", "source": "blog", "date": "2025-06-01"},
        )
        assert r.status_code == 201

    def test_reader_cannot_consume_budget(self, client, reader, strategist):
        line = client.post("/budget-lines", headers=strategist, json={"pillar": 7, "allocated": 100, "consumed": 0, "fiscal_year": 2025}).json()
        r = client.post(f"/budget-lines/{line['id']}/consume", headers=reader, json={"amount": 10})
        assert r.status_code == 403

    def test_reader_sees_masked_pii_on_stakeholders(self, client, contributor, reader):
        client.post(
            "/stakeholders",
            headers=contributor,
            json={"name": "Jean Dupont", "role": "CIO", "organization": "Banque Test", "decision_level": 5},
        )
        masked = client.get("/stakeholders", headers=reader).json()
        names = {s["name"] for s in masked}
        assert "Jean Dupont" not in names
        assert "***" in names
        unmasked = client.get("/stakeholders", headers=contributor).json()
        assert "Jean Dupont" in {s["name"] for s in unmasked}

    def test_unauthenticated_is_401(self, client):
        assert client.get("/kpis").status_code == 401
