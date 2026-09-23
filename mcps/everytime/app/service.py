from __future__ import annotations

from app.config import Settings
from app.models import BoardSummary, PageSummary
from app.scraper import EverytimeScraper


class EverytimeService:
    def __init__(self, settings: Settings):
        self.scraper = EverytimeScraper(settings)

    def get_home_summary(self, include_cookies: bool = False) -> dict:
        result = self.scraper.fetch_home().to_dict()
        if not include_cookies:
            result.pop("cookies", None)
        return result

    def list_boards(self) -> dict:
        boards: list[BoardSummary] = self.scraper.fetch_boards()
        return {"boards": [board.to_dict() for board in boards]}

    def get_board_posts(self, board_id: str, limit: int = 20) -> dict:
        return self.scraper.fetch_board(board_id=board_id, limit=limit)

    def debug_board(self, board_id: str) -> dict:
        return self.scraper.debug_board(board_id=board_id)

    def get_my_lectures(self) -> dict:
        return self.scraper.fetch_my_lectures()

    def get_lecture_points(self) -> dict:
        return self.scraper.fetch_lecture_points()

    def get_recent_lecture_reviews(self, limit: int = 20, offset: int = 0) -> dict:
        return self.scraper.fetch_recent_lecture_reviews(limit=limit, offset=offset)

    def search_lectures(
        self,
        keyword: str,
        year: str | None = None,
        semester: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict:
        if not keyword.strip():
            raise ValueError("keyword must not be empty")
        return self.scraper.search_lectures(
            keyword=keyword.strip(),
            year=year,
            semester=semester,
            limit=limit,
            offset=offset,
        )

    def get_lecture_reviews(
        self, lecture_id: str, limit: int = 20, offset: int = 0, use_cookie: bool = False
    ) -> dict:
        return self.scraper.fetch_lecture_reviews(
            lecture_id=lecture_id,
            limit=limit,
            offset=offset,
            use_cookie=use_cookie,
        )

    def get_public_lecture_page(self, lecture_id: str) -> dict:
        return self.scraper.fetch_public_lecture_page(lecture_id=lecture_id)

    def list_timetable_semesters(self) -> dict:
        return self.scraper.fetch_timetable_semesters()

    def list_timetable_tables(self, year: str, semester: str) -> dict:
        return self.scraper.fetch_timetable_tables(year=year, semester=semester)

    def get_timetable(self, table_id: str) -> dict:
        return self.scraper.fetch_timetable(table_id=table_id)

    def get_current_timetable(self) -> dict:
        return self.scraper.fetch_current_timetable()
