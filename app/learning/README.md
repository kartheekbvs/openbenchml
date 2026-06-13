# OpenBenchML Learning Platform

This module provides a FastAPI-based learning platform for the core concepts used in OpenBenchML.

## Structure

- `router.py` exposes the learning API endpoints.
- `content.py` defines the learning topics, lessons, and mini project descriptions.

## Endpoints

- `GET /learning/topics` — list supported learning topics.
- `GET /learning/topics/{topic_key}` — details for a topic.
- `GET /learning/topics/{topic_key}/lessons/{lesson_slug}` — get a specific lesson.
- `GET /learning/lessons` — list all lessons across topics.
- `GET /learning/search?query=...` — search for lessons by keyword.
