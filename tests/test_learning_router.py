from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_list_learning_topics():
    response = client.get("/learning/topics")
    assert response.status_code == 200
    data = response.json()
    assert "topics" in data
    assert any(topic["key"] == "fastapi" for topic in data["topics"])


def test_get_learning_topic():
    response = client.get("/learning/topics/fastapi")
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "FastAPI Fundamentals"
    assert "lessons" in data


def test_get_learning_lesson():
    response = client.get("/learning/topics/fastapi/lessons/app-structure")
    assert response.status_code == 200
    data = response.json()
    assert data["slug"] == "app-structure"
    assert "title" in data


def test_list_all_lessons():
    response = client.get("/learning/lessons")
    assert response.status_code == 200
    data = response.json()
    assert "lessons" in data
    assert any(lesson["slug"] == "app-structure" for lesson in data["lessons"])


def test_search_lessons():
    response = client.get("/learning/search", params={"query": "Docker"})
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert any("docker" in result["title"].lower() for result in data["results"])
