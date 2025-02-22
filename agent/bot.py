# This is a basic agent that uses Mistral AI to help a user learn in a flashcard style.
# This agent is designed to be piped every single message in a Discord server.
# It will then call the on_message function.

from agent import StudyAgent # load our agent.py class

import logging # other imports
import platform
import os

from dotenv import load_dotenv # load environment variables
load_dotenv()

import discord
from discord.ext import commands
intents = discord.Intents.default() # enable access to all message content
intents.message_content = True

logger = logging.getLogger("discord") # log discord messages
logger.setLevel(logging.INFO)

PREFIX = "!"
CUSTOM_STATUS = "you not study"


class DiscordBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=commands.when_mentioned_or(PREFIX), intents=intents)
        self.logger = logger
        self.study_agent = StudyAgent()

    async def on_ready(self):
        self.logger.info("-------------------")
        self.logger.info(f"Logged in as {self.user}")
        self.logger.info(f"Discord.py API version: {discord.__version__}")
        self.logger.info(f"Python version: {platform.python_version()}")
        self.logger.info(f"Running on: {platform.system()} {platform.release()} ({os.name})")
        self.logger.info("-------------------")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching, name=CUSTOM_STATUS
            )
        )

    async def on_message(self, message: discord.Message):
        await self.process_commands(message)
        self.logger.info(f"Message from {message.author}: {message.content}")
        if (message.author == self.user or message.author.bot or message.content.startswith("!")): # ignore messages from self or bots
            return

        user_id = message.author.id
        content = message.content.strip()

        if user_id not in self.study_agent.sessions:
            term, response = self.study_agent.start_session(user_id, content)
            if not term:
                await message.channel.send(response)
                return
        else:
            term = self.study_agent.get_current_term(user_id)
            if not term:
                await message.channel.send("❌ No active study session. Please send a list of terms to start.")
                return
            
            await message.channel.send(self.study_agent.check_answer(term, content))
            term = self.study_agent.next_term(user_id)

        if term:
            intro = "✅ Got it! Next question:" if user_id in self.study_agent.sessions else response
            await message.channel.send(f"{intro}\nWhat does **'{term}'** mean?")
        else:
            await message.channel.send("🎉 Study session complete! Great job!")

if __name__ == "__main__":
    load_dotenv()
    token = os.getenv("DISCORD_TOKEN")

    bot = DiscordBot()
    bot.run(token)
