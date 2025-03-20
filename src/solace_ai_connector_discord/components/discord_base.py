"""Base class for all Discord components"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from solace_ai_connector.components.component_base import ComponentBase

@dataclass(slots=True)
class FeedbackEndpoint:
    url: str
    headers: dict[str, str]

class DiscordBase(ComponentBase, ABC):
    _discord_apps = {}

    def __init__(self, module_info, **kwargs):
        super().__init__(module_info, **kwargs)

        discord_bot_token = self.get_config("discord_bot_token")
        max_file_size = self.get_config("max_file_size", 20)
        max_total_file_size = self.get_config("max_total_file_size", 20)
        feedback_enabled = self.get_config("feedback", False)
        command_prefix = self.get_config("command_prefix", "!")

        assert isinstance(discord_bot_token, str), "discord_bot_token must be a str"
        assert isinstance(max_file_size, int), "max_file_size must be an int"
        assert isinstance(max_total_file_size, int), "max_total_file_size must be an int"
        assert isinstance(feedback_enabled, bool), "feedback_enabled must be a bool"

        if feedback_enabled:
            feedback_post_url = self.get_config("feedback_post_url", None)
            feedback_post_headers = self.get_config("feedback_post_headers", {})

            assert isinstance(feedback_post_url, str), "feedback_post_url must be a str"
            assert isinstance(feedback_post_headers, dict), "feedback_post_headers must be a str"
            
            feedback_endpoint = FeedbackEndpoint(url=feedback_post_url, headers=feedback_post_headers)
        else:
            feedback_endpoint = None

        assert isinstance(command_prefix, str), "command_prefix must be a str"

        self.discord_bot_token = discord_bot_token
        self.max_file_size = max_file_size
        self.max_total_file_size = max_total_file_size
        self.feedback_endpoint = feedback_endpoint
        self.command_prefix = command_prefix

    @abstractmethod
    def invoke(self, message, data):
        pass

    def __str__(self):
        return self.__class__.__name__ + " " + str(self.config)

    def __repr__(self):
        return self.__str__()
