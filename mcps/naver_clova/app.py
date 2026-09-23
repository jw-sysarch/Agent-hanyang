import os
import json
import uuid
from pathlib import Path
from typing import Any

import httpx
from fastmcp import FastMCP
from dotenv import load_dotenv
from starlette.requests import Request
from starlette.responses import JSONResponse


load_dotenv()

# ── CLOVA Speech API ──────────────────────────────────────────────────────────
_INVOKE_BASE   = os.getenv("CLOVA_SPEECH_INVOKE_URL", "").rstrip("/")
STT_SHORT_URL  = f"{_INVOKE_BASE}/recognizer/words"
STT_LONG_URL   = f"{_INVOKE_BASE}/recognizer/upload"

# ── CLOVA Studio Summary API ──────────────────────────────────────────────────
SUMMARY_URL     = "https://clovastudio.stream.ntruss.com/v1/api-tools/summarization/v2"
MAX_CHUNK_CHARS = 2800


def _get_env(*keys: str) -> str:
    for key in keys:
        value = os.getenv(key)
        if value:
            return value
    raise RuntimeError(f"Missing required environment variable. Tried: {', '.join(keys)}")


def _speech_headers() -> dict[str, str]:
    return {
        "X-CLOVASPEECH-API-KEY": _get_env("CLOVA_SPEECH_API_KEY"),
    }


def _summary_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_get_env('CLOVA_STUDIO_API_KEY')}",
        "X-NCP-CLOVASTUDIO-REQUEST-ID": str(uuid.uuid4()),
        "Content-Type": "application/json",
    }


def _split_chunks(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    chunks, current = [], ""
    for sentence in text.replace("。", ".").split("."):
        sentence = sentence.strip()
        if not sentence:
            continue
        candidate = current + sentence + ". "
        if len(candidate) > max_chars and current:
            chunks.append(current.strip())
            current = sentence + ". "
        else:
            current = candidate
    if current.strip():
        chunks.append(current.strip())
    return chunks or [text[:max_chars]]


async def _call_summary_api(text: str) -> str:
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            SUMMARY_URL,
            headers=_summary_headers(),
            json={"texts": [text]},
        )
        response.raise_for_status()
        data = response.json()
    status = data.get("status", {})
    if status.get("code") != "20000":
        raise RuntimeError(f"CLOVA Studio 오류: {status.get('message', '알 수 없는 오류')}")
    return data.get("result", {}).get("text", "")


# ── MCP Server ────────────────────────────────────────────────────────────────
mcp = FastMCP("clova-lecture")


@mcp.custom_route("/health", methods=["GET"], include_in_schema=False)
async def health_check(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "server": "clova-lecture"})


# ── Tool 1: 단문 STT (60초 이하) ──────────────────────────────────────────────
@mcp.tool
async def transcribe_short(
    file_path: str,
    language: str = "ko-KR",
) -> dict[str, Any]:
    """
    짧은 오디오 클립(60초 이하)을 텍스트로 변환합니다. (동기)

    Args:
        file_path: 로컬 오디오 파일 경로 (.wav .mp3 .flac .aac .m4a 등)
        language: 언어 코드. 한국어='ko-KR', 영어='en-US' (기본값: ko-KR)
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")

    params = {"language": language}

    async with httpx.AsyncClient(timeout=60.0) as client:
        with open(path, "rb") as f:
            files = {
                "media": (path.name, f, "application/octet-stream"),
                "params": (None, json.dumps(params), "application/json"),
            }
            response = await client.post(STT_SHORT_URL, headers=_speech_headers(), files=files)
        response.raise_for_status()
        result = response.json()

    segments = result.get("segments", [])
    full_text = " ".join(seg.get("text", "") for seg in segments)

    return {
        "file": path.name,
        "language": language,
        "text": full_text,
    }


# ── Tool 2: 장문 STT (강의 전체, 동기) ────────────────────────────────────────
@mcp.tool
async def transcribe_lecture(
    file_path: str,
    language: str = "ko-KR",
    enable_diarization: bool = True,
    speaker_count: int = 1,
) -> dict[str, Any]:
    """
    강의 오디오 파일을 텍스트로 변환합니다. (동기, 결과 바로 반환)

    Args:
        file_path: 로컬 오디오 파일 경로
        language: 언어 코드. 한국어='ko-KR', 영어='en-US' (기본값: ko-KR)
        enable_diarization: 화자 분리 여부 (기본값: True)
        speaker_count: 예상 화자 수 (기본값: 1)
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")

    params = {
        "language": language,
        "completion": "sync",
        "diarization": {
            "enable": enable_diarization,
            "speakerCountMin": speaker_count,
            "speakerCountMax": speaker_count + 1,
        },
        "sed": {"enable": False},
        "fullText": True,
    }

    async with httpx.AsyncClient(timeout=600.0) as client:
        with open(path, "rb") as f:
            files = {
                "media": (path.name, f, "application/octet-stream"),
                "params": (None, json.dumps(params), "application/json"),
            }
            response = await client.post(STT_LONG_URL, headers=_speech_headers(), files=files)
        response.raise_for_status()
        result = response.json()

    segments = result.get("segments", [])
    full_text = result.get("text", "") or " ".join(seg.get("text", "") for seg in segments)

    return {
        "file": path.name,
        "language": language,
        "full_text": full_text,
        "segments": [
            {
                "speaker": seg.get("diarization", {}).get("label", "S1"),
                "start_ms": seg.get("start"),
                "end_ms": seg.get("end"),
                "text": seg.get("text", ""),
            }
            for seg in segments
        ],
    }


