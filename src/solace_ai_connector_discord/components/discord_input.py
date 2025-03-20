import threading
import queue
import base64
import requests


from solace_ai_connector.common.message import Message
from solace_ai_connector.common.log import log
from .discord_base import DiscordBase
from discord import Message as DiscordMessage, DMChannel, PartialMessageable, Client, Thread, TextChannel, Intents

def trunc(text: str, max: int = 20):
  return text[:max] if len(text) > max else text

info = {
    "class_name": "DiscordInput",
    "description": (
        "Discord input component. The component connects to Discord using the Discord API "
        "and receives messages from Discord channels."
    ),
    "config_parameters": [
        {
            "name": "discord_bot_token",
            "type": "string",
            "description": "The Discord bot token to connect to Discord.",
        },
        {
            "name": "max_file_size",
            "type": "number",
            "description": "The maximum file size to download from Discord in MB. Default: 20MB",
            "default": 20,
            "required": False,
        },
        {
            "name": "max_total_file_size",
            "type": "number",
            "description": "The maximum total file size to download "
            "from Discord in MB. Default: 20MB",
            "default": 20,
            "required": False,
        },
        {
            "name": "listen_to_channels",
            "type": "boolean",
            "description": "Whether to listen to channels or not. Default: False",
            "default": False,
            "required": False,
        },
        {
            "name": "send_history_on_join",
            "type": "boolean",
            "description": "Send history on join. Default: False",
            "default": False,
            "required": False,
        },
        {
            "name": "acknowledgement_message",
            "type": "string",
            "description": (
                "The message to send to acknowledge the "
                "user's message has been received."
            ),
            "required": False,
        },
    ],
    "output_schema": {
        "type": "object",
        "properties": {
            "event": {
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
                    "user_id": {
                        "type": "string",
                    },
                    "client_msg_id": {
                        "type": "string",
                    },
                    "ts": {
                        "type": "string",
                    },
                    "channel": {
                        "type": "string",
                    },
                    "event_ts": {
                        "type": "string",
                    },
                    "channel_type": {
                        "type": "string",
                    },
                },
            },
        },
        "required": ["event"],
    },
}


class DiscordInput(DiscordBase):
    discord_receiver_queue: queue.Queue[DiscordMessage]

    def __init__(self, **kwargs):
        super().__init__(info, use_bot=False,  **kwargs)
        self.init_discord_receiver()

    def init_discord_receiver(self):
        # Create a queue to get messages from the Discord receiver
        self.discord_receiver_queue = queue.Queue()
        self.stop_receiver_event = threading.Event()

        max_file_size = self.get_config("max_file_size")
        max_total_file_size = self.get_config("max_total_file_size")
        listen_to_channels = self.get_config("listen_to_channels")
        send_history_on_join = self.get_config("send_history_on_join")
        acknowledgement_message = self.get_config("acknowledgement_message")

        assert isinstance(max_file_size, int), "max_file_size must be an int"
        assert isinstance(max_total_file_size, int), "max_total_file_size must be an int"
        assert isinstance(listen_to_channels, bool), "listen_to_channels must be a bool"
        assert isinstance(send_history_on_join, bool), "send_history_on_join must be a bool"

        bot_intents = Intents.default()
        bot_intents.message_content = True

        self.app = Client(intents=bot_intents)
        self.discord_receiver = DiscordReceiver(
            app=self.app,
            discord_bot_token=self.discord_bot_token,
            input_queue=self.discord_receiver_queue,
            stop_event=self.stop_receiver_event,
            max_file_size=max_file_size,
            max_total_file_size=max_total_file_size,
            listen_to_channels=listen_to_channels,
            send_history_on_join=send_history_on_join,
            acknowledgement_message=acknowledgement_message,
        )
        self.discord_receiver.start()

    def stop_component(self):
        self.stop_discord_receiver()

    def stop_discord_receiver(self):
        self.stop_receiver_event.set()
        self.discord_receiver.join()

    def get_next_message(self):
        return self.discord_receiver_queue.get()

    def invoke(self, _message, data):
        return data


