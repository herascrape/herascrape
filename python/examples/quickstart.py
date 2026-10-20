"""Look up a profile and list its first followers.

export HERASCRAPE_API_KEY="hs_live_xxxxxxxx"
python examples/quickstart.py [username]
"""

import os
import sys

from herascrape import (
    Client,
    HerascrapeError,
    PrivateAccountError,
    ProfileNotFoundError,
)

FOLLOWERS_TO_SHOW = 10


def main(username: str) -> int:
    if not os.environ.get("HERASCRAPE_API_KEY"):
        print("Set HERASCRAPE_API_KEY first.", file=sys.stderr)
        return 1

    with Client() as client:
        try:
            user = client.user_by_username(username=username)
            print(f"@{user['username']}: {user['follower_count']} followers")
            followers = client.iter_user_followers(
                user["pk"], max_items=FOLLOWERS_TO_SHOW
            )
            for follower in followers:
                print(f"  @{follower['username']}")
        except ProfileNotFoundError:
            print(f"No such profile: @{username}", file=sys.stderr)
            return 1
        except PrivateAccountError:
            print(f"@{username} is private.", file=sys.stderr)
            return 1
        except HerascrapeError as exc:
            print(f"Request failed: {exc}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "instagram"))
