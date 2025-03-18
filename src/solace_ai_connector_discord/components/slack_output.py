import base64
import re
import json
from datetime import datetime

from prettytable import PrettyTable

from solace_ai_connector.common.log import log
from .slack_base import SlackBase


info = {
    "class_name": "SlackOutput",
    "description": (
        "Slack output component. The component sends messages to Slack channels using the Bolt API."
    ),
    "config_parameters": [
        {
            "name": "slack_bot_token",
            "type": "string",
            "description": "The Slack bot token to connect to Slack.",
        },
        {
            "name": "slack_app_token",
            "type": "string",
            "description": "The Slack app token to connect to Slack.",
        },
        {
            "name": "share_slack_connection",
            "type": "string",
            "description": "Share the Slack connection with other components in this instance.",
        },
        {
            "name": "correct_markdown_formatting",
            "type": "boolean",
            "description": "Correct markdown formatting in messages to conform to Slack markdown.",
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
                    "type": {
                        "type": "string",
                    },
                    "user_email": {
                        "type": "string",
                    },
                    "client_msg_id": {
                        "type": "string",
                    },
                    "ts": {
                        "type": "string",
                    },
                    "subtype": {
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


class SlackOutput(SlackBase):
    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
        self.fix_formatting = self.get_config("correct_markdown_formatting", True)
        self.streaming_state = {}
        self.register_action_handlers()

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
            log.error("slack_output: No channel specified in message")
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

            for index, text in enumerate(messages):
                if not text or not isinstance(text, str):
                    continue

                if self.fix_formatting:
                    text = self.fix_markdown(text)

                if index != 0:
                    text = "\n" + text

                if first_chunk:
                    streaming_state = self.add_streaming_state(uuid)
                else:
                    streaming_state = self.get_streaming_state(uuid)
                    if not streaming_state:
                        streaming_state = self.add_streaming_state(uuid)

                if streaming:
                    if streaming_state.get("completed"):
                        # We can sometimes get a message after the stream has completed
                        continue

                    streaming_state["completed"] = last_chunk
                    ts = streaming_state.get("ts")
                    if status_update:
                        blocks = [
                            {
                                "type": "context",
                                "elements": [
                                    {
                                        "type": "mrkdwn",
                                        "text": text,
                                    }
                                ],
                            },
                        ]

                        if not ts:
                            ts = ack_msg_ts
                        try:
                            self.app.client.chat_update(
                                channel=channel, ts=ts, text="test", blocks=blocks
                            )
                        except Exception:
                            pass
                    elif ts:
                        try:
                            self.app.client.chat_update(
                                channel=channel, ts=ts, text=text
                            )
                        except Exception:
                            # It is normal to possibly get an update after the final
                            # message has already arrived and deleted the ack message
                            pass
                    else:
                        response = self.app.client.chat_postMessage(
                            channel=channel, text=text, thread_ts=reply_to
                        )
                        streaming_state["ts"] = response["ts"]

                else:
                    # Not streaming
                    ts = streaming_state.get("ts")
                    streaming_state["completed"] = True
                    if not ts:
                        self.app.client.chat_postMessage(
                            channel=channel, text=text, thread_ts=reply_to
                        )

            for file in files:
                file_content = base64.b64decode(file["content"])
                self.app.client.files_upload_v2(
                    channel=channel,
                    file=file_content,
                    thread_ts=reply_to,
                    filename=file["name"],
                )

            if streaming and response_complete and self.feedback_enabled:
                blocks = self.create_feedback_blocks(feedback_data, channel, reply_to)
                response = self.app.client.chat_postMessage(
                    channel=channel, text="feedback", thread_ts=reply_to, blocks=blocks
                )


        except Exception as e:
            log.error("Error sending slack message: %s", e)

        super().send_message(message)

    def fix_markdown(self, message):
        # Fix links - the LLM is very stubborn about giving markdown links
        # Find [text](http...) and replace with <http...|text>
        message = re.sub(r"\[(.*?)\]\((http.*?)\)", r"<\2|\1>", message)
        # Remove the language specifier from code blocks
        message = re.sub(r"```[a-z]+\n", "```", message)
        # Fix bold
        message = re.sub(r"\*\*(.*?)\*\*", r"*\1*", message)

        # Reformat a table to be Slack compatible
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

    @staticmethod
    def create_feedback_blocks(value_object, channel, thread_ts):
        feedback_data = {
            "channel": channel,
            "thread_ts": thread_ts,
            "feedback_data": value_object
        }

        # Create a unique id for the feedback block_id (max 8 characters)
        block_id = "thumbs_up_down" + str(hash(str(feedback_data)))[-8:]
        feedback_data["feedback_data"]["block_id"] = block_id

        return [
            {
                "type": "actions",
                "block_id": block_id,
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "emoji": True,
                            "text": "👍"
                        },
                        "value": json.dumps(feedback_data),
                        "action_id": "thumbs_up_action"
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "emoji": True,
                            "text": "👎"
                        },
                        "value": json.dumps(feedback_data),
                        "action_id": "thumbs_down_action"
                    }
                ],
            }
        ]
