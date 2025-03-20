import base64
import re
import json
from datetime import datetime
import threading
import queue
import asyncio

from prettytable import PrettyTable

from solace_ai_connector.common.log import log
from .discord_base import DiscordBase
from discord import TextChannel, File, ButtonStyle, Message as DiscordMessage, Interaction, InteractionType, ComponentType, Thread
from discord.ui import Button, View, Modal, TextInput
from discord.ext.commands import Bot


info = {
    "class_name": "DiscordOutput",
    "description": (
        "Discord output component. The component sends messages to Discord channels using the Bolt API."
    ),
    "config_parameters": [
        {
            "name": "discord_bot_token",
            "type": "string",
            "description": "The Discord bot token to connect to Discord.",
        },
        {
            "name": "share_discord_connection",
            "type": "string",
            "description": "Share the Discord connection with other components in this instance.",
        },
        {
            "name": "correct_markdown_formatting",
            "type": "boolean",
            "description": "Correct markdown formatting in messages to conform to Discord markdown.",
            "default": "true",
        },
        {
            "name": "feedback",
            "type": "boolean",
            "description": "Collect thumbs up/thumbs down from users.",
        },
        {
            "name": "feedback_post_url",
            "type": "string",
            "description": "URL to send feedback to.",
        },
        {
            "name": "feedback_post_headers",
            "type": "object",
            "description": "Headers to send with feedback post.",
        }
    ],
    "input_schema": {
        "type": "object",
        "properties": {
            "message_info": {
                "type": "object",
                "properties": {
                    "channel": {
                        "type": "string",
                    },
                    "client_msg_id": {
                        "type": "string",
                    },
                    "ts": {
                        "type": "string",
                    },
                    "event_ts": {
                        "type": "string",
                    },
                    "channel_type": {
                        "type": "string",
                    },
                    "user_id": {
                        "type": "string",
                    },
                    "session_id": {
                        "type": "string",
                    },
                },
                "required": ["channel", "session_id"],
            },
            "content": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                    },
                    "files": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {
                                    "type": "string",
                                },
                                "content": {
                                    "type": "string",
                                },
                                "mime_type": {
                                    "type": "string",
                                },
                                "filetype": {
                                    "type": "string",
                                },
                                "size": {
                                    "type": "number",
                                },
                            },
                        },
                    },
                },
            },
        },
        "required": ["message_info", "content"],
    },
}


class DiscordOutput(DiscordBase):
    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
        self.fix_formatting = self.get_config("correct_markdown_formatting", True)
        self.streaming_state = {}
        self.discord_message_response_queue = queue.Queue()

        DiscordSender(self.app, self.discord_bot_token, self.discord_message_response_queue, self.feedback_enabled).start()

    def invoke(self, message, data):
        content = data.get("content")
        message_info = data.get("message_info")

        text = content.get("text")
        uuid = content.get("uuid")
        files = content.get("files")
        streaming = content.get("streaming")
        status_update = content.get("status_update")
        response_complete = content.get("response_complete")
        last_chunk = content.get("last_chunk")
        first_chunk = content.get("first_chunk")

        thread_ts = message_info.get("ts")
        channel = message_info.get("channel")
        ack_msg_ts = message_info.get("ack_msg_ts")

        feedback_data = data.get("feedback_data", {})

        if response_complete:
            status_update = True
            text = ":checkered_flag: Response complete"
        elif status_update:
            text = ":thinking_face: " + text

        if not channel:
            log.error("discord_output: No channel specified in message")
            self.discard_current_message()
            return None

        return {
            "text": text,
            "uuid": uuid,
            "files": files,
            "streaming": streaming,
            "channel": channel,
            "thread_ts": thread_ts,
            "ack_msg_ts": ack_msg_ts,
            "status_update": status_update,
            "last_chunk": last_chunk,
            "first_chunk": first_chunk,
            "response_complete": response_complete,
            "feedback_data": feedback_data,
        }

    def send_message(self, message):
        self.discord_message_response_queue.put(message)
        super().send_message(message)

    def fix_markdown(self, message):
        # Fix links - the LLM is very stubborn about giving markdown links
        # Find [text](http...) and replace with <http...|text>
        message = re.sub(r"\[(.*?)\]\((http.*?)\)", r"<\2|\1>", message)
        # Remove the language specifier from code blocks
        message = re.sub(r"```[a-z]+\n", "```", message)
        # Fix bold
        message = re.sub(r"\*\*(.*?)\*\*", r"*\1*", message)

        # Reformat a table to be Discord compatible
        message = self.convert_markdown_tables(message)

        return message

    def get_streaming_state(self, uuid):
        return self.streaming_state.get(uuid)

    def add_streaming_state(self, uuid):
        state = {
            "create_time": datetime.now(),
        }
        self.streaming_state[uuid] = state
        self.age_out_streaming_state()
        return state

    def delete_streaming_state(self, uuid):
        try:
            del self.streaming_state[uuid]
        except KeyError:
            pass

    def age_out_streaming_state(self, age=60):
        # Note that we can later optimize this by using an array of streaming_state that
        # is ordered by create_time and then we can just remove the first element until
        # we find one that is not expired.
        now = datetime.now()
        for uuid, state in list(self.streaming_state.items()):
            if (now - state["create_time"]).total_seconds() > age:
                del self.streaming_state[uuid]

    def convert_markdown_tables(self, message):
        def markdown_to_fixed_width(match):
            table_str = match.group(0)
            rows = [
                line.strip().split("|")
                for line in table_str.split("\n")
                if line.strip()
            ]
            headers = [cell.strip() for cell in rows[0] if cell.strip()]

            pt = PrettyTable()
            pt.field_names = headers

            for row in rows[2:]:
                pt.add_row([cell.strip() for cell in row if cell.strip()])

            return f"\n```\n{pt.get_string()}\n```\n"

        pattern = r"\|.*\|[\n\r]+\|[-:| ]+\|[\n\r]+((?:\|.*\|[\n\r]+)+)"
        return re.sub(pattern, markdown_to_fixed_width, message)

