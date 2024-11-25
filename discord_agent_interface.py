import asyncio
import discord
from discord.ext import commands
from typing import List, Dict, Any, Optional
import json
import async_timeout
from contextlib import asynccontextmanager
import time

def external(func):
    """Decorator to mark external interface functions"""
    func._external_tagged = True
    return func

def init(func):
    """Decorator to mark initialization functions"""
    return func

@asynccontextmanager
async def discord_connection(config_path: str):
    """Context manager to handle Discord connection lifecycle"""
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True
    intents.guild_messages = True
    
    bot = commands.Bot(command_prefix=config.get('prefix', '!'), intents=intents)
    
    try:
        # Start the bot in the background
        task = asyncio.create_task(bot.start(config['token']))
        
        # Wait for the bot to be ready
        ready = asyncio.Event()
        
        @bot.event
        async def on_ready():
            ready.set()
            
        # Wait for the ready event with a timeout
        try:
            async with async_timeout.timeout(30):
                await ready.wait()
        except asyncio.TimeoutError:
            raise RuntimeError("Bot failed to connect within timeout")
            
        yield bot, config
        
    finally:
        if not bot.is_closed():
            await bot.close()
        # Cancel the background task
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

@external
async def get_discord_channel_list() -> List[Dict[str, Any]]:
    r"""{
        "description": "Get a list of Discord channels that you have access to.",
        "returns": {
            "type": "List[Dict[str, Any]]",
            "description": "A list of dictionaries containing 'id' (int), 'name' (str), and 'type' (str) of each channel"
        }
    }"""
    async with discord_connection(discord_config) as (bot, config):
        guild = await bot.fetch_guild(config['guild_id'])
        
        async with async_timeout.timeout(10):
            channels = await guild.fetch_channels()
            allowed_channels = config.get('allowed_channels', [])
            
            result = [
                {'id': channel.id, 'name': channel.name, 'type': str(channel.type)}
                for channel in channels
                if channel.id in allowed_channels
            ]
            
            return result

@external
async def send_discord_message(channel_id: int, content: str) -> Optional[str]:
    r"""{
        "description": "Send a message to a Discord channel. Check the channel list before sending a message.",
        "args": [
            {"name": "channel_id", "type": "int", "description": "The ID of the channel to send the message to"},
            {"name": "content", "type": "str", "description": "The content of the message to send"}
        ],
        "returns": {
            "type": "Optional[str]",
            "description": "The ID of the message that was sent, or None if the message could not be sent"
        }
    }"""
    async with discord_connection(discord_config) as (bot, config):
        allowed_channels = config.get('allowed_channels', [])
        if channel_id not in allowed_channels:
            return None
            
        async with async_timeout.timeout(30):
            channel = await bot.fetch_channel(channel_id)
            message = await channel.send(content)
            return str(message.id)

#TODO: get_discord_message by message id so they can follow threads

@external
async def get_discord_message_history(channel_id: int, limit: int = 5) -> List[Dict[str, Any]]:
    r"""
    {
        "description": "Get the message history of a Discord channel. Check the history before you send a message.",
        "args": [
            {"name": "channel_id", "type": "int", "description": "The ID of the channel to get the message history from"},
            {"name": "limit", "type": "int", "description": "The maximum number of messages to retrieve (max 10, default 5)"}
        ],
        "returns": {
            "type": "str",
            "description": "well formatted list of messages"
        }
    }"""
    async with discord_connection(discord_config) as (bot, config):
        if limit > 20:
            limit = 20

        # TODO: limit by character count
        result = ""

        allowed_channels = config.get('allowed_channels', [])
        if channel_id not in allowed_channels:
            return "Channel not allowed, probably have the wrong channel id"            
            
        async with async_timeout.timeout(30):
            channel = await bot.fetch_channel(channel_id)
            messages = []

            async for message in channel.history(limit=limit, oldest_first=False):
                messages.append(message)

            messages.reverse()
            
            for message in messages:
                time_since_message = time.time() - message.created_at.timestamp()
                unit = "seconds"
                # convert it approriate time ago, like 10 seconds ago, 1 minute ago, 1 hour ago, 1 day ago
                if time_since_message > 60 and unit == "second(s)":
                    time_since_message /= 60
                    unit = "minutes"
                if time_since_message > 60 and unit == "minute(s)":
                    time_since_message /= 60
                    unit = "hours"
                if time_since_message > 24 and unit == "hour(s)":
                    time_since_message /= 24
                    unit = "days"
                if time_since_message > 365 and unit == "year(s)":
                    time_since_message /= 365
                    unit = "years"
                
                result += fr"<{message.author.name}> ({time_since_message:.0f} {unit} ago) [{message.id}]: {message.content}\n"

            print("~" * 100)
            print("~" * 100)
            print(result)
            print("~" * 100)
            return result
            

discord_config = ".discord_config"

# example usage:
async def main():
    global discord_config
    discord_config = "../.discord_config"
    print(await get_discord_channel_list())
    
if __name__ == '__main__':
    asyncio.run(main())