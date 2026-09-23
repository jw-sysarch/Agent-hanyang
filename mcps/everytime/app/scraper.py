from __future__ import annotations

import re
from datetime import date
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
import requests

from app.errors import EverytimeRequestError
from app.models import ArticleSummary, BoardSummary, PageSummary
from app.config import Settings


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)


class EverytimeScraper:
    def __init__(self, settings: Settings):
        self.settings = settings

    def fetch_home(self) -> PageSummary:
        response = self._request(self.settings.home_url)
        return self._summarize_page(
            html=response.text,
            current_url=response.url,
            cookies=self._parse_cookie_header(self.settings.cookie),
        )

    def fetch_boards(self) -> list[BoardSummary]:
        response = self._request(self.settings.home_url)
        soup = BeautifulSoup(response.text, "html.parser")
        boards: list[BoardSummary] = []
        seen_ids: set[str] = set()

        for tag in soup.select("a[href]"):
            href = urljoin(response.url, tag.get("href", "").strip())
            board_id = self._extract_board_id(href)
            if not board_id or board_id in seen_ids:
                continue

            name = tag.get_text(" ", strip=True)
            if not name or name in {"게시판", "더 보기"}:
                continue

            seen_ids.add(board_id)
            boards.append(BoardSummary(id=board_id, name=name[:120], href=href))

        return boards

    def fetch_board(self, board_id: str, limit: int = 20) -> dict[str, Any]:
        data = self._request_board_articles(board_id=board_id, limit=limit, start_num=0)
        xml = BeautifulSoup(data, "xml")
        title = self._extract_board_title_from_xml(xml)
        articles: list[ArticleSummary] = []
        for article_node in xml.find_all("article"):
            article_id = (article_node.get("id") or "").strip()
            if not article_id:
                continue
            href = urljoin(self.settings.home_url, f"{board_id}/v/{article_id}")
            title_text = (article_node.get("title") or "").strip()
            preview = (article_node.get("text") or "").strip()
            author = (article_node.get("user_nickname") or "").strip()
            created_at = (article_node.get("created_at") or "").strip()
            comment_count = (article_node.get("comment") or "").strip()
            like_count = (article_node.get("posvote") or "").strip()
            articles.append(
                ArticleSummary(
                    title=title_text[:200],
                    href=href,
                    author=author[:80],
                    created_at=created_at[:80],
                    preview=preview[:400],
                    comment_count=comment_count,
                    like_count=like_count,
                )
            )
            if len(articles) >= limit:
                break

        return {
            "board": {
                "id": board_id,
                "title": title,
                "url": urljoin(self.settings.home_url, board_id),
            },
            "articles": [article.to_dict() for article in articles],
        }

    def debug_board(self, board_id: str) -> dict[str, Any]:
        board_url = urljoin(self.settings.home_url, board_id)
        response = self._request(board_url)
        soup = BeautifulSoup(response.text, "html.parser")
        api_preview = self._request_board_articles(board_id=board_id, limit=5, start_num=0)

        href_matches = []
        for tag in soup.select("a[href]"):
            href = urljoin(response.url, tag.get("href", "").strip())
            text = tag.get_text(" ", strip=True)
            if board_id in href:
                href_matches.append({"href": href, "text": text[:120]})
            if len(href_matches) >= 50:
                break

        regex_matches = []
        pattern = re.compile(rf"/{re.escape(board_id)}/[^\"' <]+")
        for match in pattern.finditer(response.text):
            start = max(0, match.start() - 120)
            end = min(len(response.text), match.end() + 240)
            regex_matches.append(response.text[start:end])
            if len(regex_matches) >= 20:
                break

        return {
            "url": response.url,
            "title": soup.title.get_text(strip=True) if soup.title else "",
            "anchor_matches": href_matches,
            "regex_matches": regex_matches,
            "html_preview": response.text[:5000],
            "api_preview": api_preview[:5000],
        }

    def fetch_my_lectures(self) -> dict[str, Any]:
        return self._request_v2_json(
            "/v2/find/lecture/list/mine",
            referer=urljoin(self.settings.home_url, "lecture"),
        )

    def fetch_lecture_points(self) -> dict[str, Any]:
        return self._request_v2_json(
            "/v2/find/lecture/point",
            referer=urljoin(self.settings.home_url, "lecture"),
        )

    def fetch_recent_lecture_reviews(self, limit: int = 20, offset: int = 0) -> dict[str, Any]:
        return self._request_v2_json(
            "/v2/find/lecture/article/list/recent",
            data={"limit": str(limit), "offset": str(offset)},
            referer=urljoin(self.settings.home_url, "lecture"),
        )

    def search_lectures(
        self,
        keyword: str,
        year: str | None = None,
        semester: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        selected_year, selected_semester = self._resolve_semester(year, semester)
        data = self._request_xml_api(
            "/find/timetable/subject/list",
            data={
                "year": selected_year,
                "semester": selected_semester,
                "keyword": keyword,
                "limitNum": str(limit),
                "startNum": str(offset),
            },
            referer=urljoin(self.settings.home_url, "timetable"),
        )
        xml = BeautifulSoup(data, "xml")
        return {
            "keyword": keyword,
            "year": selected_year,
            "semester": selected_semester,
            "subjects": [self._parse_subject_search_result(node) for node in xml.find_all("subject")],
        }

    def fetch_lecture_reviews(
        self, lecture_id: str, limit: int = 20, offset: int = 0, use_cookie: bool = False
    ) -> dict[str, Any]:
        response = self._request_v2_json(
            "/v2/find/lecture/article/list",
            data={"lectureId": lecture_id, "limit": str(limit), "offset": str(offset)},
            referer=urljoin(self.settings.home_url, f"lecture/view/{lecture_id}"),
            include_cookie=use_cookie,
        )
        if response.get("status") == "success":
            return response

        page = self.fetch_public_lecture_page(lecture_id)
        return {
            "status": response.get("status", "error"),
            "lecture": page.get("lecture"),
            "result": response.get("result"),
            "error": response.get("error"),
            "message": (
                "Lecture review API did not return success. "
                "The public lecture page metadata is included for identification."
            ),
            "endpoint": response.get("endpoint"),
        }

    def fetch_public_lecture_page(self, lecture_id: str) -> dict[str, Any]:
        url = urljoin(self.settings.home_url, f"lecture/view/{lecture_id}")
        response = self._request_public(url)
        soup = BeautifulSoup(response.text, "html.parser")
        title = soup.title.get_text(strip=True) if soup.title else ""
        name = title.removesuffix(" 강의실 - 에브리타임").strip()
        return {
            "lecture": {
                "id": lecture_id,
                "name": name,
                "url": response.url,
                "title": title,
            }
        }

    def fetch_timetable_semesters(self) -> dict[str, Any]:
        data = self._request_xml_api(
            "/find/timetable/subject/semester/list",
            referer=urljoin(self.settings.home_url, "timetable"),
        )
        xml = BeautifulSoup(data, "xml")
        return {
            "semesters": [
                {
                    "year": node.get("year", ""),
                    "semester": node.get("semester", ""),
                    "start_date": node.get("start_date", ""),
                    "end_date": node.get("end_date", ""),
                    "is_formal": node.get("is_formal", ""),
                    "is_supported": node.get("is_supported", ""),
                    "has_syllabus": node.get("has_syllabus", ""),
                    "has_subject_database": node.get("has_subject_database", ""),
                    "updated_at": node.get("updated_at", ""),
                }
                for node in xml.find_all("semester")
            ]
        }

    def fetch_timetable_tables(self, year: str, semester: str) -> dict[str, Any]:
        data = self._request_xml_api(
            "/find/timetable/table/list/semester",
            data={"year": year, "semester": semester},
            referer=urljoin(self.settings.home_url, "timetable"),
        )
        xml = BeautifulSoup(data, "xml")
        return {
            "year": year,
            "semester": semester,
            "tables": [
                {
                    "id": node.get("id", ""),
                    "name": node.get("name", ""),
                    "private": node.get("priv", ""),
                    "is_primary": node.get("is_primary", ""),
                    "created_at": node.get("created_at", ""),
                    "updated_at": node.get("updated_at", ""),
                }
                for node in xml.find_all("table")
            ],
        }

    def fetch_timetable(self, table_id: str) -> dict[str, Any]:
        data = self._request_xml_api(
            "/find/timetable/table",
            data={"id": table_id},
            referer=urljoin(self.settings.home_url, "timetable"),
        )
        xml = BeautifulSoup(data, "xml")
        table = xml.find("table")
        if not table:
            return {"table": None, "subjects": []}

        return {
            "table": {
                "id": table.get("id", ""),
                "name": table.get("name", ""),
                "year": table.get("year", ""),
                "semester": table.get("semester", ""),
                "private": table.get("priv", ""),
                "primary": table.get("primary", ""),
                "created_at": table.get("created_at", ""),
                "updated_at": table.get("updated_at", ""),
            },
            "subjects": [self._parse_timetable_subject(node) for node in table.find_all("subject")],
        }

    def fetch_current_timetable(self) -> dict[str, Any]:
        semesters = self.fetch_timetable_semesters()["semesters"]
        today = date.today().isoformat()
        current = next(
            (
                semester
                for semester in semesters
                if semester["start_date"] <= today <= semester["end_date"]
                and semester["is_formal"] == "1"
            ),
            None,
        )
        if current is None:
            current = next(
                (semester for semester in semesters if semester["is_formal"] == "1"),
                None,
            )
        if current is None:
            return {"table": None, "subjects": [], "message": "No formal semester found."}

        tables = self.fetch_timetable_tables(current["year"], current["semester"])["tables"]
        primary = next((table for table in tables if table["is_primary"] == "1"), None)
        selected = primary or (tables[0] if tables else None)
        if selected is None:
            return {"semester": current, "table": None, "subjects": []}

        result = self.fetch_timetable(selected["id"])
        result["semester"] = current
        return result

    def _request_board_articles(self, board_id: str, limit: int, start_num: int) -> str:
        return self._request_xml_api(
            "/find/board/article/list",
            data={
                "id": board_id,
                "limit_num": str(limit),
                "start_num": str(start_num),
                "moiminfo": "true",
            },
            referer=urljoin(self.settings.home_url, board_id),
        )

    def _request_xml_api(
        self, path: str, data: dict[str, str] | None = None, referer: str | None = None
    ) -> str:
        url = self.settings.api_base_url.rstrip("/") + path
        response = requests.post(
            url,
            headers=self._headers(referer=referer),
            data=data or {},
            timeout=30,
        )
        response.raise_for_status()
        return response.text

    def _request_v2_json(
        self,
        path: str,
        data: dict[str, Any] | None = None,
        referer: str | None = None,
        include_cookie: bool = True,
    ) -> dict[str, Any]:
        url = self.settings.api_base_url.rstrip("/") + path
        try:
            response = requests.post(
                url,
                headers=self._headers(referer=referer, include_cookie=include_cookie),
                json=data or {},
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise EverytimeRequestError(str(exc)) from exc
        except ValueError as exc:
            raise EverytimeRequestError(f"Expected JSON response from {path}") from exc

        if isinstance(payload, dict):
            payload.setdefault("endpoint", path)
            return payload
        return {"status": "error", "endpoint": path, "result": payload}

    def _headers(self, referer: str | None = None, include_cookie: bool = True) -> dict[str, str]:
        headers = {
            "User-Agent": USER_AGENT,
            "Referer": referer or self.settings.home_url,
            "Origin": "https://everytime.kr",
        }
        if include_cookie:
            headers["Cookie"] = self.settings.cookie
        return headers

    def _parse_timetable_subject(self, subject_node) -> dict[str, Any]:
        def child_value(name: str) -> str:
            node = subject_node.find(name)
            return node.get("value", "") if node else ""

        time_node = subject_node.find("time")
        return {
            "id": subject_node.get("id", ""),
            "internal": child_value("internal"),
            "name": child_value("name"),
            "professor": child_value("professor"),
            "time": child_value("time"),
            "place": child_value("place"),
            "credit": child_value("credit"),
            "closed": child_value("closed"),
            "meetings": [
                {
                    "day": node.get("day", ""),
                    "starttime": node.get("starttime", ""),
                    "endtime": node.get("endtime", ""),
                    "place": node.get("place", ""),
                }
                for node in (time_node.find_all("data") if time_node else [])
            ],
        }

    def _parse_subject_search_result(self, subject_node) -> dict[str, Any]:
        result = self._parse_timetable_subject(subject_node)
        result.update(
            {
                "lecture_id": subject_node.get("lectureId", "")
                or subject_node.get("lecture_id", ""),
                "rate": subject_node.get("rate", "") or subject_node.get("rating", ""),
                "grade": subject_node.get("grade", ""),
                "category": subject_node.get("category", ""),
                "target": subject_node.get("target", ""),
                "notice": subject_node.get("notice", ""),
            }
        )
        return result

    def _resolve_semester(self, year: str | None, semester: str | None) -> tuple[str, str]:
        if year and semester:
            return year, semester

        semesters = self.fetch_timetable_semesters()["semesters"]
        today = date.today().isoformat()
        selected = next(
            (
                item
                for item in semesters
                if item["start_date"] <= today <= item["end_date"]
                and item["is_formal"] == "1"
                and item["is_supported"] == "1"
            ),
            None,
        )
        if selected is None:
            selected = next(
                (
                    item
                    for item in semesters
                    if item["is_formal"] == "1" and item["is_supported"] == "1"
                ),
                None,
            )
        if selected is None:
            raise EverytimeRequestError("No supported semester found for lecture search.")
        return selected["year"], selected["semester"]

    def _extract_board_title_from_xml(self, xml: BeautifulSoup) -> str:
        moim = xml.find("moim")
        if moim and moim.get("name"):
            return moim.get("name", "").strip()
        return ""

    def _request(self, url: str) -> requests.Response:
        response = requests.get(
            url,
            headers=self._headers(),
            timeout=30,
        )
        response.raise_for_status()
        if "로그인" in response.text and "회원가입" in response.text:
            preview = BeautifulSoup(response.text, "html.parser").get_text("\n", strip=True)[:500]
            raise EverytimeRequestError(
                "Cookie may be invalid or expired. "
                f"cookie_length={len(self.settings.cookie)!r}. "
                f"Page preview: {preview!r}"
            )
        return response

    def _request_public(self, url: str) -> requests.Response:
        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=30,
        )
        response.raise_for_status()
        return response

    def _parse_cookie_header(self, cookie_header: str) -> dict[str, str]:
        cookies: dict[str, str] = {}
        for part in cookie_header.split(";"):
            item = part.strip()
            if not item or "=" not in item:
                continue
            name, value = item.split("=", 1)
            cookies[name.strip()] = value.strip()
        return cookies

    def _extract_board_id(self, href: str) -> str | None:
        parsed = urlparse(href)
        if parsed.netloc and "everytime.kr" not in parsed.netloc:
            return None

        path = parsed.path.strip("/")
        if not path or not path.isdigit():
            return None
        return path

    def _summarize_page(
        self, *, html: str, current_url: str, cookies: dict[str, str]
    ) -> PageSummary:
        soup = BeautifulSoup(html, "html.parser")
        headings = [
            heading.get_text(" ", strip=True)
            for heading in soup.select("h1, h2, h3")
            if heading.get_text(" ", strip=True)
        ]
        links = []
        for tag in soup.select("a[href]"):
            text = tag.get_text(" ", strip=True)
            href = tag.get("href", "").strip()
            if not href:
                continue
            links.append(
                {
                    "text": text[:120],
                    "href": urljoin(current_url, href),
                }
            )
            if len(links) >= 20:
                break

        text_preview = soup.get_text("\n", strip=True)[:2000]

        return PageSummary(
            url=current_url,
            title=(soup.title.get_text(strip=True) if soup.title else ""),
            headings=headings[:20],
            links=links,
            text_preview=text_preview,
            cookies=cookies,
        )
