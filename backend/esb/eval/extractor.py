"""Transcript extraction for various video platforms.

Ported from esby-portal's app/platforms/extractor.py.
"""
import asyncio
import os
import re
from pathlib import Path
from typing import Optional

from esb.core.config import settings
from esb.eval.detector import detect_platform


def _tmp_path() -> Path:
    p = Path(settings.eval_tmp_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p


async def extract_transcript(video_url: str, job_id: str) -> str:
    """Return the full transcript text for a video URL.

    Fast-path order:
      1. YouTube transcript API (no download, local — may be IP-blocked on server)
      1b. YouTube transcript API via SSH on the primary whisper remote (residential IP, bypasses block)
      2. Granicus/Swagit caption file (no download)
      3. Groq Whisper API (cloud, real-time speed, needs GROQ_API_KEY) — non-YouTube only
      4a. YouTube: primary remote SSH with remote yt-dlp download (bypasses IP block)
      4b. Non-YouTube: primary remote via SSH
      5. Secondary remote via SSH (tertiary backup)
      6. Local faster-whisper via yt-dlp (slowest, always available) — non-YouTube only
    """
    platform = detect_platform(video_url)

    if platform == "youtube":
        transcript = await _try_youtube_api(video_url)
        if transcript:
            return transcript

    if platform == "youtube" and settings.whisper_ssh_key_path:
        video_id = _extract_youtube_id(video_url)
        if video_id:
            transcript = await _try_ssh_youtube_api(video_id)
            if transcript:
                return transcript

    transcript = await _try_platform_captions(video_url, platform)
    if transcript:
        return transcript

    # Groq Whisper API (real-time speed, free tier) — skipped for YouTube
    # because yt-dlp download from a datacenter IP is blocked by YouTube bot detection.
    if platform != "youtube":
        transcript = await _try_groq_whisper(video_url, job_id, platform)
        if transcript:
            return transcript

    if settings.whisper_ssh_key_path and settings.whisper_remote1_host:
        if platform == "youtube":
            transcript = await _try_ssh_yt_whisper(
                video_url, job_id,
                host=settings.whisper_remote1_host, user=settings.whisper_remote1_user,
                key=settings.whisper_ssh_key_path, venv=settings.whisper_remote1_venv,
                label="remote1",
            )
        else:
            transcript = await _try_ssh_whisper(
                video_url, job_id, platform,
                host=settings.whisper_remote1_host, user=settings.whisper_remote1_user,
                key=settings.whisper_ssh_key_path, venv=settings.whisper_remote1_venv,
                label="remote1",
            )
        if transcript:
            return transcript

    if settings.whisper_ssh_key_path and settings.whisper_remote2_host:
        transcript = await _try_ssh_whisper(
            video_url, job_id, platform,
            host=settings.whisper_remote2_host, user=settings.whisper_remote2_user,
            key=settings.whisper_ssh_key_path, venv=settings.whisper_remote2_venv,
            label="remote2",
        )
        if transcript:
            return transcript

    if platform == "youtube":
        raise RuntimeError(
            "All YouTube transcript/transcription paths failed. "
            "Server IP is blocked by YouTube bot detection and no remote path succeeded."
        )
    return await _ytdlp_whisper(video_url, job_id, platform)


async def _try_youtube_api(url: str) -> Optional[str]:
    """Fast path: use youtube-transcript-api (no download needed)."""
    try:
        video_id = _extract_youtube_id(url)
        if not video_id:
            return None

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _fetch_yt_transcript, video_id)
    except Exception:
        return None


def _fetch_yt_transcript(video_id: str) -> Optional[str]:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        api = YouTubeTranscriptApi()
        transcript = api.fetch(video_id)
        return " ".join(snippet.text for snippet in transcript)
    except Exception:
        return None


def _extract_youtube_id(url: str) -> Optional[str]:
    patterns = [
        r"(?:v=|youtu\.be/|embed/)([A-Za-z0-9_-]{11})",
    ]
    for pat in patterns:
        m = re.search(pat, url)
        if m:
            return m.group(1)
    return None


