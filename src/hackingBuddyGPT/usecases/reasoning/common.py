import datetime
import pathlib
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from mako.template import Template

from hackingBuddyGPT.capabilities import Capability
from hackingBuddyGPT.capabilities.capability import capabilities_to_simple_text_handler
from hackingBuddyGPT.usecases.agents import Agent
from hackingBuddyGPT.utils import llm_util
from hackingBuddyGPT.utils.cli_history import SlidingCliHistory
from hackingBuddyGPT.utils.logging import log_conversation, log_section

template_dir = pathlib.Path(__file__).parent / "templates"
template_next_cmd = Template(filename=str(template_dir / "query_next_command.txt"))
template_analyze = Template(filename=str(template_dir / "analyze_cmd.txt"))
template_state = Template(filename=str(template_dir / "update_state.txt"))
template_summarize = Template(filename=str(template_dir / "summarize_output.txt"))


@dataclass
class ReasoningPrivesc(Agent):
    system: str = ""
    enable_explanation: bool = False
    enable_update_state: bool = False
    disable_history: bool = False
    hint: str = ""
    conn: Any = None  # Add this line to define the conn attribute
    known_exploit_file : str = ""
    known_exploit: str = ""

    _sliding_history: Optional[SlidingCliHistory] = None
    _state: str = ""
    _capabilities: Dict[str, Capability] = field(default_factory=dict)
    _template_params: Dict[str, Any] = field(default_factory=dict)
    _max_history_size: int = 0

    def read_exploit_file(self):
        try:
            with open(self.known_exploit_file, "r") as file:
                self.known_exploit = file.read()
        except FileNotFoundError:
            self.log.error(f"Exploit file '{self.known_exploit_file}' not found.")
        except Exception as e:
            self.log.error(f"Error reading exploit file: {e}")

    def get_capability_block(self) -> str:
        capability_descriptions, _parser = capabilities_to_simple_text_handler(self._capabilities)
        return "You can use the following tools:\n\n" + "\n".join(
            f"- {description}" for description in capability_descriptions.values()
        )

    def before_run(self):
        if self.hint != "":
            self.log.status_message(f"[bold green]Using the following hint: '{self.hint}'")
        
        if self.known_exploit_file != "":
            self.log.status_message(f"[bold green]Using the following known exploit file: '{self.known_exploit_file}'")
            self.read_exploit_file()

        if self.disable_history is False:
            self._sliding_history = SlidingCliHistory(self.llm, template_summarize, reasoning=True)

        self._template_params = {
            "capabilities": self.get_capability_block(),
            "system": self.system,
            "hint": self.hint,
            "known_exploit": self.known_exploit,
            "conn": self.conn,
            "update_state": self.enable_update_state,
            "target_user": "root",
        }

        template_size = self.llm.count_tokens(template_next_cmd.source)
        self._max_history_size = self.llm.context_size - llm_util.SAFETY_MARGIN - template_size

    def perform_round(self, turn: int) -> bool:
        # get the next command and run it
        cmd, message_id = self.get_next_command()
        result, got_root = self.run_command(cmd, message_id)

        # log and output the command and its result
        if self._sliding_history:
            self._sliding_history.add_command(cmd, result if result is not None else "")

        # analyze the result..
        if self.enable_explanation:
            self.analyze_result(cmd, result)

        # .. and let our local model update its state
        if self.enable_update_state:
            self.update_state(cmd, result)

        # if we got root, we can stop the loop
        return got_root

    def get_state_size(self) -> int:
        if self.enable_update_state:
            return self.llm.count_tokens(self._state)
        else:
            return 0

    @log_conversation("Asking LLM for a new command...", start_section=True)
    def get_next_command(self) -> tuple[str, int]:
        history = ""
        if not self.disable_history and self._sliding_history:
            history = self._sliding_history.get_history(self._max_history_size - self.get_state_size())

        self._template_params.update({"history": history, "state": self._state})

        cmd = self.llm.get_response(template_next_cmd, **self._template_params)
        message_id = self.log.call_response(cmd)
        return llm_util.cmd_output_fixer(cmd.result, capabilities=self._capabilities.keys(), reasoning=True), message_id

    @log_section("Executing that command...")
    def run_command(self, cmd, message_id) -> tuple[Optional[str], bool]:
        _capability_descriptions, parser = capabilities_to_simple_text_handler(
            self._capabilities, default_capability=self._default_capability
        )
        start_time = datetime.datetime.now()
        success, *output = parser(cmd)
        capability, cmd, (result, got_root) = output[0]
        result = llm_util.remove_nonprintable(result)
        if not success:
            self.log.add_tool_call(
                message_id, tool_call_id=0, function_name="", arguments=cmd, result_text=str(output[0]), duration=0
            )
            return str(output[0]), False

        assert len(output) == 1
        duration = datetime.datetime.now() - start_time
        self.log.add_tool_call(
            message_id, tool_call_id=0, function_name=capability, arguments=cmd, result_text=result, duration=duration
        )

        return result, bool(got_root)

    @log_conversation("Analyze its result...", start_section=True)
    def analyze_result(self, cmd, result):
        state_size = self.get_state_size()
        target_size = self.llm.context_size - llm_util.SAFETY_MARGIN - state_size

        # ugly, but cut down result to fit context size
        result = llm_util.trim_result_front(self.llm, target_size, result)
        answer = self.llm.get_response(template_analyze, cmd=cmd, resp=result, facts=self._state)
        answer.result = llm_util.remove_think_block(answer.result)
        self.log.call_response(answer)

    @log_conversation("Updating fact list..", start_section=True)
    def update_state(self, cmd, result):
        # ugly, but cut down result to fit context size
        # don't do this linearly as this can take too long
        ctx = self.llm.context_size
        state_size = self.get_state_size()
        target_size = ctx - llm_util.SAFETY_MARGIN - state_size
        result = llm_util.trim_result_front(self.llm, target_size, result)

        state = self.llm.get_response(template_state, cmd=cmd, resp=result, facts=self._state)
        state.result = llm_util.remove_think_block(state.result)
        self._state = state.result
        self.log.call_response(state)
