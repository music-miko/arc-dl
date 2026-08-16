# Copyright (c) 2026 tusar404
# Licensed under the MIT License.


import uuid
from collections import OrderedDict


class TokenCache:
    def __init__(self, max_entries: int = 5000):
        self.max_entries = max_entries
        self.store: "OrderedDict[str, dict]" = OrderedDict()

    def put(self, token: str, data: dict) -> None:
        self.store[token] = data
        self.store.move_to_end(token)
        while len(self.store) > self.max_entries:
            self.store.popitem(last=False)

    def put_new(self, data: dict) -> str:
        token = uuid.uuid4().hex[:10]
        self.put(token, data)
        return token

    def get(self, token: str) -> dict | None:
        return self.store.get(token)


cache = TokenCache()
