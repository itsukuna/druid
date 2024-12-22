from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import os
import logging

uri = os.getenv("mango_db")
client = MongoClient(uri, server_api=ServerApi("1"))

logger = logging.getLogger("mongodb")


class VoiceDB:
    def __init__(self):
        self.client = client
        self.db = self.client["tempvoice_db"]
        try:
            client.admin.command("ping")
            logger.info("Database connection was successful.")
        except Exception as e:
            logger.error(f"Database connection failed: {e}")

    def get_server_config(self, guild_id):
        try:
            return self.db.server_configs.find_one({"guild_id": guild_id})
        except Exception as e:
            logger.error(f"Error finding server config for guild {guild_id}: {e}")

    def set_server_config(self, guild_id, config_data):
        try:
            self.db.server_configs.update_one(
                {"guild_id": guild_id}, {"$set": config_data}, upsert=True
            )
            logger.info(f"Server config updated for guild {guild_id}")
        except Exception as e:
            logger.error(f"Error saving server config for guild {guild_id}: {e}")

    def remove_server_config(self, guild_id):
        try:
            self.db.server_configs.delete_one({"guild_id": guild_id})
            logger.info(f"Server config removed for guild {guild_id}")
        except Exception as e:
            logger.error(f"Error removing server config for guild {guild_id}: {e}")

    def add_temp_channel(self, guild_id, channel_id, owner_id):
        try:
            self.db.temp_channels.update_one(
                {"guild_id": guild_id},
                {
                    "$push": {
                        "channels": {"channel_id": channel_id, "owner_id": owner_id}
                    }
                },
                upsert=True,
            )
            logger.info(f"Temporary channel {channel_id} added for guild {guild_id}")
        except Exception as e:
            logger.error(
                f"Error adding temporary channel {channel_id} for guild {guild_id}: {e}"
            )

    def remove_temp_channel(self, guild_id, channel_id):
        try:
            self.db.temp_channels.update_one(
                {"guild_id": guild_id},
                {"$pull": {"channels": {"channel_id": channel_id}}},
                upsert=True,
            )
            logger.info(f"Temporary channel {channel_id} removed for guild {guild_id}")
        except Exception as e:
            logger.error(
                f"Error removing temporary channel {channel_id} for guild {guild_id}: {e}"
            )

    def get_temp_channels(self, guild_id):
        try:
            record = self.db.temp_channels.find_one({"guild_id": guild_id})
            logger.info(
                f"Temporary channels for guild {guild_id}: {record['channels'] if record else 'None'}"
            )
            return record["channels"] if record else []
        except Exception as e:
            logger.error(f"Error getting temporary channels for guild {guild_id}: {e}")
            return []

    def update_temp_channel_owner(self, guild_id, channel_id, new_owner_id):
        try:
            self.db.temp_channels.update_one(
                {"guild_id": guild_id, "channels.channel_id": channel_id},
                {"$set": {"channels.$.owner_id": new_owner_id}},
            )
            logger.info(
                f"Updated owner of temporary channel {channel_id} to {new_owner_id} for guild {guild_id}"
            )
        except Exception as e:
            logger.error(
                f"Error updating owner of temporary channel {channel_id} for guild {guild_id}: {e}"
            )