# ── Tool 3: 강의 전체 요약 ─────────────────────────────────────────────────────
@mcp.tool
async def summarize_lecture(
    text: str,
) -> dict[str, Any]:
    """
    STT 전사 텍스트를 CLOVA Studio로 요약합니다.
    텍스트가 길면 자동으로 청크 분할 후 계층 요약합니다.

    Args:
        text: 요약할 강의 전사 텍스트 (길이 제한 없음)
    """
    if not text.strip():
        raise ValueError("요약할 텍스트가 비어 있습니다.")

    chunks = _split_chunks(text)
    chunk_summaries = [await _call_summary_api(c) for c in chunks]

    if len(chunk_summaries) == 1:
        final_summary = chunk_summaries[0]
    else:
        merged = "\n\n".join(chunk_summaries)
        final_summary = (
            await _call_summary_api(merged)
            if len(merged) <= MAX_CHUNK_CHARS
            else await _call_summary_api("\n\n".join(
                [await _call_summary_api(c) for c in _split_chunks(merged)]
            ))
        )

    return {
        "summary": final_summary,
        "chunk_count": len(chunks),
        "original_chars": len(text),
        "summary_chars": len(final_summary),
        "compression_ratio": round(len(final_summary) / max(len(text), 1) * 100, 1),
    }


# ── Tool 4: 화자별 요약 ────────────────────────────────────────────────────────
@mcp.tool
async def summarize_by_speaker(
    segments: list[dict],
) -> dict[str, Any]:
    """
    화자 분리된 세그먼트를 화자별로 요약합니다.
    transcribe_lecture의 segments를 그대로 넣으면 됩니다.

    Args:
        segments: [{"speaker": "S1", "text": "...", "start_ms": 0, "end_ms": 5000}, ...]
    """
    if not segments:
        raise ValueError("세그먼트가 비어 있습니다.")

    speaker_texts: dict[str, list[str]] = {}
    for seg in segments:
        speaker = seg.get("speaker", "S1")
        text = seg.get("text", "").strip()
        if text:
            speaker_texts.setdefault(speaker, []).append(text)

    speaker_summaries: dict[str, str] = {}
    for speaker, texts in speaker_texts.items():
        combined = " ".join(texts)
        chunks = _split_chunks(combined)
        summaries = [await _call_summary_api(c) for c in chunks]
        speaker_summaries[speaker] = (
            summaries[0] if len(summaries) == 1
            else await _call_summary_api("\n\n".join(summaries))
        )

    all_text = " ".join(t for texts in speaker_texts.values() for t in texts)
    chunks = _split_chunks(all_text)
    chunk_summaries = [await _call_summary_api(c) for c in chunks]
    overall = (
        chunk_summaries[0] if len(chunk_summaries) == 1
        else await _call_summary_api("\n\n".join(chunk_summaries))
    )

    return {
        "speaker_summaries": speaker_summaries,
        "overall_summary": overall,
        "speaker_count": len(speaker_summaries),
    }


if __name__ == "__main__":
    transport = os.getenv("FASTMCP_TRANSPORT", "streamable-http")
    host = os.getenv("FASTMCP_HOST", "0.0.0.0")
    port = int(os.getenv("FASTMCP_PORT", os.getenv("PORT", "8005")))
    mcp.run(transport=transport, host=host, port=port)
