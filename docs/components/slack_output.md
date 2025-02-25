# SlackOutput

Slack output component. The component sends messages to Slack channels using the Bolt API.

## Configuration Parameters

```yaml
component_name: <user-supplied-name>
component_module: slack_output
component_config:
  slack_bot_token: <string>
  slack_app_token: <string>
  share_slack_connection: <string>
  correct_markdown_formatting: <boolean>
```

| Parameter | Required | Default | Description |
| --- | --- | --- | --- |
| slack_bot_token | False |  | The Slack bot token to connect to Slack. |
| slack_app_token | False |  | The Slack app token to connect to Slack. |
| share_slack_connection | False |  | Share the Slack connection with other components in this instance. |
| correct_markdown_formatting | False | true | Correct markdown formatting in messages to conform to Slack markdown. |


## Component Input Schema

```
{
  message_info:   {
    channel:     <string>,
    type:     <string>,
    user_email:     <string>,
    client_msg_id:     <string>,
    ts:     <string>,
    subtype:     <string>,
    event_ts:     <string>,
    channel_type:     <string>,
    user_id:     <string>,
    session_id:     <string>
  },
  content:   {
    text:     <string>,
    files: [
      {
        name:         <string>,
        content:         <string>,
        mime_type:         <string>,
        filetype:         <string>,
        size:         <number>
      },
      ...
    ]
  }
}
```
| Field | Required | Description |
| --- | --- | --- |
| message_info | True |  |
| message_info.channel | True |  |
| message_info.type | False |  |
| message_info.user_email | False |  |
| message_info.client_msg_id | False |  |
| message_info.ts | False |  |
| message_info.subtype | False |  |
| message_info.event_ts | False |  |
| message_info.channel_type | False |  |
| message_info.user_id | False |  |
| message_info.session_id | True |  |
| content | True |  |
| content.text | False |  |
| content.files | False |  |
| content.files[].name | False |  |
| content.files[].content | False |  |
| content.files[].mime_type | False |  |
| content.files[].filetype | False |  |
| content.files[].size | False |  |
