"""
Turns raw user input (a link, a bare video ID, or a plain search phrase)
into a (kind, value) pair the rest of the bot can branch on. All the
regex live as attributes on `MessageClassifier`, compiled once in
`__init__` — no loose module-level `_XXX_RE = re.compile(...)` constants
floating around for other files to reach into.
"""

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

        # Instagram/X are narrowed to the actual post-permalink shapes
        # (rather than "any instagram.com/x.com URL") so a profile link or
        # a bare hashtag page is classified as unsupported instead of being
        # forwarded to Arc API and coming back as a confusing 404 — every
        # shape here is still a *subset* of what Arc API itself accepts, so
        # nothing that used to work stops working.
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

        self.url_re = re.compile(r"https?://\S+", re.I)

        # Ordered (platform_kind, pattern) — first match wins. Shared by the
        # plain-text handler and the inline-query handler so both recognize
        # the same links.
        self.social_patterns = [
            ("instagram", self.instagram_re),
            ("facebook", self.facebook_re),
            ("threads", self.threads_re),
            ("bluesky", self.bluesky_re),
            ("tiktok", self.tiktok_re),
            ("twitter", self.twitter_re),
        ]

    def classify(self, text: str) -> tuple[str, str]:
        """Returns (kind, value) where kind is one of:
        'youtube_playlist', 'youtube_video', 'spotify_playlist', 'spotify_track',
        'soundcloud', 'instagram', 'facebook', 'threads', 'bluesky', 'tiktok',
        'twitter', 'unsupported_url', 'search'. `value` is the relevant link/id/query.
        """
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

        for kind, pattern in self.social_patterns:
            if pattern.match(text):
                return kind, text

        if self.url_re.match(text):
            # Some other URL we don't understand — treat as unsupported
            # rather than silently searching YouTube for a raw link.
            return "unsupported_url", text

        return "search", text


classifier = MessageClassifier()
