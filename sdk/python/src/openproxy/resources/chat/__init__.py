from .completions import SyncChatCompletionsResource, AsyncChatCompletionsResource


class SyncChatResource:
    def __init__(self, client):
        self.completions = SyncChatCompletionsResource(client)


class AsyncChatResource:
    def __init__(self, client):
        self.completions = AsyncChatCompletionsResource(client)
