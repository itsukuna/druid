from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import os
import logging

uri = os.getenv("mongodb_uri")
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

    def add_banned_user(self, guild_id, channel_id, user_id):
        self.db.banned_users.update_one(
            {"guild_id": guild_id},
            {
                "$addToSet": {
                    f"channels.{channel_id}.banned_users": user_id
                }
            },
            upsert=True 
        )
        logger.info(f"Added banned user {user_id} to guild {guild_id}, channel {channel_id}")
    
    def remove_banned_user(self, guild_id, channel_id, user_id):
        self.db.banned_users.update_one(
            {"guild_id": guild_id, "channel_id": channel_id},
            {"$pull": {"banned_users": user_id}}
        )

    def get_banned_users(self, guild_id, channel_id):
        """Gets a list of banned user IDs for a specific voice channel."""
        result = self.db.banned_users.find_one(
            {"guild_id": guild_id, "channel_id": channel_id},
            {"banned_users": 1, "_id": 0}
        )
        return result.get("banned_users", []) if result else []


class AutoModDB:
    def __init__(self):
        self.client = client
        self.db = self.client["automod_db"]

    def add_bad_word(self, guild_id, word):
        try:
            self.db.bad_words.update_one(
                {"guild_id": guild_id},
                {"$addToSet": {"words": word}},
                upsert=True,
            )
            logger.info(f"Added bad word '{word}' for guild {guild_id}")
        except Exception as e:
            logger.error(f"Error adding bad word '{word}' for guild {guild_id}: {e}")

    def remove_bad_word(self, guild_id, word):
        try:
            self.db.bad_words.update_one(
                {"guild_id": guild_id},
                {"$pull": {"words": word}},
                upsert=True,
            )
            logger.info(f"Removed bad word '{word}' for guild {guild_id}")
        except Exception as e:
            logger.error(f"Error removing bad word '{word}' for guild {guild_id}: {e}")

    def get_bad_words(self, guild_id):
        try:
            record = self.db.bad_words.find_one({"guild_id": guild_id})
            logger.info(
                f"Bad words for guild {guild_id}: {record['words'] if record else 'None'}"
            )
            return record["words"] if record else []
        except Exception as e:
            logger.error(f"Error getting bad words for guild {guild_id}: {e}")
            return []


class LevelDB:
    def __init__(self):
        self.client = client
        self.db = self.client["xp_db"]

    def add_xp(self, guild_id, user_id, xp):
        try:
            self.db.xp.update_one(
                {"guild_id": guild_id, "user_id": user_id},
                {"$inc": {"xp": xp}, "$setOnInsert": {"level": 0}},
                upsert=True,
            )
            logger.info(f"Added {xp} XP for user {user_id} in guild {guild_id}")
        except Exception as e:
            logger.error(f"Error adding XP for user {user_id} in guild {guild_id}: {e}")

    def get_xp(self, guild_id, user_id):
        try:
            record = self.db.xp.find_one({"guild_id": guild_id, "user_id": user_id})
            return record["xp"] if record else 0
        except Exception as e:
            logger.error(f"Error getting XP for user {user_id} in guild {guild_id}: {e}")
            return 0

    def get_level(self, guild_id, user_id):
        try:
            record = self.db.xp.find_one({"guild_id": guild_id, "user_id": user_id})
            return record["level"] if record else 0
        except Exception as e:
            logger.error(f"Error getting level for user {user_id} in guild {guild_id}: {e}")
            return 0

    def set_level(self, guild_id, user_id, level):
        try:
            self.db.xp.update_one(
                {"guild_id": guild_id, "user_id": user_id},
                {"$set": {"level": level}},
                upsert=True,
            )
            logger.info(f"Set level {level} for user {user_id} in guild {guild_id}")
        except Exception as e:
            logger.error(f"Error setting level for user {user_id} in guild {guild_id}: {e}")

    def get_leaderboard(self, guild_id):
        try:
            return list(self.db.xp.find({"guild_id": guild_id}).sort("xp", -1).limit(10))
        except Exception as e:
            logger.error(f"Error getting leaderboard for guild {guild_id}: {e}")
            return []
