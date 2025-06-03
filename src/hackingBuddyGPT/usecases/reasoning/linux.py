from hackingBuddyGPT.capabilities import SSHRunCommand, SSHTestCredential
from hackingBuddyGPT.usecases.base import AutonomousAgentUseCase, use_case
from hackingBuddyGPT.utils import SSHConnection

from .common import ReasoningPrivesc


class ReasoningLinuxPrivesc(ReasoningPrivesc):
    conn: SSHConnection = None
    system: str = "Linux"

    def init(self):
        super().init()
        self.add_capability(SSHTestCredential(conn=self.conn))
        self.add_capability(SSHRunCommand(conn=self.conn), default=True)


@use_case("Reasoning Linux Privilege Escalation")
class ReasoningLinuxPrivescUseCase(AutonomousAgentUseCase[ReasoningLinuxPrivesc]):
    pass
