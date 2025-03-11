# This is a basic agent that uses Mistral AI to help a user learn in a flashcard style.
# This agent is designed to be piped every single message in a Discord server.
# It will then call the on_message function.

from agent import StudyAgent # load our agent.py class

import logging # other imports
import platform
import os
import aiohttp

from dotenv import load_dotenv # load environment variables
load_dotenv()

import discord
from discord.ext import commands
intents = discord.Intents.default() # enable access to all message content
intents.message_content = True

logger = logging.getLogger("discord") # log discord messages
logger.setLevel(logging.INFO)

PREFIX = "!"
CUSTOM_STATUS = "you learn | @QuizAI"

# Globals
pending_extractions = {}
bot = commands.Bot(command_prefix='!', intents=intents)
ctx = None

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
        global ctx
        ctx = await bot.get_context(message)
        await self.process_commands(message)
        self.logger.info(f"Message from {message.author}: {message.content}")

        # Ignore messages from self, bots, or commands
        if message.author == self.user or message.author.bot:
            return

        # Handle @QuizAI mention
        if self.user.mentioned_in(message):
            await self.show_help(self, ctx)
            return

        user_id = message.author.id
        content = message.content.strip()

        # **Handle PDF Uploads**
        if message.attachments:
            for attachment in message.attachments:
                if attachment.filename.lower().endswith(".pdf"):
                    await ctx.send(
                        f"📄 I detected a PDF file: `{attachment.filename}`. Would you like me to extract study terms from it? Reply with `yes` or `no`."
                    )

                    file_path = f"./temp/{attachment.filename}"
                    os.makedirs("./temp", exist_ok=True)

                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.get(attachment.url) as resp:
                                if resp.status == 200:
                                    with open(file_path, "wb") as f:
                                        f.write(await resp.read())

                        if not os.path.exists(file_path):
                            logger.error(f"❌ File was not saved correctly: {file_path}")
                            await ctx.send("❌ Error saving file. Please try again.")
                            return

                        logger.info(f"✅ PDF successfully saved at: {file_path}")

                    except Exception as e:
                        logger.error(f"❌ Error downloading file: {e}")
                        await ctx.send("❌ Error downloading file. Please try again.")
                        return

                    pending_extractions[user_id] = file_path
                    return 
                else:
                    await ctx.send("❌ Sorry, I only support PDF files for study term extraction.")
                    return


        # **Handle PDF Processing Confirmation**
        if user_id in pending_extractions and content.lower() in ["yes", "y"]:
            pdf_path = pending_extractions.pop(user_id)
            await ctx.send("🔍 Extracting study terms from your document... Please wait.")
            logger.info(f"🔍 Calling process_pdf() with path: {pdf_path}")
            extracted_text = self.study_agent.process_pdf(pdf_path)

            if extracted_text.startswith("⚠") or extracted_text.startswith("❌"):
                await ctx.send(extracted_text)
                return

            self.study_agent.sessions[user_id] = {
                "extracted_text": extracted_text,
                "awaiting_question_count": True
            }
            
            await ctx.send("✅ Extraction complete! How many questions would you like to study? (Enter a number)")
            return

        elif user_id in pending_extractions and content.lower() in ["no", "n"]:
            pending_extractions.pop(user_id)
            await ctx.send("❌ PDF processing canceled.")
            return

        if "awaiting_question_count" in self.study_agent.sessions.get(user_id, {}):
            try:
                num_questions = int(content)
                if num_questions <= 0:
                    await ctx.send("⚠ Please enter a positive number.")
                    return
                    
                session = self.study_agent.sessions[user_id]
                session["num_questions"] = num_questions
                extracted_text = session.pop("extracted_text")
                del session["awaiting_question_count"]
                
                terms = self.study_agent.extract_study_terms(user_id, extracted_text)
                response = self.study_agent.start_session(user_id, "") # Reuse existing flow
                await ctx.send(response)
                return
            except ValueError:
                await ctx.send("⚠ Please enter a valid number.")
                return

        # **New Study Session Handling**
        if user_id not in self.study_agent.sessions:
            self.logger.info(f"Starting study session for user {user_id}")
            response = self.study_agent.start_session(user_id, content)
            await ctx.send(response)
            return

        session = self.study_agent.sessions[user_id]

        # **Handle Study Format Selection**
        if session.get("setup"):
            self.logger.info(f"Setting mode for user {user_id}")
            response = self.study_agent.set_study_format(user_id, content)
            await ctx.send(response)

            if "format" in session:
                cur_term = self.study_agent.get_current_term(user_id)
                if cur_term:
                    if session["format"] == "Multiple Choice":
                        mcq_data = self.study_agent.generate_multiple_choice_question(cur_term)
                        session["mcq_options"] = mcq_data["options"]
                        session["correct_answer"] = mcq_data["correct_answer"]
                        formatted_options = "\n".join(
                            [f"{i + 1}. {option}" for i, option in enumerate(session["mcq_options"])]
                        )

                        await ctx.send(f"**First question:**\n{mcq_data['question']}")
                        await ctx.send(f"**Options:**\n{formatted_options}")

                    elif session["format"] == "Fill-in-the-Blank":
                        question = self.study_agent.generate_fill_in_the_blank_question(cur_term)
                        await ctx.send(f"\nFirst question:\n{question}")
                    else:
                        await ctx.send(f"\nFirst question:\n")
                        await ctx.send(f">>> What does **'{cur_term}'** mean?")
            return

        # **Handle Answer Checking and Next Question**
        term = self.study_agent.get_current_term(user_id)
        mcq_options = session.get("mcq_options") if session["format"] == "Multiple Choice" else None
        correct_index = session.get("correct_answer") if session["format"] == "Multiple Choice" else None
        response = self.study_agent.check_answer(user_id, term, content, mcq_options, correct_index)
        await ctx.send(response)

        next_term = self.study_agent.next_term(user_id)
        if next_term:
            if session["format"] == "Multiple Choice":
                mcq_data = self.study_agent.generate_multiple_choice_question(next_term)
                session["mcq_options"] = mcq_data["options"]
                session["correct_answer"] = mcq_data["correct_answer"]
                formatted_options = "\n".join(
                    [f"{i + 1}. {option}" for i, option in enumerate(session["mcq_options"])]
                )

                await ctx.send(f">>> **Next question:**\n{mcq_data['question']}")
                await ctx.send(f">>> **Options:**\n{formatted_options}")
            elif session["format"] == "Fill-in-the-Blank":
                question = self.study_agent.generate_fill_in_the_blank_question(next_term)
                await ctx.send(f">>> **Next question:**\n{question}")
            else:
                await ctx.send(f"\nNext question:\n")
                await ctx.send(f">>> What does **'{next_term}'** mean?")
        else:
            await ctx.send("\n🎉 Study session complete! Great job!")

    @commands.command(name="help")
    async def show_help(self, ctx):
        help_message = (
            ">>> **QuizAI Help Guide**\n"
            "I can help you study using flashcards in various formats!\n\n"
            "Commands:\n"
            "`@QuizAI` - Show this help message.\n\n"
            "To start a study session, simply send any message with the terms you want to study (comma separated).\n"
            "You can also upload a PDF file, and I will extract study terms from it.\n\n"
            "After starting a session, you can choose the study format:\n"
            "- Free Response\n"
            "- Multiple Choice\n"
            "- Fill-in-the-Blank\n"
        )
        await ctx.send(help_message)

if __name__ == "__main__":
    DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
    if DISCORD_TOKEN:
        bot = DiscordBot()
        bot.run(DISCORD_TOKEN)
    else:
        logger.error("DISCORD_TOKEN not set.")
