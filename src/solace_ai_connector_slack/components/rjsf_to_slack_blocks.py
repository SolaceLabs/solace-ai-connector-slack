"""
Module for converting RJSF (React JSON Schema Form) objects to Slack blocks.
"""

import json
import uuid


class RJSFToSlackBlocksConverter:
    """
    Converts RJSF objects to Slack blocks.
    """

    def __init__(self):
        """
        Initialize the converter.
        """
        pass

    def convert(self, user_form, task_id=None):
        """
        Convert a RJSF object to Slack blocks.

        Args:
            user_form (dict): A RJSF object containing schema, formData, and uiSchema.
            task_id (str, optional): The task ID to include in the submit button's value.

        Returns:
            list: A list of Slack blocks representing the form.
        """
        schema = user_form.get("schema", {})
        form_data = user_form.get("formData", {})
        ui_schema = user_form.get("uiSchema", {})

        blocks = []

        # Add title and description if present
        if "title" in schema:
            blocks.append({
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": schema["title"],
                    "emoji": True
                }
            })

        if "description" in schema:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": schema["description"]
                }
            })

        # Add a divider if we added a title or description
        if "title" in schema or "description" in schema:
            blocks.append({"type": "divider"})

        # Process properties
        properties = schema.get("properties", {})
        required_fields = schema.get("required", [])

        for field_name, field_schema in properties.items():
            field_blocks = self._convert_field(
                field_name, 
                field_schema, 
                form_data.get(field_name), 
                ui_schema.get(field_name, {}),
                field_name in required_fields
            )
            blocks.extend(field_blocks)

        # Add submit button
        blocks.append({"type": "divider"})
        blocks.append(self._create_submit_button(task_id))

        return blocks

    def _convert_field(self, field_name, field_schema, value, ui_schema, is_required):
        """
        Convert a field to Slack blocks based on its type.

        Args:
            field_name (str): The name of the field.
            field_schema (dict): The JSON schema for the field.
            value: The value of the field from formData.
            ui_schema (dict): The UI schema for the field.
            is_required (bool): Whether the field is required.

        Returns:
            list: A list of Slack blocks representing the field.
        """
        field_type = field_schema.get("type")
        
        # Handle enum fields specially
        if "enum" in field_schema:
            return self._convert_enum_field(field_name, field_schema, value, ui_schema, is_required)
        
        # Handle different field types
        if field_type == "string":
            return self._convert_string_field(field_name, field_schema, value, ui_schema, is_required)
        elif field_type in ["number", "integer"]:
            return self._convert_number_field(field_name, field_schema, value, ui_schema, is_required)
        elif field_type == "boolean":
            return self._convert_boolean_field(field_name, field_schema, value, ui_schema, is_required)
        elif field_type == "array":
            return self._convert_array_field(field_name, field_schema, value, ui_schema, is_required)
        elif field_type == "object":
            return self._convert_object_field(field_name, field_schema, value, ui_schema, is_required)
        else:
            # Default to string input for unknown types
            return self._convert_string_field(field_name, field_schema, value, ui_schema, is_required)

    def _convert_string_field(self, field_name, field_schema, value, ui_schema, is_required):
        """
        Convert a string field to Slack blocks.

        Args:
            field_name (str): The name of the field.
            field_schema (dict): The JSON schema for the field.
            value: The value of the field from formData.
            ui_schema (dict): The UI schema for the field.
            is_required (bool): Whether the field is required.

        Returns:
            list: A list of Slack blocks representing the string field.
        """
        blocks = []
        
        # Create a label for the field
        title = field_schema.get("title", field_name)
        if is_required:
            title = f"{title} *"
        # Check if we should use a textarea
        # Use textarea if specified in uiSchema or if the value is longer than 100 characters
        use_textarea_from_ui = ui_schema.get("ui:widget") == "textarea"
        is_long_text = value is not None and isinstance(value, str) and len(value) > 100
        
        is_textarea = use_textarea_from_ui or is_long_text
        
        # Create the input element
        block_id = f"input_{field_name}_{str(uuid.uuid4())[:8]}"
        
        input_block = {
            "type": "input",
            "block_id": block_id,
            "element": {
                "type": "plain_text_input",
                "action_id": f"action_{field_name}",
                "multiline": is_textarea
            },
            "label": {
                "type": "plain_text",
                "text": title,
                "emoji": True
            }
        }
        
        # Add placeholder if specified
        if "ui:placeholder" in ui_schema:
            input_block["element"]["placeholder"] = {
                "type": "plain_text",
                "text": ui_schema["ui:placeholder"]
            }
        
        # Add initial value if provided
        if value is not None:
            input_block["element"]["initial_value"] = str(value)
        
        blocks.append(input_block)
        
        return blocks

    def _convert_number_field(self, field_name, field_schema, value, ui_schema, is_required):
        """
        Convert a number/integer field to Slack blocks.

        Args:
            field_name (str): The name of the field.
            field_schema (dict): The JSON schema for the field.
            value: The value of the field from formData.
            ui_schema (dict): The UI schema for the field.
            is_required (bool): Whether the field is required.

        Returns:
            list: A list of Slack blocks representing the number field.
        """
        blocks = []
        
        # Create a label for the field
        title = field_schema.get("title", field_name)
        if is_required:
            title = f"{title} *"
        
        # Create the input element
        block_id = f"input_{field_name}_{str(uuid.uuid4())[:8]}"
        
        input_block = {
            "type": "input",
            "block_id": block_id,
            "element": {
                "type": "number_input",
                "action_id": f"action_{field_name}",
                "is_decimal_allowed": field_schema.get("type") == "number"
            },
            "label": {
                "type": "plain_text",
                "text": title,
                "emoji": True
            }
        }
        
        # Add min/max if specified
        if "minimum" in field_schema:
            input_block["element"]["min_value"] = field_schema["minimum"]
        
        if "maximum" in field_schema:
            input_block["element"]["max_value"] = field_schema["maximum"]
        
        # Add initial value if provided
        if value is not None:
            input_block["element"]["initial_value"] = str(value)
        
        blocks.append(input_block)
        
        return blocks

    def _convert_boolean_field(self, field_name, field_schema, value, ui_schema, is_required):
        """
        Convert a boolean field to Slack blocks.

        Args:
            field_name (str): The name of the field.
            field_schema (dict): The JSON schema for the field.
            value: The value of the field from formData.
            ui_schema (dict): The UI schema for the field.
            is_required (bool): Whether the field is required.

        Returns:
            list: A list of Slack blocks representing the boolean field.
        """
        blocks = []
        
        # Create a label for the field
        title = field_schema.get("title", field_name)
        if is_required:
            title = f"{title} *"
        
        # Create the checkbox element
        block_id = f"input_{field_name}_{str(uuid.uuid4())[:8]}"
        
        checkbox_block = {
            "type": "input",
            "block_id": block_id,
            "element": {
                "type": "checkboxes",
                "action_id": f"action_{field_name}",
                "options": [
                    {
                        "text": {
                            "type": "plain_text",
                            "text": title,
                            "emoji": True
                        },
                        "value": "true"
                    }
                ]
            },
            "label": {
                "type": "plain_text",
                "text": title,
                "emoji": True
            }
        }
        
        # Set initial value if provided
        if value is True:
            checkbox_block["element"]["initial_options"] = [
                {
                    "text": {
                        "type": "plain_text",
                        "text": title,
                        "emoji": True
                    },
                    "value": "true"
                }
            ]
        
        blocks.append(checkbox_block)
        
        return blocks

    def _convert_enum_field(self, field_name, field_schema, value, ui_schema, is_required):
        """
        Convert an enum field to Slack blocks.

        Args:
            field_name (str): The name of the field.
            field_schema (dict): The JSON schema for the field.
            value: The value of the field from formData.
            ui_schema (dict): The UI schema for the field.
            is_required (bool): Whether the field is required.

        Returns:
            list: A list of Slack blocks representing the enum field.
        """
        blocks = []
        
        # Create a label for the field
        title = field_schema.get("title", field_name)
        if is_required:
            title = f"{title} *"
        
        # Determine if we should use radio buttons or a dropdown
        use_radio = ui_schema.get("ui:widget") == "radio"
        
        # Get enum values and names
        enum_values = field_schema.get("enum", [])
        enum_names = field_schema.get("enumNames", enum_values)
        
        # Create the input element
        block_id = f"input_{field_name}_{str(uuid.uuid4())[:8]}"
        
        if use_radio:
            # Create radio buttons
            options = []
            for i, enum_value in enumerate(enum_values):
                enum_name = enum_names[i] if i < len(enum_names) else str(enum_value)
                options.append({
                    "text": {
                        "type": "plain_text",
                        "text": enum_name,
                        "emoji": True
                    },
                    "value": str(enum_value)
                })
            
            radio_block = {
                "type": "input",
                "block_id": block_id,
                "element": {
                    "type": "radio_buttons",
                    "action_id": f"action_{field_name}",
                    "options": options
                },
                "label": {
                    "type": "plain_text",
                    "text": title,
                    "emoji": True
                }
            }
            
            # Set initial value if provided
            if value is not None:
                for option in options:
                    if option["value"] == str(value):
                        radio_block["element"]["initial_option"] = option
                        break
            
            blocks.append(radio_block)
        else:
            # Create dropdown
            options = []
            for i, enum_value in enumerate(enum_values):
                enum_name = enum_names[i] if i < len(enum_names) else str(enum_value)
                options.append({
                    "text": {
                        "type": "plain_text",
                        "text": enum_name,
                        "emoji": True
                    },
                    "value": str(enum_value)
                })
            
            select_block = {
                "type": "input",
                "block_id": block_id,
                "element": {
                    "type": "static_select",
                    "action_id": f"action_{field_name}",
                    "options": options
                },
                "label": {
                    "type": "plain_text",
                    "text": title,
                    "emoji": True
                }
            }
            
            # Set initial value if provided
            if value is not None:
                for option in options:
                    if option["value"] == str(value):
                        select_block["element"]["initial_option"] = option
                        break
            
            blocks.append(select_block)
        
        return blocks

    def _convert_array_field(self, field_name, field_schema, value, ui_schema, is_required):
        """
        Convert an array field to Slack blocks.

        Args:
            field_name (str): The name of the field.
            field_schema (dict): The JSON schema for the field.
            value: The value of the field from formData.
            ui_schema (dict): The UI schema for the field.
            is_required (bool): Whether the field is required.

        Returns:
            list: A list of Slack blocks representing the array field.
        """
        blocks = []
        
        # Create a label for the field
        title = field_schema.get("title", field_name)
        if is_required:
            title = f"{title} *"
        
        # Create the multi-select element
        block_id = f"input_{field_name}_{str(uuid.uuid4())[:8]}"
        
        # Get items schema
        items_schema = field_schema.get("items", {})
        
        # If items have enum, create a multi-select with options
        if "enum" in items_schema:
            enum_values = items_schema.get("enum", [])
            enum_names = items_schema.get("enumNames", enum_values)
            
            options = []
            for i, enum_value in enumerate(enum_values):
                enum_name = enum_names[i] if i < len(enum_names) else str(enum_value)
                options.append({
                    "text": {
                        "type": "plain_text",
                        "text": enum_name,
                        "emoji": True
                    },
                    "value": str(enum_value)
                })
            
            multi_select_block = {
                "type": "input",
                "block_id": block_id,
                "element": {
                    "type": "multi_static_select",
                    "action_id": f"action_{field_name}",
                    "options": options
                },
                "label": {
                    "type": "plain_text",
                    "text": title,
                    "emoji": True
                }
            }
            
            # Set initial values if provided
            if value is not None and isinstance(value, list):
                initial_options = []
                for val in value:
                    for option in options:
                        if option["value"] == str(val):
                            initial_options.append(option)
                            break
                
                if initial_options:
                    multi_select_block["element"]["initial_options"] = initial_options
            
            blocks.append(multi_select_block)
        else:
            # For non-enum arrays, we'll use a plain text input and ask for comma-separated values
            input_block = {
                "type": "input",
                "block_id": block_id,
                "element": {
                    "type": "plain_text_input",
                    "action_id": f"action_{field_name}",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Enter comma-separated values"
                    }
                },
                "label": {
                    "type": "plain_text",
                    "text": title,
                    "emoji": True
                }
            }
            
            # Set initial value if provided
            if value is not None and isinstance(value, list):
                input_block["element"]["initial_value"] = ", ".join(str(v) for v in value)
            
            blocks.append(input_block)
        
        return blocks

    def _convert_object_field(self, field_name, field_schema, value, ui_schema, is_required):
        """
        Convert an object field to Slack blocks.

        Args:
            field_name (str): The name of the field.
            field_schema (dict): The JSON schema for the field.
            value: The value of the field from formData.
            ui_schema (dict): The UI schema for the field.
            is_required (bool): Whether the field is required.

        Returns:
            list: A list of Slack blocks representing the object field.
        """
        blocks = []
        
        # Create a label for the field
        title = field_schema.get("title", field_name)
        if is_required:
            title = f"{title} *"
        
        # For objects, we still need a header to group the nested fields
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{title}*"
            }
        })
        
        # Process properties of the object
        properties = field_schema.get("properties", {})
        required_fields = field_schema.get("required", [])
        
        if not value:
            value = {}
        
        for prop_name, prop_schema in properties.items():
            prop_blocks = self._convert_field(
                f"{field_name}.{prop_name}", 
                prop_schema, 
                value.get(prop_name), 
                ui_schema.get(prop_name, {}),
                prop_name in required_fields
            )
            blocks.extend(prop_blocks)
        
        return blocks

    def _create_submit_button(self, task_id=None):
        """
        Create a submit button block.

        Args:
            task_id (str, optional): The task ID to include in the button's value.

        Returns:
            dict: A Slack block representing the submit button.
        """
        # Create a value object that includes the task_id
        value = {
            "action": "submit_form"
        }
        if task_id:
            value["task_id"] = task_id
        return {
            "type": "actions",
            "block_id": f"submit_{str(uuid.uuid4())[:8]}",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Submit",
                        "emoji": True
                    },
                    "value": json.dumps(value),
                    "action_id": "submit_form"
                }
            ]
        }