class Feedback(Modal, title=''):
    feedback = TextInput(
        label='Feedback',
        placeholder='How can we improve this response?',
        required=False,
        max_length=300,
    )

    async def on_submit(self, interaction: Interaction):
        await interaction.response.send_message(f'Thanks for your feedback, {interaction.user.mention}!', ephemeral=True)

    async def on_error(self, interaction: Interaction, error: Exception) -> None:
        await interaction.response.send_message('Oops! Something went wrong.', ephemeral=True)

class DiscordSender(threading.Thread):
    def __init__(
        self,
        app: Bot,
        discord_bot_token,
        input_queue: queue.Queue[DiscordMessage],
        feedback_enabled: bool
    ):
        threading.Thread.__init__(self)
        self.app = app
        self.discord_bot_token = discord_bot_token
        self.input_queue = input_queue
        self.feedback_enabled = feedback_enabled
        self.last_sent_by_uuid = {}
        self.sent_message_by_uuid: dict[str, DiscordMessage] = {}
        self.last_content_len_by_uuid: dict[str, int] = {}

    def run(self):
        asyncio.run(self.really_run())

    @staticmethod
    def create_feedback_view() -> View:
        thumbsup_button = Button(label="👍", style=ButtonStyle.green, custom_id="thumbs_up")
        thumbsdown_button = Button(label="👎", style=ButtonStyle.red, custom_id="thumbs_down")

        view = View()
        view.add_item(thumbsup_button)
        view.add_item(thumbsdown_button)

        return view

    async def send_message(self, message):
        try:
            channel = message.get_data("previous:channel")
            messages = message.get_data("previous:text")
            streaming = message.get_data("previous:streaming")
            files = message.get_data("previous:files") or []
            reply_to = (message.get_user_properties() or {}).get("reply_to_thread", message.get_data("previous:thread_ts"))
            ack_msg_ts = message.get_data("previous:ack_msg_ts")
            first_chunk = message.get_data("previous:first_chunk")
            last_chunk = message.get_data("previous:last_chunk")
            uuid = message.get_data("previous:uuid")
            status_update = message.get_data("previous:status_update")
            response_complete = message.get_data("previous:response_complete")
            feedback_data = message.get_data("previous:feedback_data") or {}

            if not isinstance(messages, list):
                if messages is not None:
                    messages = [messages]
                else:
                    messages = []

            now = datetime.now().timestamp()
            text = ""

            for part in messages:
                if not part or not isinstance(part, str):
                    continue
                text += part

            if len(text) <= self.last_content_len_by_uuid.get(uuid, 0):
                return
            self.last_content_len_by_uuid[uuid] = len(text)

            # throttle responses
            if last_chunk or response_complete or now - self.last_sent_by_uuid.get(uuid, 0) > 1_200:
                self.last_sent_by_uuid[uuid] = now
            else:
                return

            text_channel = self.app.get_channel(channel)
            if not isinstance(text_channel, (TextChannel, Thread)):
                return

            full = text or "\u200b"
            if len(full) > 2000:
                full = full[:2000]

            view = self.create_feedback_view() if response_complete else None

            if uuid not in self.sent_message_by_uuid:
                sent_message = await text_channel.send(full, view=view) if view else await text_channel.send(full)
                self.sent_message_by_uuid[uuid] = sent_message
            else:
                sent_message = self.sent_message_by_uuid[uuid]
                await sent_message.edit(content=full, view=view)

            files_to_add = []

            for file in files:
                file_content = base64.b64decode(file["content"])
                files_to_add.append(File(fp=file_content, filename=file["name"]))

            if files_to_add:
                await sent_message.add_files(*files_to_add)

        except Exception as e:
            log.error("Error sending discord message: %s", e)
            raise e

    async def really_run(self):
        await self.app.login(self.discord_bot_token)

        asyncio.create_task(self.do_messages())
        self.register_action_handlers()

        await self.app.connect()
    
    async def do_messages(self):
        while True:
            try:
                message = self.input_queue.get_nowait()
                asyncio.create_task(self.send_message(message))
            except queue.Empty:
                await asyncio.sleep(0.01)

    def register_action_handlers(self):
        """
            _summary_ : Register the action handlers for the Discord bot
        """

        @self.app.event
        async def on_ready():
            await self.app.tree.sync()

        @self.app.event
        async def on_interaction(interaction: Interaction):
            if interaction.type != InteractionType.component:
                return
            if not interaction.data:
                return
            if "component_type" not in interaction.data or interaction.data["component_type"] != ComponentType.button.value:
                return

            custom_id = interaction.data["custom_id"]

            if interaction.message:
                await interaction.message.edit(view=None)

            match custom_id:
                case "thumbs_up": await self.thumbs_up_callback(interaction)
                case "thumbs_down": await self.thumbs_down_callback(interaction)

    async def thumbs_up_callback(self, interaction: Interaction):
        await interaction.response.send_message("You clicked thumbs up!", ephemeral=True)

    async def thumbs_down_callback(self, interaction: Interaction):
        await interaction.response.send_modal(Feedback())