async def _try_ssh_youtube_api(video_id: str) -> Optional[str]:
    """Run youtube_transcript_api on the primary whisper remote (residential IP) to bypass server block."""
    import logging
    log = logging.getLogger(__name__)

    py_cmd = (
        "from youtube_transcript_api import YouTubeTranscriptApi; "
        f"api = YouTubeTranscriptApi(); "
        f"t = api.fetch('{video_id}'); "
        "import sys; sys.stdout.write(' '.join(s.text for s in t))"
    )
    try:
        proc = await asyncio.create_subprocess_exec(
            "ssh", "-i", settings.whisper_ssh_key_path,
            "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10",
            f"{settings.whisper_remote1_user}@{settings.whisper_remote1_host}",
            f"{settings.whisper_remote1_venv}/bin/python3 -c \"{py_cmd}\"",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=90)
        if proc.returncode == 0:
            text = stdout.decode().strip()
            if len(text) > 200:
                log.info(f"SSH YouTube API: got {len(text)} chars")
                return text
            log.warning(f"SSH YouTube API: too short ({len(text)} chars)")
        else:
            log.warning(f"SSH YouTube API failed: {stderr.decode()[:300]}")
    except asyncio.TimeoutError:
        log.warning("SSH YouTube API timed out")
    except Exception as e:
        log.warning(f"SSH YouTube API error: {e}")
    return None