class DiscordReceiver(threading.Thread):
    def __init__(
        self,
        app: Client,
        discord_bot_token,
        input_queue,
        stop_event,
        max_file_size=20,
        max_total_file_size=20,
        listen_to_channels=False,
        send_history_on_join=False,
        acknowledgement_message=None,
    ):
        threading.Thread.__init__(self)
        self.app = app
        self.discord_bot_token = discord_bot_token
        self.input_queue = input_queue
        self.stop_event = stop_event
        self.max_file_size = max_file_size
        self.max_total_file_size = max_total_file_size
        self.listen_to_channels = listen_to_channels
        self.send_history_on_join = send_history_on_join
        self.acknowledgement_message = acknowledgement_message
        self.register_handlers()

    def run(self):
        self.app.run(self.discord_bot_token)
        self.stop_event.wait()

    async def handle_event(self, message: DiscordMessage):
        files = []
        total_file_size = 0

        for attachment in message.attachments:
            attachment_url = attachment.url
            attachment_name = attachment.filename
            size = attachment.size
            total_file_size += size
            if size > self.max_file_size * 1024 * 1024:
                log.warning(
                    "Attachment %s is too large to download. Skipping download.",
                    attachment_name,
                )
                continue
            if total_file_size > self.max_total_file_size * 1024 * 1024:
                log.warning(
                    "Total file size exceeds the maximum limit. Skipping download."
                )
                break
            b64_file = self.download_file_as_base64_string(attachment_url)
            files.append(
                {
                    "name": attachment_name,
                    "content": b64_file,
                    "mime_type": attachment.content_type,
                    "filetype": attachment.content_type,
                    "size": size,
                }
            )

        team_domain = message.guild.name if message.guild else message.author.name

        user_id = message.author.id
        text = message.clean_content

        is_thread = isinstance(message.channel, (Thread, DMChannel))

        if is_thread:
            thread_id = message.channel.id
        else:
            thread = await message.create_thread(name=trunc(message.clean_content, 20), auto_archive_duration=60)
            thread_id = thread.id

        payload = {
            "text": text,
            "files": files,
            "team_domain": team_domain,
            "client_msg_id": message.id,
            "ts": message.created_at.timestamp(),
            "channel": thread_id,
            "channel_name": message.author.name if isinstance(message.channel, (DMChannel, PartialMessageable)) else message.channel.name,
            "event_ts": message.created_at.timestamp(),
            "thread_ts": message.channel.created_at.timestamp() if is_thread and message.channel.created_at else message.created_at.timestamp(),
            "channel_type": str(message.channel.type),
            "user_id": user_id,
            "thread_id": thread_id,
            "reply_to_thread": thread_id,
        }
        user_properties = {
            "session_id": str(thread_id),
            "username": message.author.name,
            "client_msg_id": message.id,
            "ts": message.created_at.timestamp(),
            "thread_ts": message.channel.created_at.timestamp() if is_thread and message.channel.created_at else message.created_at.timestamp(),
            "channel": thread_id,
            "event_ts": message.created_at.timestamp(),
            "channel_type": str(message.channel.type),
            "user_id": user_id,
            "input_type": "discord",
            "thread_id": thread_id,
            "reply_to_thread": thread_id,
            "identity": user_id
        }

        solace_message = Message(payload=payload, user_properties=user_properties)
        solace_message.set_previous(payload)
        self.input_queue.put(solace_message)
        #Start a typing animation (lasts ten seconds)
        await message.channel.typing()

    def download_file_as_base64_string(self, file_url):
        headers = {"Authorization": "Bearer " + self.discord_bot_token}
        response = requests.get(file_url, headers=headers, timeout=10)
        base64_string = base64.b64encode(response.content).decode("utf-8")
        return base64_string

    async def get_channel_history(self, channel_id: int):
        pass # what's the point?
        '''
        channel = self.app.get_channel(channel_id)
        if not channel or not isinstance(channel, TextChannel):
            return []

        # First search through messages to get all their replies
        messages_to_add = []
        async for message in channel.history(limit=200):
            if "subtype" not in message and "text" in message:
                if "reply_count" in message:
                    # Get the replies
                    replies = self.app.get_channel(channel_id)
                    messages_to_add.extend(replies["messages"])

        response["messages"].extend(messages_to_add)

        # Go through the messages and remove any that have a sub_type
        messages = []
        for message in response["messages"]:
            if "subtype" not in message and "text" in message:
                payload = {
                    "text": message.get("text"),
                    "team_id": team_id,
                    "user_email": emails[message.get("user")],
                    "mentions": [],
                    "type": message.get("type"),
                    "client_msg_id": message.get("client_msg_id") or message.get("ts"),
                    "ts": message.get("ts"),
                    "event_ts": message.get("event_ts") or message.get("ts"),
                    "channel": channel_id,
                    "subtype": message.get("subtype"),
                    "user_id": message.get("user"),
                    "message_id": message.get("client_msg_id"),
                }
                messages.append(payload)

        return messages
    '''

    def register_handlers(self):
        @self.app.event
        async def on_message(message: DiscordMessage):
            if not self.app.user or message.author.bot:
                return

            if isinstance(message.channel, Thread) and isinstance(message.channel.parent, TextChannel):
                if "I am satisfied with my care" in message.content:
                  return await message.channel.delete()

                first_message = await message.channel.parent.fetch_message(message.channel.id)

                if first_message.author != message.author:
                    return
            elif not isinstance(message.channel, DMChannel) and not self.app.user.mentioned_in(message):
                return

            await self.handle_event(message)
