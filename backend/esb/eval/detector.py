from urllib.parse import urlparse


def detect_platform(url: str) -> str:
    parsed = urlparse(url.lower())
    host = parsed.netloc.replace("www.", "")
    path = parsed.path

    if "youtube.com" in host or "youtu.be" in host:
        return "youtube"
    if "vimeo.com" in host:
        return "vimeo"
    if "granicus.com" in host or "/player/" in path or "/mediaplayer/" in path:
        return "granicus"
    if "swagit.com" in host:
        return "swagit"
    if "cablecast.tv" in host or "/live/show/" in path or "/vod/" in path:
        return "cablecast"
    if "facebook.com" in host or "fb.com" in host:
        return "facebook"
    if "civiclive.com" in host or "civic-live.com" in host:
        return "civiclive"
    return "generic"
