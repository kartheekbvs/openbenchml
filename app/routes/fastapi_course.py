import logging
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.config import templates
from app.learning.site_content import COURSE_TITLE, COURSE_SUBTITLE, COURSE_OVERVIEW, COURSE_MODULES, COURSE_BY_SLUG

logger = logging.getLogger(__name__)
router = APIRouter()


def get_module(slug: str) -> Optional[dict]:
    return COURSE_BY_SLUG.get(slug)


def get_lesson(module_slug: str, lesson_slug: str) -> Optional[dict]:
    module = get_module(module_slug)
    if not module:
        return None
    return module['lessons_by_slug'].get(lesson_slug)


@router.get('/fastapi-course', response_class=HTMLResponse)
async def fastapi_course_home(request: Request):
    return templates.TemplateResponse('fastapi_course_index.html', {
        'request': request,
        'course_title': COURSE_TITLE,
        'course_subtitle': COURSE_SUBTITLE,
        'course_overview': COURSE_OVERVIEW,
        'modules': COURSE_MODULES,
    })


@router.get('/fastapi-course/syllabus', response_class=HTMLResponse)
async def fastapi_course_syllabus(request: Request):
    total_lessons = sum(len(module['lessons']) for module in COURSE_MODULES)
    return templates.TemplateResponse('fastapi_course_syllabus.html', {
        'request': request,
        'course_title': COURSE_TITLE,
        'course_subtitle': COURSE_SUBTITLE,
        'course_overview': COURSE_OVERVIEW,
        'modules': COURSE_MODULES,
        'total_lessons': total_lessons,
    })


@router.get('/fastapi-course/modules/{module_slug}', response_class=HTMLResponse)
async def fastapi_course_module(request: Request, module_slug: str):
    module = get_module(module_slug)
    if module is None:
        logger.warning('FastAPI course module not found: %s', module_slug)
        return templates.TemplateResponse('base.html', {
            'request': request,
            'error': 'Module not found',
        }, status_code=404)

    return templates.TemplateResponse('fastapi_course_module.html', {
        'request': request,
        'course_title': COURSE_TITLE,
        'course_subtitle': COURSE_SUBTITLE,
        'module': module,
        'modules': COURSE_MODULES,
    })


@router.get('/fastapi-course/modules/{module_slug}/lessons/{lesson_slug}', response_class=HTMLResponse)
async def fastapi_course_lesson(request: Request, module_slug: str, lesson_slug: str):
    module = get_module(module_slug)
    lesson = get_lesson(module_slug, lesson_slug)
    if module is None or lesson is None:
        logger.warning('FastAPI course lesson not found: %s / %s', module_slug, lesson_slug)
        return templates.TemplateResponse('base.html', {
            'request': request,
            'error': 'Lesson not found',
        }, status_code=404)

    lesson_index = next((i for i, item in enumerate(module['lessons']) if item['slug'] == lesson_slug), None)
    next_lesson = None
    if lesson_index is not None and lesson_index + 1 < len(module['lessons']):
        next_lesson = module['lessons'][lesson_index + 1]

    return templates.TemplateResponse('fastapi_course_lesson.html', {
        'request': request,
        'course_title': COURSE_TITLE,
        'course_subtitle': COURSE_SUBTITLE,
        'module': module,
        'lesson': lesson,
        'modules': COURSE_MODULES,
        'next_lesson': next_lesson,
    })
