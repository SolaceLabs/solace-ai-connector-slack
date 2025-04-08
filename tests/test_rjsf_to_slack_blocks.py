"""
Test the RJSF to Slack blocks converter.
"""

import json
import sys
import os

# Add the src directory to the path so we can import the module
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.solace_ai_connector_slack.components.rjsf_to_slack_blocks import RJSFToSlackBlocksConverter


def test_plotly_graph_approval_form():
    """
    Test the converter with the Plotly Graph Approval form.
    """
    # Example user form from the requirements
    user_form = {
        "schema": {
            "type": "object",
            "title": "Plotly Graph Approval",
            "description": "Please approve the plotly graph generation.",
            "properties": {
                "decision": {
                    "type": "string",
                    "title": "Decision",
                    "enum": [
                        "approve",
                        "deny"
                    ],
                    "enumNames": [
                        "Approve",
                        "Deny"
                    ]
                },
                "comment": {
                    "type": "string",
                    "title": "Comment"
                },
                "long_text": {
                    "type": "string",
                    "title": "Long Text"
                },
                "plotly_definition": {
                    "type": "string",
                    "title": "Plotly Definition"
                }
            },
            "required": [
                "decision"
            ]
        },
        "formData": {
            "long_text": "This is a very long text that should automatically be rendered as a textarea because it exceeds 100 characters. Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.",
            "plotly_definition": "{\n\"data\": [\n{\n\"x\": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],\n\"y\": [2, 3, 5, 8, 11, 13, 16, 21, 26, 31],\n\"type\": \"scatter\",\n\"mode\": \"lines+markers\",\n\"name\": \"Series A\",\n\"line\": {\"color\": \"blue\"}\n},\n{\n\"x\": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],\n\"y\": [1, 4, 9, 16, 25, 36, 49, 64, 81, 100],\n\"type\": \"scatter\",\n\"mode\": \"lines+markers\",\n\"name\": \"Series B\",\n\"line\": {\"color\": \"red\"}\n}\n],\n\"layout\": {\n\"title\": \"Sample Line Chart\",\n\"xaxis\": {\"title\": \"X Axis\"},\n\"yaxis\": {\"title\": \"Y Axis\"},\n\"legend\": {\"orientation\": \"h\", \"y\": -0.2}\n}\n}"
        },
        "uiSchema": {
            "decision": {
                "ui:widget": "radio"
            },
            "comment": {
                "ui:widget": "textarea"
            }
        }
    }

    # Convert the form to Slack blocks
    converter = RJSFToSlackBlocksConverter()
    blocks = converter.convert(user_form)

    # Print the blocks as JSON for inspection
    print(json.dumps(blocks, indent=2))

    # Verify that the blocks contain the expected elements
    assert any(block.get("type") == "header" and block.get("text", {}).get("text") == "Plotly Graph Approval" for block in blocks)
    assert any(block.get("type") == "section" and "Please approve the plotly graph generation" in block.get("text", {}).get("text", "") for block in blocks)
    
    # Check for the long_text field (should be a textarea due to length)
    long_text_blocks = [block for block in blocks if block.get("type") == "input" and "Long Text" in block.get("label", {}).get("text", "")]
    assert len(long_text_blocks) > 0
    assert long_text_blocks[0]["element"]["type"] == "plain_text_input"
    assert long_text_blocks[0]["element"]["multiline"] is True
    assert "initial_value" in long_text_blocks[0]["element"]
    assert len(long_text_blocks[0]["element"]["initial_value"]) > 100
    
    # Check for the decision field (radio buttons)
    decision_blocks = [block for block in blocks if block.get("type") == "input" and "Decision" in block.get("label", {}).get("text", "")]
    assert len(decision_blocks) > 0
    assert decision_blocks[0]["element"]["type"] == "radio_buttons"
    
    # Check for the comment field (textarea)
    comment_blocks = [block for block in blocks if block.get("type") == "input" and "Comment" in block.get("label", {}).get("text", "")]
    assert len(comment_blocks) > 0
    assert comment_blocks[0]["element"]["type"] == "plain_text_input"
    assert comment_blocks[0]["element"]["multiline"] is True
    
    # Check for the plotly_definition field
    plotly_blocks = [block for block in blocks if block.get("type") == "input" and "Plotly Definition" in block.get("label", {}).get("text", "")]
    assert len(plotly_blocks) > 0
    assert plotly_blocks[0]["element"]["type"] == "plain_text_input"
    assert "initial_value" in plotly_blocks[0]["element"]
    
    # Check for the submit button
    submit_blocks = [block for block in blocks if block.get("type") == "actions"]
    assert len(submit_blocks) > 0
    assert any(element.get("type") == "button" and element.get("text", {}).get("text") == "Submit" for element in submit_blocks[0].get("elements", []))


