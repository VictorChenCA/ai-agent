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

        # ignore messages from self or bots
        if message.author == self.user or message.author.bot or message.content.startswith("!"):
            return

        user_id = message.author.id
        content = message.content.strip()

        # new session
        if user_id not in self.study_agent.sessions:
            self.logger.info(f"Starting study session for user {user_id}")
            response = self.study_agent.start_session(user_id, content)
            await message.channel.send(response)
            return

        session = self.study_agent.sessions[user_id]


        # set mode
        if session.get("setup"):
            self.logger.info(f"Setting mode for user {user_id}")
            response = self.study_agent.set_study_format(user_id, content)
            await message.channel.send(response)

            # first question
            cur_term = self.study_agent.get_current_term(user_id)
            if cur_term:
               if session["format"] == "Multiple Choice":
                mcq_data = self.study_agent.generate_multiple_choice_question(
                    cur_term)
                session["mcq_options"] = mcq_data["options"]
                formatted_options = "\n".join(
                    [f"{i + 1}. {option}" for i,
                        option in enumerate(session["mcq_options"])]
                )

                await message.channel.send(f"**Next question:**\n{mcq_data['question']}")
                await message.channel.send(f"**Options:**\n{formatted_options}")
            else:
                await message.channel.send(f"\nNext question:\nWhat does **'{cur_term}'** mean?")
            return

        # rest of the questions
        term = self.study_agent.get_current_term(user_id)
        mcq_options = session.get(
            "mcq_options") if session["format"] == "Multiple Choice" else None

        response = self.study_agent.check_answer(user_id, term, content, mcq_options)
        await message.channel.send(response)

        next_term = self.study_agent.next_term(user_id)
        if next_term:
            if session["format"] == "Multiple Choice":
                mcq_data = self.study_agent.generate_multiple_choice_question(
                    next_term)
                session["mcq_options"] = mcq_data["options"]
                formatted_options = "\n".join(
                    [f"{i + 1}. {option}" for i,
                        option in enumerate(session["mcq_options"])]
                )

                await message.channel.send(f"**Next question:**\n{mcq_data['question']}")
                await message.channel.send(f"**Options:**\n{formatted_options}")
            else:
                await message.channel.send(f"\nNext question:\nWhat does **'{next_term}'** mean?")
        else:
            await message.channel.send("\n🎉 Study session complete! Great job!")

if __name__ == "__main__":
    DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
    if DISCORD_TOKEN:
        bot = DiscordBot()
        bot.run(DISCORD_TOKEN)
    else:
        logger.error("DISCORD_TOKEN not set.")
