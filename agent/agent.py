# This is a basic agent that uses Mistral AI to help a user learn in a flashcard style.
# This agent is designed to be piped every single message in a Discord server.
# First, the agent checks for a request to be quizzed on a term or terms in the message, and extracts it if it exists.
# This prevents the agent from responding to messages that don't request QuizAI's help.
# Then, a separate prompt chain is used to get definitions and responses from the user.

import os
import json
import logging
import discord

from mistralai import Mistral
from tools.weather import seven_day_forecast

logger = logging.getLogger("discord")

MISTRAL_MODEL = "mistral-large-latest"

EXTRACT_LOCATION_PROMPT = """
Is this message explicitly requesting help with understanding an academic term?
If not, return {"term": "none"}.

Otherwise, return the term in JSON format.

Example:
Message: What's a privative adjective???
Response: {"term": "privative adjective"}

Message: Dude I don't understand linear reg
Response: {"term": "linear regression"}
"""

EXTRACT_TERMS_PROMPT = """
Is this message clearly giving a list of terms or a paired list of terms and definitions?
If not, return {"placeholder": "none"}.

Otherwise, return the full name of the city in JSON format.

Example:
Message: privative typology, subsective typology, nonsubsective typology
Response: {"placeholder": "placeholder"}

Message: privative typology, subsective typology, nonsubsective typology
Response: {"placeholder": "placeholder"}

Message: I miss my ex girlfriend
Response: {"placeholder": "none"}

Message: I love linguistics
Response: {"placeholder": "none"}
"""


TOOLS_PROMPT = """
You are a patient study assistant designed to help students learn through interactive flashcards.

Your primary functions include:
   
- **Subject Mode:** Prompt user for a subject and/or specific topics, then choose related terms and definitions.
- **Notes Mode:** Accept user-provided notes, then choose terms and definitions from those notes.

- **Game Setting:** If enabled, introduce point-based system where users can pass levels with correct answers.
- **Adaptive Difficulty Setting** Adjusts the difficulty of questions based on user performance.

- **Multiple Choice Format** Instead of open-ended answers, allows users to choose from multiple-choice options.
- **Fill In The Blank Format** Presents definitions with missing words that users must fill in.
- **Free Response Format** Allow users to answer questions in one or more sentences. 

Engage users in a conversational manner to make learning feel natural and effective.
Encourage learning through repetition and interactive questioning.
Only use tools when necessary and focus on enhancing the study experience.
"""


class WeatherAgent:
    def __init__(self):
        MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

        self.client = Mistral(api_key=MISTRAL_API_KEY)
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "seven_day_forecast",
                    "description": "Get the seven day forecast for a given location with latitude and longitude.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "latitude": {"type": "string"},
                            "longitude": {"type": "string"},
                        },
                        "required": ["latitude", "longitude"],
                    },
                },
            }
        ]
        self.tools_to_functions = {
            "seven_day_forecast": seven_day_forecast,
        }

    async def extract_location(self, message: str) -> dict:
        # Extract the location from the message.
        response = await self.client.chat.complete_async(
            model=MISTRAL_MODEL,
            messages=[
                {"role": "system", "content": EXTRACT_LOCATION_PROMPT},
                {"role": "user", "content": f"Discord message: {message}\nOutput:"},
            ],
            response_format={"type": "json_object"},
        )

        message = response.choices[0].message.content

        obj = json.loads(message)
        if obj["location"] == "none":
            return None

        return obj["location"]

    async def get_weather_with_tools(self, location: str, request: str):
        messages = [
            {"role": "system", "content": TOOLS_PROMPT},
            {
                "role": "user",
                "content": f"Location: {location}\nRequest: {request}\nOutput:",
            },
        ]

        # Require the agent to use a tool with the "any" tool choice.
        tool_response = await self.client.chat.complete_async(
            model=MISTRAL_MODEL,
            messages=messages,
            tools=self.tools,
            tool_choice="any",
        )

        messages.append(tool_response.choices[0].message)

        tool_call = tool_response.choices[0].message.tool_calls[0]
        function_name = tool_call.function.name
        function_params = json.loads(tool_call.function.arguments)
        function_result = self.tools_to_functions[function_name](**function_params)

        # Append the tool call and its result to the messages.
        messages.append(
            {
                "role": "tool",
                "name": function_name,
                "content": function_result,
                "tool_call_id": tool_call.id,
            }
        )

        # Run the model again with the tool call and its result.
        response = await self.client.chat.complete_async(
            model=MISTRAL_MODEL,
            messages=messages,
        )

        return response.choices[0].message.content

    async def run(self, message: discord.Message):
        # Extract the location from the message to verify that the user is asking about weather in a specific location.
        location = await self.extract_location(message.content)
        if location is None:
            return None

        # Send a message to the user that we are fetching weather data.
        res_message = await message.reply(f"Fetching weather for {location}...")

        # Use a second prompt chain to get the weather data and response.
        weather_response = await self.get_weather_with_tools(location, message.content)

        # Edit the message to show the weather data.
        await res_message.edit(content=weather_response)
