"""Offline deterministic Portal adapter for contract tests."""

from transport.portal import AddChannelMembers, AuthorizedPortalCommand, CommandApplied, PortalOutcome, PublishMessage, PublishedMessage


class RecordingPortalAdmin:
    def __init__(self) -> None:
        self.calls: list[AuthorizedPortalCommand] = []

    async def execute(self, command: AuthorizedPortalCommand) -> PortalOutcome:
        self.calls.append(command)
        if isinstance(command, AddChannelMembers):
            return CommandApplied(operation=command.operation, added=len(command.members))
        if not isinstance(command, PublishMessage):
            return CommandApplied(operation=command.operation)
        return PublishedMessage(id=f"fake-{len(self.calls)}", seq=len(self.calls), timestamp=0)
