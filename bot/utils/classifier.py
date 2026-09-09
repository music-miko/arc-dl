# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


import re


class MessageClassifier:
    def __init__(self):
        self.youtube_playlist_re = re.compile(
            r"(?:youtube\.com|youtu\.be).*[?&]list=([A-Za-z0-9_-]+)", re.I
        )
        self.youtube_video_re = re.compile(
            r"(?:youtube\.com/(?:watch\?v=|shorts/)|youtu\.be/)([A-Za-z0-9_-]{11})", re.I
        )
        self.youtube_bare_id_re = re.compile(r"^[A-Za-z0-9_-]{11}$")

        self.spotify_playlist_re = re.compile(r"open\.spotify\.com/playlist/", re.I)
        self.spotify_track_re = re.compile(r"open\.spotify\.com/track/", re.I)

        self.soundcloud_re = re.compile(r"soundcloud\.com/", re.I)

        self.instagram_re = re.compile(
            r"^https?://(www\.)?instagram\.com/(p|reel|reels|tv|stories|share)/.+", re.I
        )
        self.facebook_re = re.compile(r"^https?://(www\.|web\.|m\.)?(facebook\.com|fb\.watch)/.+", re.I)
        self.threads_re = re.compile(r"^https?://(www\.)?threads\.(net|com)/.+", re.I)
        self.bluesky_re = re.compile(r"^https?://(www\.)?bsky\.app/.+", re.I)
        self.tiktok_re = re.compile(r"^https?://(www\.|vm\.|vt\.)?tiktok\.com/.+", re.I)
        self.twitter_re = re.compile(
            r"^https?://(www\.)?(twitter\.com|x\.com)/(?:[A-Za-z0-9_]+|i)/status/\d+", re.I
        )
        self.pinterest_re = re.compile(r"^https?://(www\.)?(pinterest\.[a-z.]+|pin\.it)/.+", re.I)
        self.reddit_re = re.compile(
            r"^https?://((www\.|old\.|new\.|m\.)?reddit\.com/.+|redd\.it/.+)", re.I
        )

        self.terabox_re = re.compile(
            r"^https?://([a-z0-9-]+\.)*"
            r"(terabox\w*|1024tera\w*|terasharelink|terafileshare|"
            r"nephobox|4funbox|mirrobox|momerybox|freeterabox)"
            r"\.(com|app|net|co|link|cc)/.+",
            re.I,
        )

        self.applemusic_url_re = re.compile(
            r"^https?://music\.apple\.com/([a-z]{2})/(song|album|playlist)/[^/?#]+(?:/[^/?#]+)*?/(\d+|pl\.[a-z0-9]+)",
            re.I,
        )
        self.jiosaavn_url_re = re.compile(
            r"^https?://(www\.)?jiosaavn\.com/(song|album|playlist|featured)/", re.I
        )

        self.url_re = re.compile(r"https?://\S+", re.I)

        self.social_patterns = [
            ("instagram", self.instagram_re),
            ("facebook", self.facebook_re),
            ("threads", self.threads_re),
            ("bluesky", self.bluesky_re),
            ("tiktok", self.tiktok_re),
            ("twitter", self.twitter_re),
            ("pinterest", self.pinterest_re),
            ("reddit", self.reddit_re),
        ]
        self.social_kinds = {kind for kind, _ in self.social_patterns}
        self.social_labels = {
            "instagram": "Instagram media",
            "facebook": "Facebook media",
            "threads": "Threads media",
            "bluesky": "Bluesky media",
            "tiktok": "TikTok video",
            "twitter": "Twitter/X media",
            "pinterest": "Pinterest media",
            "reddit": "Reddit media",
        }

    def classify(self, text: str) -> tuple[str, str]:
        text = text.strip()

        if self.spotify_playlist_re.search(text):
            return "spotify_playlist", text
        if self.spotify_track_re.search(text):
            return "spotify_track", text
        if self.youtube_playlist_re.search(text):
            return "youtube_playlist", text
        if self.youtube_video_re.search(text) or self.youtube_bare_id_re.match(text):
            return "youtube_video", text
        if self.soundcloud_re.search(text):
            return "soundcloud", text

        if self.terabox_re.match(text):
            return "terabox", text

        apple_match = self.applemusic_url_re.match(text)
        if apple_match:
            media_type = apple_match.group(2)
            if media_type == "song" or "i=" in text.split("?", 1)[-1]:
                return "applemusic_track", text
            return "applemusic_playlist", text

        if self.jiosaavn_url_re.match(text):
            if "/song/" in text:
                return "jiosaavn_track", text
            return "jiosaavn_playlist", text

        for kind, pattern in self.social_patterns:
            if pattern.match(text):
                return kind, text

        if self.url_re.match(text):
            return "unsupported_url", text

        return "search", text


classifier = MessageClassifier()
