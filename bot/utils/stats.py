# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


def format_stats_text(total_users: int, total_clones: int, running_clones: int, uptime_str: str) -> str:
    return (
        "Bot Stats\n\n"
        f"Users: {total_users}\n"
        f"Clones: {total_clones} total, {running_clones} running\n"
        f"Uptime: {uptime_str}\n"
    )
