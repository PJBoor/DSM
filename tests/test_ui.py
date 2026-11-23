"""Test de l'IHM statique servie sur /ui."""


def test_ui_index_served(client):
    r = client.get("/ui/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Holistic Approach" in r.text
    assert "/ui/app.js" in r.text


def test_ui_static_assets(client):
    assert client.get("/ui/app.js").status_code == 200
    assert client.get("/ui/styles.css").status_code == 200


def test_root_mentions_ui(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["ui"] == "/ui/"
