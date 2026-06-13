from typing import Any, List
from fastapi import APIRouter, Query

from app.learning.content import LEARNING_CONTENT

router = APIRouter(prefix="/learning", tags=["learning"])


def _search_lessons(query: str) -> List[dict]:
    query_lower = query.lower()
    results = []
    for topic_key, topic in LEARNING_CONTENT.items():
        for lesson in topic.get("lessons", []):
            haystack = " ".join(
                str(lesson.get(field, "")).lower()
                for field in ["title", "description", "mini_project"]
            )
            if query_lower in haystack:
                results.append({
                    "topic": topic_key,
                    "slug": lesson["slug"],
                    "title": lesson["title"],
                    "description": lesson["description"],
                })
    return results


@router.get("/topics")
async def list_learning_topics():
    return {
        "topics": [
            {
                "key": key,
                "title": value["title"],
                "overview": value["overview"],
            }
            for key, value in LEARNING_CONTENT.items()
        ]
    }


@router.get("/topics/{topic_key}")
async def get_topic(topic_key: str):
    topic = LEARNING_CONTENT.get(topic_key)
    if topic is None:
        return {"error": "Topic not found"}
    return topic


@router.get("/topics/{topic_key}/lessons/{lesson_slug}")
async def get_lesson(topic_key: str, lesson_slug: str):
    topic = LEARNING_CONTENT.get(topic_key)
    if topic is None:
        return {"error": "Topic not found"}
    lesson = next((lesson for lesson in topic["lessons"] if lesson["slug"] == lesson_slug), None)
    if lesson is None:
        return {"error": "Lesson not found"}
    return lesson


@router.get("/lessons")
async def list_all_lessons():
    lessons = []
    for topic_key, topic in LEARNING_CONTENT.items():
        for lesson in topic.get("lessons", []):
            lessons.append({
                "topic": topic_key,
                **lesson,
            })
    return {"lessons": lessons}


@router.get("/search")
async def search_lessons(query: str = Query(..., min_length=2)):
    return {"results": _search_lessons(query)}
