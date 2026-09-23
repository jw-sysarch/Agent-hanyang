from fastapi import FastAPI, HTTPException, Query

from app.dependencies import get_service
from app.errors import EverytimeRequestError


def create_api_app() -> FastAPI:
    app = FastAPI(title="Everytime MCP Bootstrap API", version="0.2.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/home")
    def fetch_home(include_cookies: bool = Query(default=False)) -> dict:
        try:
            return get_service().get_home_summary(include_cookies=include_cookies)
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except EverytimeRequestError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Unexpected error: {exc}") from exc

    @app.get("/api/boards")
    def fetch_boards() -> dict:
        try:
            return get_service().list_boards()
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except EverytimeRequestError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Unexpected error: {exc}") from exc

    @app.get("/api/boards/{board_id}")
    def fetch_board(board_id: str, limit: int = Query(default=20, ge=1, le=100)) -> dict:
        try:
            return get_service().get_board_posts(board_id=board_id, limit=limit)
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except EverytimeRequestError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Unexpected error: {exc}") from exc

    @app.get("/api/debug/boards/{board_id}")
    def debug_board(board_id: str) -> dict:
        try:
            return get_service().debug_board(board_id=board_id)
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except EverytimeRequestError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Unexpected error: {exc}") from exc

    @app.get("/api/lectures/mine")
    def fetch_my_lectures() -> dict:
        try:
            return get_service().get_my_lectures()
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except EverytimeRequestError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Unexpected error: {exc}") from exc

    @app.get("/api/lectures/points")
    def fetch_lecture_points() -> dict:
        try:
            return get_service().get_lecture_points()
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except EverytimeRequestError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Unexpected error: {exc}") from exc

    @app.get("/api/lectures/search")
    def search_lectures(
        keyword: str,
        year: str | None = None,
        semester: str | None = None,
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
    ) -> dict:
        try:
            return get_service().search_lectures(
                keyword=keyword,
                year=year,
                semester=semester,
                limit=limit,
                offset=offset,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except EverytimeRequestError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Unexpected error: {exc}") from exc

    @app.get("/api/lectures/reviews/recent")
    def fetch_recent_lecture_reviews(
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
    ) -> dict:
        try:
            return get_service().get_recent_lecture_reviews(limit=limit, offset=offset)
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except EverytimeRequestError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Unexpected error: {exc}") from exc

    @app.get("/api/lectures/{lecture_id}")
    def fetch_public_lecture_page(lecture_id: str) -> dict:
        try:
            return get_service().get_public_lecture_page(lecture_id=lecture_id)
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except EverytimeRequestError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Unexpected error: {exc}") from exc

    @app.get("/api/lectures/{lecture_id}/reviews")
    def fetch_lecture_reviews(
        lecture_id: str,
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        use_cookie: bool = Query(default=False),
    ) -> dict:
        try:
            return get_service().get_lecture_reviews(
                lecture_id=lecture_id,
                limit=limit,
                offset=offset,
                use_cookie=use_cookie,
            )
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except EverytimeRequestError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Unexpected error: {exc}") from exc

    @app.get("/api/timetable/semesters")
    def fetch_timetable_semesters() -> dict:
        try:
            return get_service().list_timetable_semesters()
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except EverytimeRequestError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Unexpected error: {exc}") from exc

    @app.get("/api/timetable/current")
    def fetch_current_timetable() -> dict:
        try:
            return get_service().get_current_timetable()
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except EverytimeRequestError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Unexpected error: {exc}") from exc

    @app.get("/api/timetable/tables")
    def fetch_timetable_tables(year: str, semester: str) -> dict:
        try:
            return get_service().list_timetable_tables(year=year, semester=semester)
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except EverytimeRequestError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Unexpected error: {exc}") from exc

    @app.get("/api/timetable/tables/{table_id}")
    def fetch_timetable(table_id: str) -> dict:
        try:
            return get_service().get_timetable(table_id=table_id)
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except EverytimeRequestError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Unexpected error: {exc}") from exc

    return app
