"""Base class for all Slack components"""

from abc import ABC, abstractmethod
import json
import requests

from slack_bolt import App  # pylint: disable=import-error
from solace_ai_connector.components.component_base import ComponentBase


class SlackBase(ComponentBase, ABC):
    _slack_apps = {}
    _component_registry = {}  # Static registry for components
    _channels_and_users = None  # Static instance of SlackChannelsAndUsers
    
    @classmethod
    def get_channels_and_users(cls):
        """
        Get the shared SlackChannelsAndUsers instance.
        
        Returns:
            SlackChannelsAndUsers: The shared instance.
        """
        if cls._channels_and_users is None:
            from .slack_channels_and_users import SlackChannelsAndUsers
            cls._channels_and_users = SlackChannelsAndUsers()
        return cls._channels_and_users

    @classmethod
    def register_component(cls, component_type, component):
        """
        Register a component in the registry.
        
        Args:
            component_type (str): The type of the component (e.g., "input", "output").
            component: The component instance.
        """
        cls._component_registry[component_type] = component

    @classmethod
    def get_component(cls, component_type):
        """
        Get a component from the registry.
        
        Args:
            component_type (str): The type of the component (e.g., "input", "output").
            
        Returns:
            The component instance, or None if not found.
        """
        return cls._component_registry.get(component_type)

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
            
        # Set the app in the channels and users instance
        channels_and_users = self.get_channels_and_users()
        channels_and_users.set_app(self.app)
            
        # Register this component in the registry
        component_type = self.__class__.__name__.lower()
        SlackBase.register_component(component_type, self)

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
            
        @self.app.action("submit_form")
        def handle_submit_form(ack, body, say):
            self.handle_form_submission(ack, body)

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
            
    def handle_form_submission(self, ack, body):
        """
        Handle form submissions.
        
        Args:
            ack: Function to acknowledge the action.
            body: The action payload.
        """
        # Acknowledge the action request
        ack()
        
        # Extract the value from the button
        value_json = body['actions'][0]['value']
        try:
            value_object = json.loads(value_json)
            task_id = value_object.get("task_id")
        except json.JSONDecodeError:
            self.logger.error("Failed to parse submit button value as JSON")
            return
        
        if not task_id:
            self.logger.error("No task_id found in submit button value")
            return
        
        # Extract form data from the submission
        form_data = {}
        state_values = body.get("state", {}).get("values", {})
        for block_id, block_values in state_values.items():
            for action_id, action_value in block_values.items():
                # Extract the field name from the action_id (e.g., "action_firstName" -> "firstName")
                if action_id.startswith("action_"):
                    field_name = action_id[len("action_"):]
                    
                    # Handle different types of inputs
                    if "value" in action_value:
                        # Plain text input
                        form_data[field_name] = action_value["value"]
                    elif "selected_option" in action_value:
                        # Radio buttons or select
                        form_data[field_name] = action_value["selected_option"]["value"]
                    elif "selected_options" in action_value:
                        # Checkboxes or multi-select
                        form_data[field_name] = [option["value"] for option in action_value["selected_options"]]
        
        # Create a new message with the form data
        channel = body["channel"]["id"]
        user_id = body["user"]["id"]
        thread_ts = body["message"].get("thread_ts")
        
        # Get user email
        user_email = self.get_user_email(user_id)
        # Find the SlackInput instance
        slack_input = SlackBase.get_component("slackinput")
        if not slack_input:
            self.logger.error("Could not find SlackInput instance")
            return
        
        # Create an event that mimics a message event
        event = {
            "type": "form_submission",
            "user": user_id,
            "channel": channel,
            "ts": body["message"]["ts"],
            "thread_ts": thread_ts,
            "text": json.dumps(form_data), # Put the form data in the text field
            "event_type": "post_user_form",
            "form_data": form_data,  # Also include it directly
            "task_id": task_id,  # Include the task_id
            "channel_type": body.get("channel_type") or (
                body.get("channel", {}).get("type", "unknown") if isinstance(body.get("channel"), dict) else "unknown"
            ),
            "user_email": user_email,
        }
        
        # Invoke the handle_event method of SlackInput
        slack_input.handle_event(event)
        
        # Optionally, send a confirmation message to the user
        self.app.client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            text="Form submitted successfully!"
        )
        
    def get_user_email(self, user_id):
        """
        Get the email of a user.
        
        Args:
            user_id (str): The ID of the user.
            
        Returns:
            str: The email of the user, or the user ID if the email is not available.
        """
        try:
            response = self.app.client.users_info(user=user_id)
            return response["user"]["profile"].get("email", user_id)
        except Exception as e:
            self.logger.error(f"Failed to get user email: {str(e)}")
            return user_id
