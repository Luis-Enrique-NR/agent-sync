"""Offline deterministic Portal adapter for contract tests."""

from transport.portal import PortalOutcome, PublishMessage, PublishedMessage


class RecordingPortalAdmin:
    def __init__(self) -> None:
        self.calls: list[PublishMessage] = []

    async def execute(self, command: PublishMessage) -> PortalOutcome:
        self.calls.append(command)
        return PublishedMessage(id=f"fake-{len(self.calls)}", seq=len(self.calls), timestamp=0)
