from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_fastapi_course_home():
    response = client.get('/fastapi-course')
    assert response.status_code == 200
    assert 'FastAPI Mastery' in response.text


def test_fastapi_course_module():
    response = client.get('/fastapi-course/modules/fastapi-introduction')
    assert response.status_code == 200
    assert 'FastAPI Introduction' in response.text


def test_fastapi_course_lesson():
    response = client.get('/fastapi-course/modules/fastapi-introduction/lessons/what-is-fastapi')
    assert response.status_code == 200
    assert 'What is FastAPI?' in response.text


def test_fastapi_course_syllabus():
    response = client.get('/fastapi-course/syllabus')
    assert response.status_code == 200
    assert 'Syllabus' in response.text
    assert 'FastAPI Introduction' in response.text
