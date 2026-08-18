# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


from typing import Any, Callable

from pyrogram import Client


class HandlerRegistry:
    def __init__(self, name: str):
        self.name = name
        self._entries: list[tuple[type, Callable, Any]] = []

    def on(self, handler_cls: type, filters: Any = None) -> Callable:
        def decorator(func: Callable) -> Callable:
            self._entries.append((handler_cls, func, filters))
            return func
        return decorator

    def attach(self, client: Client) -> int:
        for handler_cls, func, filt in self._entries:
            client.add_handler(handler_cls(func, filt))
        return len(self._entries)

    def __len__(self) -> int:
        return len(self._entries)
