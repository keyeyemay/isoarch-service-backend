import struct
from fastapi import HTTPException, UploadFile
from core.config import MAX_IMAGE_BYTES, MAX_VIDEO_BYTES, MAX_VIDEO_SECONDS


def mp4_duration(data: bytes) -> float:
    """Read movie duration from ISO BMFF moov/mvhd, including extended boxes."""
    def boxes(start, end):
        while start + 8 <= end:
            size, kind = struct.unpack_from(">I4s", data, start)
            header = 8
            if size == 1:
                if start + 16 > end:
                    raise ValueError("Truncated box")
                size = struct.unpack_from(">Q", data, start + 8)[0]
                header = 16
            elif size == 0:
                size = end - start
            if size < header or start + size > end:
                raise ValueError("Invalid box")
            yield kind, start + header, start + size
            start += size
    for kind, start, end in boxes(0, len(data)):
        if kind == b"moov":
            for child, payload, child_end in boxes(start, end):
                if child == b"mvhd":
                    version = data[payload]
                    if version not in (0, 1):
                        raise ValueError("Unsupported mvhd")
                    offset = payload + (20 if version == 1 else 12)
                    required = 12 if version == 1 else 8
                    if offset + required > child_end:
                        raise ValueError("Truncated mvhd")
                    scale = struct.unpack_from(">I", data, offset)[0]
                    duration = struct.unpack_from(">Q" if version == 1 else ">I", data, offset + 4)[0]
                    if not scale:
                        raise ValueError("Invalid timescale")
                    return duration / scale
    raise ValueError("No MP4 movie duration")


def read_media(upload: UploadFile, kind: str) -> tuple[bytes, str]:
    limit = MAX_IMAGE_BYTES if kind == "image" else MAX_VIDEO_BYTES
    data = upload.file.read(limit + 1)
    if not data:
        raise HTTPException(422, f"Empty {kind} file")
    if len(data) > limit:
        raise HTTPException(413, f"{kind} file is too large")
    mime = upload.content_type or ""
    if kind == "image":
        valid = ((mime == "image/png" and data.startswith(b"\x89PNG\r\n\x1a\n"))
                 or (mime == "image/jpeg" and data.startswith(b"\xff\xd8\xff"))
                 or (mime == "image/webp" and data.startswith(b"RIFF") and data[8:12] == b"WEBP"))
        if not valid:
            raise HTTPException(422, "Use a PNG, JPEG or WebP image")
    else:
        try:
            if mime != "video/mp4" or data[4:8] != b"ftyp":
                raise ValueError("Not MP4")
            duration = mp4_duration(data)
            if not 0 < duration <= MAX_VIDEO_SECONDS:
                raise ValueError("Duration")
        except (ValueError, IndexError, struct.error) as exc:
            raise HTTPException(422, f"Use an MP4 video of up to {MAX_VIDEO_SECONDS} seconds") from exc
    return data, mime