async def _try_ssh_yt_whisper(url: str, job_id: str,
                               host: str, user: str, key: str,
                               venv: str, label: str) -> Optional[str]:
    """For YouTube: download audio + transcribe entirely on remote to bypass IP block."""
    import logging
    log = logging.getLogger(__name__)

    remote_audio = f"/tmp/{job_id}_yt_audio.mp3"
    remote_out = f"/tmp/{job_id}_yt_out.txt"

    log.info(f"SSH YT Whisper [{label}]: downloading audio on remote...")
    dl_cmd = (
        f"python3 -m yt_dlp --extract-audio --audio-format mp3 --audio-quality 5 "
        f"--no-playlist -o '{remote_audio}' '{url}'"
    )
    try:
        ssh_dl = await asyncio.create_subprocess_exec(
            "ssh", "-i", key, "-o", "StrictHostKeyChecking=no",
            f"{user}@{host}", dl_cmd,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        _, dl_stderr = await asyncio.wait_for(ssh_dl.communicate(), timeout=600)
        if ssh_dl.returncode != 0:
            log.warning(f"SSH YT Whisper [{label}]: yt-dlp failed: {dl_stderr.decode()[:300]}")
            return None

        log.info(f"SSH YT Whisper [{label}]: transcribing...")
        whisper_cmd = (
            f"{venv}/bin/python3 -c \""
            f"from faster_whisper import WhisperModel; "
            f"m = WhisperModel('large-v3', device='auto', compute_type='auto'); "
            f"segs, _ = m.transcribe('{remote_audio}', beam_size=5, language='en'); "
            f"open('{remote_out}', 'w').write(' '.join(s.text.strip() for s in segs))"
            f"\""
        )
        ssh = await asyncio.create_subprocess_exec(
            "ssh", "-i", key, "-o", "StrictHostKeyChecking=no",
            f"{user}@{host}", whisper_cmd,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        _, ssh_err = await asyncio.wait_for(ssh.communicate(), timeout=3600)
        if ssh.returncode != 0:
            log.warning(f"SSH YT Whisper [{label}]: whisper failed: {ssh_err.decode()[:200]}")
            return None

        cat_proc = await asyncio.create_subprocess_exec(
            "ssh", "-i", key, "-o", "StrictHostKeyChecking=no",
            f"{user}@{host}", f"cat '{remote_out}'",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        result_stdout, _ = await cat_proc.communicate()
        text = result_stdout.decode().strip()
        log.info(f"SSH YT Whisper [{label}]: got {len(text)} chars")
        return text if len(text) > 200 else None

    except asyncio.TimeoutError:
        log.warning(f"SSH YT Whisper [{label}]: timed out")
        return None
    except Exception as e:
        log.warning(f"SSH YT Whisper [{label}]: error: {e}")
        return None
    finally:
        try:
            cleanup = await asyncio.create_subprocess_exec(
                "ssh", "-i", key, "-o", "StrictHostKeyChecking=no",
                f"{user}@{host}", f"rm -f '{remote_audio}' '{remote_out}'",
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
            )
            await cleanup.communicate()
        except Exception:
            pass


async def _try_platform_captions(url: str, platform: str) -> Optional[str]:
    """Try to fetch pre-existing caption/transcript file from platform CDN."""
    import httpx
    import re as _re

    caption_url = None

    if platform == "granicus":
        m = _re.search(r'clip_id=(\d+)', url) or _re.search(r'/clip/(\d+)', url)
        if m:
            clip_id = m.group(1)
            base = _re.match(r'(https?://[^/]+)', url)
            if base:
                caption_url = f"{base.group(1)}/videos/{clip_id}/captions.vtt"

    elif platform == "swagit":
        m = _re.search(r'/videos/(\d+)', url)
        if m:
            vid_id = m.group(1)
            base = _re.match(r'(https?://[^/]+)', url)
            if base:
                caption_url = f"{base.group(1)}/videos/{vid_id}/captions.vtt"

    if not caption_url:
        return None

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(caption_url, follow_redirects=True)
        if resp.status_code != 200:
            return None
        vtt = resp.text.strip()
        if len(vtt) < 200 or vtt.count('\n') < 5:
            return None
        lines = vtt.splitlines()
        text_lines = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith('WEBVTT') or line.startswith('NOTE') or '-->' in line:
                continue
            if _re.match(r'^\d+$', line):
                continue
            text_lines.append(line)
        text = ' '.join(text_lines).strip()
        if len(text) < 200:
            return None
        import logging
        logging.getLogger(__name__).info(f"Caption fast path: got {len(text)} chars from {caption_url}")
        return text
    except Exception:
        return None


async def _try_groq_whisper(url: str, job_id: str, platform: str) -> Optional[str]:
    """Transcribe via Groq Whisper API (real-time speed). Requires GROQ_API_KEY."""
    import httpx

    groq_key = settings.groq_api_key
    if not groq_key:
        return None

    import logging
    log = logging.getLogger(__name__)
    log.info("Groq fast path: downloading audio for Groq Whisper transcription...")

    tmp_dir = _tmp_path()
    audio_out = str(tmp_dir / f"{job_id}_groq_audio.mp3")

    if platform in ("cablecast", "civiclive", "granicus"):
        url = await _resolve_embed_url(url)

    yt_dlp = settings.yt_dlp_path
    cmd = [
        yt_dlp,
        "--extract-audio", "--audio-format", "mp3", "--audio-quality", "5",
        "--no-playlist", "--js-runtimes", "node:/usr/bin/node",
        "--output", audio_out, url,
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        log.warning(f"Groq path: yt-dlp failed: {stderr.decode()[:200]}")
        return None

    if not Path(audio_out).exists():
        candidates = list(tmp_dir.glob(f"{job_id}_groq_audio*"))
        if not candidates:
            return None
        audio_out = str(candidates[0])

    file_size = Path(audio_out).stat().st_size
    log.info(f"Groq fast path: uploading {file_size // 1024 // 1024}MB to Groq Whisper...")

    try:
        async with httpx.AsyncClient(timeout=300) as client:
            with open(audio_out, 'rb') as f:
                resp = await client.post(
                    "https://api.groq.com/openai/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {groq_key}"},
                    files={"file": (f"{job_id}.mp3", f, "audio/mpeg")},
                    data={"model": "whisper-large-v3-turbo", "response_format": "text"},
                )
        if resp.status_code == 200:
            text = resp.text.strip()
            log.info(f"Groq fast path: got {len(text)} chars")
            return text if len(text) > 200 else None
        else:
            log.warning(f"Groq API returned {resp.status_code}: {resp.text[:200]}")
            return None
    except Exception as e:
        log.warning(f"Groq fast path error: {e}")
        return None
    finally:
        try:
            os.unlink(audio_out)
        except OSError:
            pass


async def _try_ssh_whisper(url: str, job_id: str, platform: str,
                           host: str, user: str, key: str,
                           venv: str, label: str) -> Optional[str]:
    """Transcribe using faster-whisper on a remote machine via SSH/SCP."""
    import logging
    log = logging.getLogger(__name__)

    tmp_dir = _tmp_path()
    local_audio = str(tmp_dir / f"{job_id}_ssh_audio.mp3")
    remote_audio = f"/tmp/{job_id}_whisper_audio.mp3"
    remote_out = f"/tmp/{job_id}_whisper_out.txt"

    log.info(f"SSH Whisper [{label}]: downloading audio...")

    if platform in ("cablecast", "civiclive", "granicus"):
        url = await _resolve_embed_url(url)

    yt_dlp = settings.yt_dlp_path
    cmd = [
        yt_dlp,
        "--extract-audio", "--audio-format", "mp3", "--audio-quality", "5",
        "--no-playlist", "--js-runtimes", "node:/usr/bin/node",
        "--output", local_audio, url,
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        log.warning(f"SSH Whisper [{label}]: yt-dlp failed: {stderr.decode()[:200]}")
        return None

    if not Path(local_audio).exists():
        candidates = list(tmp_dir.glob(f"{job_id}_ssh_audio*"))
        if not candidates:
            return None
        local_audio = str(candidates[0])

    try:
        log.info(f"SSH Whisper [{label}]: copying audio to remote...")
        scp = await asyncio.create_subprocess_exec(
            "scp", "-i", key, "-o", "StrictHostKeyChecking=no",
            local_audio, f"{user}@{host}:{remote_audio}",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        _, scp_err = await scp.communicate()
        if scp.returncode != 0:
            log.warning(f"SSH Whisper [{label}]: scp failed: {scp_err.decode()[:200]}")
            return None

        log.info(f"SSH Whisper [{label}]: transcribing...")
        whisper_cmd = (
            f"{venv}/bin/python3 -c \""
            f"from faster_whisper import WhisperModel; "
            f"m = WhisperModel('large-v3', device='auto', compute_type='auto'); "
            f"segs, _ = m.transcribe('{remote_audio}', beam_size=5, language='en'); "
            f"open('{remote_out}', 'w').write(' '.join(s.text.strip() for s in segs))"
            f"\""
        )
        ssh = await asyncio.create_subprocess_exec(
            "ssh", "-i", key, "-o", "StrictHostKeyChecking=no",
            f"{user}@{host}", whisper_cmd,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        _, ssh_err = await asyncio.wait_for(ssh.communicate(), timeout=3600)
        if ssh.returncode != 0:
            log.warning(f"SSH Whisper [{label}]: whisper failed: {ssh_err.decode()[:200]}")
            return None

        result_local = str(tmp_dir / f"{job_id}_ssh_result.txt")
        scp2 = await asyncio.create_subprocess_exec(
            "scp", "-i", key, "-o", "StrictHostKeyChecking=no",
            f"{user}@{host}:{remote_out}", result_local,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        await scp2.communicate()

        if not Path(result_local).exists():
            return None

        text = Path(result_local).read_text().strip()
        log.info(f"SSH Whisper [{label}]: got {len(text)} chars")
        return text if len(text) > 200 else None

    except asyncio.TimeoutError:
        log.warning(f"SSH Whisper [{label}]: timed out after 1h")
        return None
    except Exception as e:
        log.warning(f"SSH Whisper [{label}]: error: {e}")
        return None
    finally:
        for p in [local_audio, str(tmp_dir / f"{job_id}_ssh_result.txt")]:
            try:
                os.unlink(p)
            except OSError:
                pass
        try:
            cleanup = await asyncio.create_subprocess_exec(
                "ssh", "-i", key, "-o", "StrictHostKeyChecking=no",
                f"{user}@{host}", f"rm -f {remote_audio} {remote_out}",
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
            )
            await cleanup.communicate()
        except Exception:
            pass


async def _ytdlp_whisper(url: str, job_id: str, platform: str) -> str:
    """Download audio with yt-dlp, transcribe with faster-whisper."""
    tmp_dir = _tmp_path()
    audio_out = str(tmp_dir / f"{job_id}_audio.mp3")

    if platform in ("cablecast", "civiclive", "granicus"):
        url = await _resolve_embed_url(url)

    yt_dlp = settings.yt_dlp_path
    cmd = [
        yt_dlp,
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "5",
        "--no-playlist",
        "--js-runtimes", "node:/usr/bin/node",
        "--output", audio_out,
        url,
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"yt-dlp failed: {stderr.decode()[:500]}")

    if not Path(audio_out).exists():
        candidates = list(tmp_dir.glob(f"{job_id}_audio*"))
        if not candidates:
            raise RuntimeError("Audio file not found after yt-dlp extraction")
        audio_out = str(candidates[0])

    transcript = await _whisper_transcribe(audio_out)

    try:
        os.unlink(audio_out)
    except OSError:
        pass

    return transcript


async def _whisper_transcribe(audio_path: str) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _run_whisper, audio_path)


def _run_whisper(audio_path: str) -> str:
    from faster_whisper import WhisperModel
    model = WhisperModel("base", device="cpu", compute_type="int8")
    segments, _ = model.transcribe(audio_path, beam_size=5, language="en")
    return " ".join(seg.text.strip() for seg in segments)


async def _resolve_embed_url(page_url: str) -> str:
    """Extract actual stream URL from a player page (Cablecast, CivicLive, Granicus)."""
    import httpx
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(page_url, follow_redirects=True)
        html = resp.text

    m = re.search(r'(?:https?:)?//[^\s"\']*granicus[^\s"\']*/OnDemand/[^\s"\']*\.m3u8', html)
    if m:
        url = m.group(0)
        if url.startswith("//"):
            url = "https:" + url
        return url

    patterns = [
        r'src=["\']([^"\']*(?:m3u8|mp4|stream)[^"\']*)["\']',
        r'file:\s*["\']([^"\']+(?:m3u8|mp4)[^"\']*)["\']',
        r'"url":\s*"([^"]+(?:m3u8|mp4)[^"]*)"',
    ]
    for pat in patterns:
        m = re.search(pat, html)
        if m:
            return m.group(1)

    return page_url
