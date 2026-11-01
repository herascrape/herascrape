"""Authoritative OpenAPI path to public method-name map (44 GET endpoints).

Hand-maintained public surface, consumed by ``generate.py``. Keep in sync
with ``openapi.json``; the generator asserts full coverage.
"""

PATH_METHOD_NAMES: dict[str, str] = {
    "/users/username/{username}": "user_by_username",
    "/users/{user_id}": "user",
    "/users/{user_id}/followers": "user_followers",
    "/users/{user_id}/following": "user_following",
    "/users/{user_id}/posts": "user_posts",
    "/users/{user_id}/reels": "user_reels",
    "/users/{user_id}/tagged": "user_tagged",
    "/users/{user_id}/stories": "user_stories",
    "/users/{user_id}/highlights": "user_highlights",
    "/users/{user_id}/reposts": "user_reposts",
    "/users/{user_id}/about": "user_about",
    "/users/{user_id}/similar": "user_similar",
    "/posts/counts": "post_counts",
    "/posts/{post_id}": "post",
    "/posts/{post_id}/comments": "post_comments",
    "/posts/{post_id}/likers": "post_likers",
    "/posts/{post_id}/likers/all": "post_likers_all",
    "/comments/{comment_id}/replies": "comment_replies",
    "/comments/{comment_id}/likers": "comment_likers",
    "/search/users": "search_users",
    "/search/hashtags": "search_hashtags",
    "/search/audio": "search_audio",
    "/search/top": "search_top",
    "/search/places": "search_places",
    "/search/reels": "search_reels",
    "/hashtags/{name}": "hashtag",
    "/hashtags/{name}/top": "hashtag_top",
    "/hashtags/{name}/recent": "hashtag_recent",
    "/hashtags/{name}/reels": "hashtag_reels",
    "/locations/{location_id}": "location",
    "/locations/{location_id}/top": "location_top",
    "/locations/{location_id}/recent": "location_recent",
    "/highlights/{highlight_id}": "highlight",
    "/stories/{story_id}": "story",
    "/stories/templates/{template_id}": "story_template",
    "/stories/templates/{template_id}/participants": (
        "story_template_participants"
    ),
    "/stories/templates/{template_id}/stories": "story_template_stories",
    "/audio/trending": "audio_trending",
    "/audio/{audio_id}": "audio",
    "/audio/{audio_id}/medias": "audio_medias",
    "/resolve/media": "resolve_media",
    "/oembed": "oembed",
    "/system/health": "health",
    "/system/balance": "balance",
}
