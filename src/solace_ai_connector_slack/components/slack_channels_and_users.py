import os
from solace_ai_connector.common.log import log

class SlackChannelsAndUsers:
    def __init__(self):
        self.slack_app_token = os.environ.get('SLACK_APP_TOKEN')
        self.slack_bot_token = os.environ.get('SLACK_BOT_TOKEN')
        self.app = None
        
        if not self.slack_app_token or not self.slack_bot_token:
            raise ValueError("SLACK_APP_TOKEN and SLACK_BOT_TOKEN must be set in environment variables")
    
    def set_app(self, app):
        """Set the Slack app instance."""
        self.app = app
    
    def get_or_create_dm_channel(self, user_id):
        """
        Get or create a DM channel with a user.
        
        Args:
            user_id (str): The ID of the user.
            
        Returns:
            str: The ID of the DM channel, or None if creation failed.
        """
        if not self.app:
            log.error("Slack app not set. Call set_app() first.")
            return None
        
        try:
            # Open a DM conversation with the user
            response = self.app.client.conversations_open(users=[user_id])
            return response["channel"]["id"]
        except Exception as e:
            log.error(f"Failed to open DM conversation with user {user_id}: {str(e)}")
            return None
    
    def get_channel_name(self, channel_id):
        """
        Get the name of a channel.
        
        Args:
            channel_id (str): The ID of the channel.
            
        Returns:
            str: The name of the channel, or the channel ID if the name is not available.
        """
        if not self.app:
            log.error("Slack app not set. Call set_app() first.")
            return channel_id
        
        try:
            response = self.app.client.conversations_info(channel=channel_id)
            return response["channel"].get("name", channel_id)
        except Exception as e:
            log.error(f"Failed to get channel name for {channel_id}: {str(e)}")
            return channel_id