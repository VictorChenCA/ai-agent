from mistralai import Mistral

import os
from dotenv import load_dotenv
load_dotenv()

import logging
import colorlog
logger = logging.getLogger("agent")  # log agent messages
logger.setLevel(logging.ERROR)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = colorlog.ColoredFormatter(
    "%(asctime)s %(log_color)s%(levelname)-8s%(reset)s %(yellow)s%(name)s %(white)s%(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    log_colors={
        "DEBUG": "cyan",
        "INFO": "blue",
        "WARNING": "yellow",
        "ERROR": "red",
        "CRITICAL": "bold_red",
    },
    style="%",
)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)



MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
MISTRAL_MODEL = "mistral-large-latest"


class StudyAgent:

    def __init__(self):
        self.sessions = {}
        self.mistral = Mistral(api_key=MISTRAL_API_KEY)

    def extract_terms_and_subject(self, user_message):
        prompt = f"""
        Extract the study terms and subject from the following user message:
        {user_message}
        Respond in JSON format:
        {{
          "terms": ["term1", "term2", ...],
          "subject": "subject name"
        }}
        """

        try:
            messages = [{"role": "user", "content": prompt}]
            response = self.mistral.chat.complete(
                model="mistral-tiny",
                messages=messages
            )
            extracted_data = response.choices[0].message.content.strip()
            return eval(extracted_data)  # Convert JSON string to dict
        except Exception as e:
            logger.error(f"Error extracting terms and subject: {str(e)}")
            return {"terms": [], "subject": ""}

    def start_session(self, user_id, user_message):
        extracted = self.extract_terms_and_subject(user_message)
        terms = extracted.get("terms", [])
        subject = extracted.get("subject", "")

        if not terms:
            return None, "⚠️ I couldn't extract any study terms. Please list them clearly."

        self.sessions[user_id] = {"terms": terms,
                                  "current_term": 0, "subject": subject}
        confirmation_message = self.generate_custom_confirmation(
            terms, subject)
        return terms[0], confirmation_message

    def generate_custom_confirmation(self, terms, subject):
        subject_text = f"for {subject} " if subject else ""
        return f"Sounds great! I'll help you quickly study these {subject_text}terms. Let's get started."

    def get_current_term(self, user_id):
        session = self.sessions.get(user_id)
        return session["terms"][session["current_term"]] if session else None

    def next_term(self, user_id):
        session = self.sessions.get(user_id)
        if not session:
            return None

        session["current_term"] += 1
        if session["current_term"] >= len(session["terms"]):
            del self.sessions[user_id]
            return None
        return session["terms"][session["current_term"]]

    def check_answer(self, term, user_answer):
        prompt = f"""
        You are an AI tutor. The user was asked:
        'What does {term} mean?'
        
        The user's answer: "{user_answer}"
        
        Evaluate if the answer is correct. Respond with:
        - ✅ "Correct!" if the answer is mostly accurate. Correct any minor mistakes. Be succinct.
        - ❌ "Incorrect" if it's wrong, followed by a brief correction.
        """

        try:
            messages = [{"role": "user", "content": prompt}]
            response = self.mistral.chat.complete(
                model="mistral-tiny",
                messages=messages
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            self.logger.error(f"Error communicating with MistralAI: {str(e)}")
            return "⚠️ Error evaluating the response. Please try again."
