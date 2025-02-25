"""Base class for all Slack components"""

from abc import ABC, abstractmethod
import json
import requests

from slack_bolt import App  # pylint: disable=import-error
from solace_ai_connector.components.component_base import ComponentBase


class SlackBase(ComponentBase, ABC):
    _slack_apps = {}

    def __init__(self, module_info, **kwargs):
        super().__init__(module_info, **kwargs)
        self.slack_bot_token = self.get_config("slack_bot_token")
        self.slack_app_token = self.get_config("slack_app_token")
        self.max_file_size = self.get_config("max_file_size", 20)
        self.max_total_file_size = self.get_config("max_total_file_size", 20)
        self.share_slack_connection = self.get_config("share_slack_connection")
        self.feedback_enabled = self.get_config("feedback", False)
        self.feedback_post_url = self.get_config("feedback_post_url", None)
        self.feedback_post_headers = self.get_config("feedback_post_headers", {})

        if self.share_slack_connection:
            if self.slack_bot_token not in SlackBase._slack_apps:
                self.app = App(token=self.slack_bot_token)
                SlackBase._slack_apps[self.slack_bot_token] = self.app
            else:
                self.app = SlackBase._slack_apps[self.slack_bot_token]
        else:
            self.app = App(token=self.slack_bot_token)

    @abstractmethod
    def invoke(self, message, data):
        pass

    def __str__(self):
        return self.__class__.__name__ + " " + str(self.config)

    def __repr__(self):
        return self.__str__()
    
    def register_action_handlers(self):
        @self.app.action("thumbs_up_action")
        def handle_thumbs_up(ack, body, say):
            self.thumbs_up_down_feedback_handler(ack, body, "thumbs_up")

        @self.app.action("thumbs_down_action")
        def handle_thumbs_down(ack, body, say):
            self.thumbs_up_down_feedback_handler(ack, body, "thumbs_down")

        @self.app.action("feedback_text_reason")
        def handle_feedback_input(ack, body, say):
            self.feedback_reason_handler(ack, body)

    def feedback_reason_handler(self, ack, body):
        # Acknowledge the action request
        ack()
        
        # This is a bit of a hack but slack leaves us no choice.
        # The block_id is a stringified JSON object that contains the channel, thread_ts and feedback.
        block_id = body['actions'][0]['block_id']
        value_object = json.loads(block_id)
        channel = value_object.get("channel", None)
        thread_ts = value_object.get("thread_ts", None)
        user_id = body['user']['id']
        feedback = value_object.get("feedback", "thumbs_down")
        
        # Get the input text from the input block
        feedback_reason = (body
            .get("state", {})
            .get("values", {})
            .get(block_id, {})
            .get("feedback_text_reason", {})
            .get("value", None)
        )

        # Get the previous message in the thread with the block_id
        prev_message_ts = self._find_previous_message(thread_ts, channel, block_id)

        thanks_message_block = SlackBase._create_feedback_thanks_block(user_id, feedback)
        if prev_message_ts is None:
            # We couldn't find the previous message
            # Just add a new message with a thank you message
            self.app.client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                text="Thanks!",
                blocks=[thanks_message_block]
            )
        else:
            # Overwrite the previous message with a thank you message
            self.app.client.chat_update(
                channel=channel,
                ts=prev_message_ts,
                text="Thanks",  # Fallback text
                blocks=[thanks_message_block]
            )

        self._send_feedback_rest_post(body, feedback, feedback_reason, value_object.get("feedback_data", "no feedback provided"))       


    def thumbs_up_down_feedback_handler(self, ack, body, feedback):
        # Acknowledge the action request
        ack()

        # Check if feedback is enabled and the feedback post URL is set
        if not self.feedback_enabled or not self.feedback_post_url:
            self.logger.error("Feedback is not enabled or feedback post URL is not set.")
            return
        
        # Respond to the action
        value_object = json.loads(body['actions'][0]['value'])
        feedback_data = value_object.get("feedback_data", {})
        channel = value_object.get("channel", None)
        thread_ts = value_object.get("thread_ts", None)
        user_id = body['user']['id']
        
        block_id = feedback_data.get("block_id", "thumbs_up_down")

        # Remove the block_id from the feedback_data if it exists
        # For negative feedback, the feedback_data becomes the block_id
        # and it gets too big if we also include the previous block_id
        feedback_data.pop("block_id", None)

        # We want to find the previous message in the thread that has the thumbs_up_down block
        # and then overwrite it
        prev_message_ts = self._find_previous_message(thread_ts, channel, block_id)

        if prev_message_ts is None:
            # We couldn't find the previous message
            # Just add a new message with a thank you message
            thanks_block = SlackBase._create_feedback_thanks_block(user_id, feedback)
            self.app.client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                text="Thanks!",
                blocks=[thanks_block]
            )
        else:

            # If it's a thumbs up, we just thank them but if it's a thumbs down, we ask for a reason
            if feedback == "thumbs_up":
                next_block = SlackBase._create_feedback_thanks_block(user_id, feedback)

            else:
                value_object["feedback"] = feedback
                next_block = SlackBase._create_feedback_reason_block(value_object)

            self.app.client.chat_update(
                channel=channel,
                ts=prev_message_ts,
                text="Thanks!",
                blocks=[next_block]
            )

        if feedback == "thumbs_up" or prev_message_ts is None:
            self._send_feedback_rest_post(body, feedback, None, feedback_data)

    def _find_previous_message(self, thread_ts, channel, block_id):
        """Find a previous message in a Slack conversation or thread based on a block_id.
        This method searches through the recent message history of a Slack conversation or thread
        to find a message containing a block with a specific block_id.
        Args:
            thread_ts (str, optional): The timestamp of the thread. If None, searches in main channel history.
            channel (str): The ID of the Slack channel to search in.
            block_id (str): The block ID to search for within messages.
        Returns:
            str or None: The timestamp (ts) of the message containing the specified block_id,
                        or None if no matching message is found.
        Example:
            message_ts = find_previous_message('1234567890.123456', 'C0123ABCD', 'thumbs_up_down')
        """
        if thread_ts is None:
            # Get the history of the conversation
            response = self.app.client.conversations_history(
                channel=channel,
                latest=thread_ts,
                limit=100,
                inclusive=True
            )
        else:
            # We're in a thread, get the replies
            response = self.app.client.conversations_replies(
                channel=channel,
                ts=thread_ts,
                limit=100,
            )

        messages = response.get("messages", None)
        blocks = None
        message_ts = None

        # loop over the messages until we find the message with a block id of thumbs_up_down
        for message in messages:
            blocks = message.get("blocks", [])
            for block in blocks:
                if block.get("block_id", None) == block_id:
                    message_ts = message.get("ts", None)
                    break
        
        return message_ts

    def _send_feedback_rest_post(self, body, feedback, feedback_reason, feedback_data):
        rest_body = {
            "user": body['user'],
            "feedback": feedback,
            "interface": "slack",
            "interface_data": {
                "channel": body['channel']
            },
            "data": feedback_data
        }

        if feedback_reason:
            rest_body["feedback_reason"] = feedback_reason

        try:
            requests.post(
                url=self.feedback_post_url,
                headers=self.feedback_post_headers,
                data=json.dumps(rest_body)
            )
        except Exception as e:
            self.logger.error(f"Failed to post feedback: {str(e)}")

    @staticmethod
    def _create_feedback_thanks_block(user_id, feedback):
        message = SlackBase._create_feedback_message(feedback)
        return {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"{message}, <@{user_id}>!",
                    }
                }
    
    @staticmethod
    def _create_feedback_message(feedback):
        if feedback == "thumbs_up":
            message = f"Thanks for the thumbs up"
        else:
            message = f"Thanks for the feedback"
        return message
    
    @staticmethod
    def _create_feedback_reason_block(feedback_data):
        return {
                "type": "input",

                # This is a bit of a hack but slack leaves us no choice.
                # The block_id is a stringified JSON object that contains # the feedback specific data. We need this state in the
                # action handler to respond to the user.
                "block_id": json.dumps(feedback_data),
                "dispatch_action": True,
                "label": {
                    "type": "plain_text",
                    "text": " "
                },
                "element": {
                    "type": "plain_text_input",
                    "action_id": "feedback_text_reason",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "How can we improve the response?"
                    },
                    "dispatch_action_config": {
                    "trigger_actions_on": ["on_enter_pressed"]
                    }
                }
            }
