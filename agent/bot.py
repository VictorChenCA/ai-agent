import os
import discord
import logging
import platform

from discord.ext import commands
from agent import StudyAgent
from dotenv import load_dotenv

load_dotenv()
intents = discord.Intents.default()
intents.message_content = True  # Enable message content intent

logger = logging.getLogger("discord")

PREFIX = "!"

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
        self.logger.info("-------------------")

    async def on_message(self, message):
        if message.author == self.user:
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
    DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
    if DISCORD_TOKEN:
        bot = DiscordBot()
        bot.run(DISCORD_TOKEN)
    else:
        logger.error("DISCORD_TOKEN not set.")
