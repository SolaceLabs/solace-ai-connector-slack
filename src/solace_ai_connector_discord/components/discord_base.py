"""Base class for all Discord components"""

from abc import ABC, abstractmethod
import json
import os
import requests

from discord import Intents, Client, Interaction, Message, ChannelType, ButtonStyle, InteractionType
from discord.ui import Button, View
from solace_ai_connector.components.component_base import ComponentBase


class DiscordBase(ComponentBase, ABC):
    _discord_apps = {}

    def __init__(self, module_info, **kwargs):
        super().__init__(module_info, **kwargs)
        self.discord_bot_token = self.get_config("discord_bot_token")
        self.max_file_size = self.get_config("max_file_size", 20)
        self.max_total_file_size = self.get_config("max_total_file_size", 20)
        self.feedback_enabled = self.get_config("feedback", False)
        self.feedback_post_url = self.get_config("feedback_post_url", None)
        self.feedback_post_headers = self.get_config("feedback_post_headers", {})
        self.app = Client(intents=Intents.default())
        
        # Here are some buttons that the discord bot should be able to use
        self.thumbs_up_button = Button(label="👍", style=ButtonStyle.green)
        self.thumbs_down_button = Button(label="👎", style=ButtonStyle.red)
        self.thumbs_up_button.callback = self.thumbsup_callback
        self.thumbs_down_button.callback = self.thumbsdown_callback
        self.view = View()
        self.view.add_item(self.thumbs_up_button)
        self.view.add_item(self.thumbs_down_button)
        
        #We should run the register action handlers function (temporary, this will be called by DiscordOutput)
        self.register_action_handlers()

    def run(self):
        self.app.run(os.getenv('DISCORD_TOKEN') or exit(-123))

    @abstractmethod
    def invoke(self, message, data):
        pass

    def __str__(self):
        return self.__class__.__name__ + " " + str(self.config)

    def __repr__(self):
        return self.__str__()
    
    def register_action_handlers(self):
        """
            _summary_ : Register the action handlers for the Discord bot
            
        """
        @self.app.event
        async def on_ready():
            print(f'We have logged in as {self.app.user}')

        @self.app.event
        async def on_message(message: Message):
            if message.author != self.app.user:
                return
            if  not self.app.user.mentioned_in(message):
                return
            for attachment in message.attachments:
                attachment.url

            if message.channel.type in [ChannelType.public_thread, ChannelType.private_thread]:
                await message.reply("hello world", view=self.view)
            else:
                thread = await message.create_thread(name="solly")
                await thread.send("hello world", view=self.view)


        @self.app.event
        async def on_reaction_add(reaction, user):
            if user != self.app.user:
                if reaction.emoji == '👍':
                    await self.thumbs_up_callback(reaction)
                elif reaction.emoji == '👎':
                    await self.thumbs_down_callback(reaction)
                else:
                    await reaction.message.channel.send(f'{user.name} reacted with {reaction.emoji}')

    
    async def thumbs_up_callback(self, interaction: Interaction):
        await interaction.response.send_message("You clicked thumbs up!", ephemeral=True)

    async def thumbs_down_callback(self, interaction: Interaction):
        await interaction.response.send_message("You clicked thumbs down!", ephemeral=True)

    def thumbs_up_down_feedback_handler(self, body, feedback):
            # # Acknowledge the action request
            # ack()

            # # Check if feedback is enabled and the feedback post URL is set
            # if not self.feedback_enabled or not self.feedback_post_url:
            #     self.logger.error("Feedback is not enabled or feedback post URL is not set.")
            #     return
            
            # # Respond to the action
            # value_object = json.loads(body['actions'][0]['value'])
            # feedback_data = value_object.get("feedback_data", {})
            # channel = value_object.get("channel", None)
            # thread_ts = value_object.get("thread_ts", None)
            # user_id = body['user']['id']
            
            # block_id = feedback_data.get("block_id", "thumbs_up_down")

            # # Remove the block_id from the feedback_data if it exists
            # # For negative feedback, the feedback_data becomes the block_id
            # # and it gets too big if we also include the previous block_id
            # feedback_data.pop("block_id", None)

            # # We want to find the previous message in the thread that has the thumbs_up_down block
            # # and then overwrite it
            # prev_message_ts = self._find_previous_message(thread_ts, channel, block_id)

            # if prev_message_ts is None:
            #     # We couldn't find the previous message
            #     # Just add a new message with a thank you message
            #     thanks_block = DiscordBase._create_feedback_thanks_block(user_id, feedback)
            #     self.app.client.chat_postMessage(
            #         channel=channel,
            #         thread_ts=thread_ts,
            #         text="Thanks!",
            #         blocks=[thanks_block]
            #     )
            # else:

            #     # If it's a thumbs up, we just thank them but if it's a thumbs down, we ask for a reason
            #     if feedback == "thumbs_up":
            #         next_block = DiscordBase._create_feedback_thanks_block(user_id, feedback)

            #     else:
            #         value_object["feedback"] = feedback
            #         next_block = DiscordBase._create_feedback_reason_block(value_object)

            #     self.app.client.chat_update(
            #         channel=channel,
            #         ts=prev_message_ts,
            #         text="Thanks!",
            #         blocks=[next_block]
            #     )

            # if feedback == "thumbs_up" or prev_message_ts is None:
            #     self._send_feedback_rest_post(body, feedback, None, feedback_data)
            pass


    # def feedback_reason_handler(self, ack, body):
    #     # Acknowledge the action request
    #     ack()
        
    #     # This is a bit of a hack but discord leaves us no choice.
    #     # The block_id is a stringified JSON object that contains the channel, thread_ts and feedback.
    #     block_id = body['actions'][0]['block_id']
    #     value_object = json.loads(block_id)
    #     channel = value_object.get("channel", None)
    #     thread_ts = value_object.get("thread_ts", None)
    #     user_id = body['user']['id']
    #     feedback = value_object.get("feedback", "thumbs_down")
        
    #     # Get the input text from the input block
    #     feedback_reason = (body
    #         .get("state", {})
    #         .get("values", {})
    #         .get(block_id, {})
    #         .get("feedback_text_reason", {})
    #         .get("value", None)
    #     )

    #     # Get the previous message in the thread with the block_id
    #     prev_message_ts = self._find_previous_message(thread_ts, channel, block_id)

    #     thanks_message_block = DiscordBase._create_feedback_thanks_block(user_id, feedback)
    #     if prev_message_ts is None:
    #         # We couldn't find the previous message
    #         # Just add a new message with a thank you message
    #         self.app.client.chat_postMessage(
    #             channel=channel,
    #             thread_ts=thread_ts,
    #             text="Thanks!",
    #             blocks=[thanks_message_block]
    #         )
    #     else:
    #         # Overwrite the previous message with a thank you message
    #         self.app.client.chat_update(
    #             channel=channel,
    #             ts=prev_message_ts,
    #             text="Thanks",  # Fallback text
    #             blocks=[thanks_message_block]
    #         )

    #     self._send_feedback_rest_post(body, feedback, feedback_reason, value_object.get("feedback_data", "no feedback provided"))       
    pass


    
    def _find_previous_message(self, thread_ts, channel, block_id):
        # """Find a previous message in a Discord conversation or thread based on a block_id.
        # This method searches through the recent message history of a Discord conversation or thread
        # to find a message containing a block with a specific block_id.
        # Args:
        #     thread_ts (str, optional): The timestamp of the thread. If None, searches in main channel history.
        #     channel (str): The ID of the Discord channel to search in.
        #     block_id (str): The block ID to search for within messages.
        # Returns:
        #     str or None: The timestamp (ts) of the message containing the specified block_id,
        #                 or None if no matching message is found.
        # Example:
        #     message_ts = find_previous_message('1234567890.123456', 'C0123ABCD', 'thumbs_up_down')
        # """
        # if thread_ts is None:
        #     # Get the history of the conversation
        #     response = self.app.client.conversations_history(
        #         channel=channel,
        #         latest=thread_ts,
        #         limit=100,
        #         inclusive=True
        #     )
        # else:
        #     # We're in a thread, get the replies
        #     response = self.app.client.conversations_replies(
        #         channel=channel,
        #         ts=thread_ts,
        #         limit=100,
        #     )

        # messages = response.get("messages", None)
        # blocks = None
        # message_ts = None

        # # loop over the messages until we find the message with a block id of thumbs_up_down
        # for message in messages:
        #     blocks = message.get("blocks", [])
        #     for block in blocks:
        #         if block.get("block_id", None) == block_id:
        #             message_ts = message.get("ts", None)
        #             break
        
        # return message_ts
        pass

    def _send_feedback_rest_post(self, body, feedback, feedback_reason, feedback_data):
        # rest_body = {
        #     "user": body['user'],
        #     "feedback": feedback,
        #     "interface": "discord",
        #     "interface_data": {
        #         "channel": body['channel']
        #     },
        #     "data": feedback_data
        # }

        # if feedback_reason:
        #     rest_body["feedback_reason"] = feedback_reason

        # try:
        #     requests.post(
        #         url=self.feedback_post_url,
        #         headers=self.feedback_post_headers,
        #         data=json.dumps(rest_body)
        #     )
        # except Exception as e:
        #     self.logger.error(f"Failed to post feedback: {str(e)}")
        pass

    @staticmethod
    def _create_feedback_thanks_block(user_id, feedback):
        message = DiscordBase._create_feedback_message(feedback)
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

                # This is a bit of a hack but discord leaves us no choice.
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