def test_registration_form():
    """
    Test the converter with the Registration form.
    """
    # Example user form from the requirements
    user_form = {
        "schema": {
            "title": "A registration form",
            "description": "A simple form example.",
            "type": "object",
            "required": [
                "firstName",
                "lastName"
            ],
            "properties": {
                "firstName": {
                    "type": "string",
                    "title": "First name",
                    "default": "Chuck"
                },
                "lastName": {
                    "type": "string",
                    "title": "Last name"
                },
                "age": {
                    "type": "integer",
                    "title": "Age"
                },
                "bio": {
                    "type": "string",
                    "title": "Bio"
                },
                "password": {
                    "type": "string",
                    "title": "Password",
                    "minLength": 3
                },
                "telephone": {
                    "type": "string",
                    "title": "Telephone",
                    "minLength": 10
                }
            }
        },
        "formData": {
            "firstName": "Chuck",
            "lastName": "Norris",
            "age": 75,
            "bio": "Roundhouse kicking asses since 1940",
            "password": "noneed"
        },
        "uiSchema": {
            "firstName": {
                "ui:autofocus": True,
                "ui:emptyValue": "",
                "ui:placeholder": "ui:emptyValue causes this field to always be valid despite being required",
                "ui:autocomplete": "family-name",
                "ui:enableMarkdownInDescription": True,
                "ui:description": "Make text **bold** or *italic*. Take a look at other options [here](https://markdown-to-jsx.quantizor.dev/)."
            },
            "lastName": {
                "ui:autocomplete": "given-name",
                "ui:enableMarkdownInDescription": True,
                "ui:description": "Make things **bold** or *italic*. Embed snippets of `code`. <small>And this is a small texts.</small> "
            },
            "age": {
                "ui:widget": "updown",
                "ui:title": "Age of person",
                "ui:description": "(earth year)"
            },
            "bio": {
                "ui:widget": "textarea"
            },
            "password": {
                "ui:widget": "password",
                "ui:help": "Hint: Make it strong!"
            },
            "telephone": {
                "ui:options": {
                    "inputType": "tel"
                }
            }
        }
    }

    # Convert the form to Slack blocks
    converter = RJSFToSlackBlocksConverter()
    blocks = converter.convert(user_form)

    # Print the blocks as JSON for inspection
    print(json.dumps(blocks, indent=2))

    # Verify that the blocks contain the expected elements
    assert any(block.get("type") == "header" and block.get("text", {}).get("text") == "A registration form" for block in blocks)
    assert any(block.get("type") == "section" and "A simple form example" in block.get("text", {}).get("text", "") for block in blocks)
    
    # Check for the firstName field
    firstName_blocks = [block for block in blocks if block.get("type") == "input" and "First name" in block.get("label", {}).get("text", "")]
    assert len(firstName_blocks) > 0
    assert firstName_blocks[0]["element"]["type"] == "plain_text_input"
    assert firstName_blocks[0]["element"]["initial_value"] == "Chuck"
    
    # Check for the lastName field
    lastName_blocks = [block for block in blocks if block.get("type") == "input" and "Last name" in block.get("label", {}).get("text", "")]
    assert len(lastName_blocks) > 0
    assert lastName_blocks[0]["element"]["type"] == "plain_text_input"
    assert lastName_blocks[0]["element"]["initial_value"] == "Norris"
    
    # Check for the age field
    age_blocks = [block for block in blocks if block.get("type") == "input" and "Age" in block.get("label", {}).get("text", "")]
    assert len(age_blocks) > 0
    assert age_blocks[0]["element"]["type"] == "number_input"
    assert age_blocks[0]["element"]["initial_value"] == "75"
    
    # Check for the bio field (textarea)
    bio_blocks = [block for block in blocks if block.get("type") == "input" and "Bio" in block.get("label", {}).get("text", "")]
    assert len(bio_blocks) > 0
    assert bio_blocks[0]["element"]["type"] == "plain_text_input"
    assert bio_blocks[0]["element"]["multiline"] is True
    assert bio_blocks[0]["element"]["initial_value"] == "Roundhouse kicking asses since 1940"
    
    # Check for the password field
    password_blocks = [block for block in blocks if block.get("type") == "input" and "Password" in block.get("label", {}).get("text", "")]
    assert len(password_blocks) > 0
    assert password_blocks[0]["element"]["type"] == "plain_text_input"
    assert password_blocks[0]["element"]["initial_value"] == "noneed"
    
    # Check for the telephone field
    telephone_blocks = [block for block in blocks if block.get("type") == "input" and "Telephone" in block.get("label", {}).get("text", "")]
    assert len(telephone_blocks) > 0
    assert telephone_blocks[0]["element"]["type"] == "plain_text_input"
    
    # Check for the submit button
    submit_blocks = [block for block in blocks if block.get("type") == "actions"]
    assert len(submit_blocks) > 0
    assert any(element.get("type") == "button" and element.get("text", {}).get("text") == "Submit" for element in submit_blocks[0].get("elements", []))


if __name__ == "__main__":
    print("Testing Plotly Graph Approval Form:")
    test_plotly_graph_approval_form()
    
    print("\nTesting Registration Form:")
    test_registration_form()
    
    print("\nAll tests passed!")