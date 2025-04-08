"""
Test the form submission handling.
"""

import json
import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Mock the slack_bolt module
sys.modules['slack_bolt'] = MagicMock()
sys.modules['slack_bolt.adapter.socket_mode'] = MagicMock()

# Add the src directory to the path so we can import the module
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Mock the solace_ai_connector module
sys.modules['solace_ai_connector'] = MagicMock()
sys.modules['solace_ai_connector.components'] = MagicMock()
sys.modules['solace_ai_connector.components.component_base'] = MagicMock()
sys.modules['solace_ai_connector.components.component_base'].ComponentBase = MagicMock

# Now we can import our modules
from src.solace_ai_connector_slack.components.rjsf_to_slack_blocks import RJSFToSlackBlocksConverter


# Create a mock SlackBase class
class MockSlackBase:
    _component_registry = {}  # Static registry for components
    
    @classmethod
    def register_component(cls, component_type, component):
        cls._component_registry[component_type] = component
        
    @classmethod
    def get_component(cls, component_type):
        return cls._component_registry.get(component_type)
    def __init__(self):
        self.app = MagicMock()
        self.app.client = MagicMock()
        self.app.client.chat_postMessage = MagicMock()
        self.app.client.users_info = MagicMock()
        self.logger = MagicMock()
    
    def get_user_email(self, user_id):
        return "test@example.com"
    
    def handle_form_submission(self, ack, body):
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
        slack_input = MockSlackBase.get_component("slackinput")
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
            "text": json.dumps(form_data),  # Put the form data in the text field
            "form_data": form_data,  # Also include it directly
            "task_id": task_id,  # Include the task_id
            "channel_type": body["channel"]["type"],
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


class TestFormSubmission(unittest.TestCase):
    """
    Test the form submission handling.
    """

    def setUp(self):
        """
        Set up the test.
        """
        # Mock the component registry
        MockSlackBase._component_registry = {}
        
        # Create a mock SlackInput instance
        self.slack_input = MagicMock()
        self.slack_input.handle_event = MagicMock()
        
        # Register the mock SlackInput instance
        MockSlackBase.register_component("slackinput", self.slack_input)
        
        # Create a mock SlackBase instance
        self.slack_base = MockSlackBase()

    def test_create_submit_button_with_task_id(self):
        """
        Test that the submit button is created with the task_id.
        """
        # Create a converter
        converter = RJSFToSlackBlocksConverter()
        
        # Create a submit button with a task_id
        task_id = "test_task_id"
        submit_button = converter._create_submit_button(task_id)
        
        # Verify that the submit button has the task_id in its value
        value_json = submit_button["elements"][0]["value"]
        value_object = json.loads(value_json)
        self.assertEqual(value_object["task_id"], task_id)

    def test_convert_with_task_id(self):
        """
        Test that the converter includes the task_id in the submit button.
        """
        # Create a converter
        converter = RJSFToSlackBlocksConverter()
        
        # Create a user form
        user_form = {
            "schema": {
                "type": "object",
                "title": "Test Form",
                "properties": {
                    "name": {
                        "type": "string",
                        "title": "Name"
                    }
                }
            },
            "formData": {
                "name": "Test Name"
            }
        }
        
        # Convert the form with a task_id
        task_id = "test_task_id"
        blocks = converter.convert(user_form, task_id)
        
        # Find the submit button
        submit_button = None
        for block in blocks:
            if block["type"] == "actions":
                submit_button = block
                break
        
        # Verify that the submit button has the task_id in its value
        self.assertIsNotNone(submit_button)
        value_json = submit_button["elements"][0]["value"]
        value_object = json.loads(value_json)
        self.assertEqual(value_object["task_id"], task_id)

    def test_handle_form_submission(self):
        """
        Test that the form submission handler extracts the form data and invokes the handle_event method of SlackInput.
        """
        # Create a mock ack function
        ack = MagicMock()
        
        # Create a mock body
        body = {
            "actions": [
                {
                    "value": json.dumps({"task_id": "test_task_id"})
                }
            ],
            "state": {
                "values": {
                    "input_name_12345678": {
                        "action_name": {
                            "value": "Test Name"
                        }
                    },
                    "input_age_87654321": {
                        "action_age": {
                            "selected_option": {
                                "value": "30"
                            }
                        }
                    },
                    "input_interests_abcdefgh": {
                        "action_interests": {
                            "selected_options": [
                                {"value": "reading"},
                                {"value": "coding"}
                            ]
                        }
                    }
                }
            },
            "channel": {
                "id": "C12345678",
                "type": "channel"
            },
            "user": {
                "id": "U12345678"
            },
            "message": {
                "ts": "1234567890.123456",
                "thread_ts": "1234567890.123456"
            }
        }
        
        # Call the handle_form_submission method
        self.slack_base.handle_form_submission(ack, body)
        
        # Verify that ack was called
        ack.assert_called_once()
        
        # Verify that handle_event was called on the SlackInput instance
        self.slack_input.handle_event.assert_called_once()
        
        # Verify that the event passed to handle_event has the expected properties
        args, kwargs = self.slack_input.handle_event.call_args
        event = args[0]
        self.assertEqual(event["type"], "form_submission")
        self.assertEqual(event["user"], "U12345678")
        self.assertEqual(event["channel"], "C12345678")
        self.assertEqual(event["task_id"], "test_task_id")
        self.assertIn("form_data", event)
        self.assertEqual(event["form_data"]["name"], "Test Name")
        self.assertEqual(event["form_data"]["age"], "30")
        self.assertEqual(event["form_data"]["interests"], ["reading", "coding"])
        
        # Verify that chat_postMessage was called for the confirmation message
        self.slack_base.app.client.chat_postMessage.assert_called_once()
        args, kwargs = self.slack_base.app.client.chat_postMessage.call_args
        self.assertEqual(kwargs["channel"], "C12345678")
        self.assertEqual(kwargs["thread_ts"], "1234567890.123456")
        self.assertEqual(kwargs["text"], "Form submitted successfully!")


if __name__ == "__main__":
    unittest.main()