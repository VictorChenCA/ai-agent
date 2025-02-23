from mistralai import Mistral

import os
import random
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
        setup = True

        if not terms:
            return None, "⚠️ I couldn't extract any study terms. Please list them clearly."

        self.sessions[user_id] = {"terms": terms,
                                  "current_term": 0, "subject": subject, "setup": True}
        confirmation_message = self.generate_custom_confirmation(
            terms, subject)
        
        format_message = (
            "First, select your mode: \n"
            "Free Response: answer in your own words. \n"
            "Multiple Choice: choose from four given options. \n"
        )
        return f"{confirmation_message}\n{format_message}"

    def generate_custom_confirmation(self, terms, subject):
        subject_text = f"{subject}" if subject else ""
        return f"Sounds great! I'll help you quickly study these {subject_text} terms. Let's get started! \n"

    def extract_format(self, user_message):
        prompt = f"""
        Extract the study format from the following user message:
        {user_message}
        The format should be either "Free Response" or "Multiple Choice".
        Respond in JSON format:
        {{
        "format": "Free Response" or "Multiple Choice"
        }}
        """

        try:
            messages = [{"role": "user", "content": prompt}]
            response = self.mistral.chat.complete(
                model="mistral-tiny",
                messages=messages
            )
            extracted_data = response.choices[0].message.content.strip()
            return eval(extracted_data).get("format", "")
        except Exception as e:
            logger.error(f"Error extracting format: {str(e)}")
            return ""


    def set_study_format(self, user_id, user_message):
        extracted_format = self.extract_format(
            user_message)  # Extracts format from user message

        if user_id not in self.sessions or "setup" not in self.sessions[user_id]:
            return "⚠️ No active study session found. Please start a session first."

        if extracted_format not in ["Free Response", "Multiple Choice"]:
            return "⚠️ Invalid format. Please choose either 'Free Response' or 'Multiple Choice'."

        self.sessions[user_id]["format"] = extracted_format
        self.sessions[user_id]["setup"] = False

        return f"You have chosen the {extracted_format} format. Let's get started!"

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

    def generate_multiple_choice_question(self, term):
        question = f"What does '{term}' mean?"

        correct_answer = self.generate_correct_answer(term)
        distractors = self.generate_distractors(term)

        options = [correct_answer] + distractors
        random.shuffle(options)

        correct_index = options.index(correct_answer)

        return {
            "question": question,
            "options": options,
            "correct_answer": correct_index
        }

    def generate_correct_answer(self, term):
        prompt = f"Generate an incredibly succinct and short definition for the term '{term}'. Maximum 10 words."
        try:
            messages = [{"role": "user", "content": prompt}]
            response = self.mistral.chat.complete(
                model="mistral-tiny",
                messages=messages
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logging.error(f"Error generating correct answer: {str(e)}")
            return "Correct definition not available."

    def generate_distractors(self, term):
        prompt = f"Generate three incredibly succinct and short incorrect definitions for the term '{term}'. They should be plausible, but incorrect. Maximum 10 words each. Do not number each entry."
        try:
            messages = [{"role": "user", "content": prompt}]
            response = self.mistral.chat.complete(
                model="mistral-tiny",
                messages=messages
            )
            return response.choices[0].message.content.strip().split('\n')
        except Exception as e:
            logging.error(f"Error generating distractors: {str(e)}")
            # Fallback
            return ["Incorrect definition 1", "Incorrect definition 2", "Incorrect definition 3"]


    def check_answer(self, user_id, term, user_answer, mcq_questions=None, correct_index=None):
        session = self.sessions.get(user_id)

        if not session:
            return "⚠️ No active study session found."

        try:
            if session["format"] == "Multiple Choice" and mcq_questions:
                if user_answer.isdigit() and len(user_answer) == 1:
                    user_answer_text = mcq_questions[user_answer]
                else:
                    user_answer_text = user_answer 

                correct_answer = mcq_questions[correct_index] if correct_index is not None else mcq_questions[0]

                prompt = f"""
                You are an AI tutor. The user was asked:
                'What does {term} mean?'

                The user's answer: "{user_answer_text}"
                The correct answer is: "{correct_answer}"
                The other options are: {', '.join(mcq_questions)}

                Evaluate if the answer is correct. Respond with:
                - ✅ "Correct!" if the answer is mostly accurate.
                - ❌ "Incorrect" if it's wrong, followed by a brief explanation of why it's wrong. 
                """
            else:
                prompt = f"""
                You are an AI tutor. The user was asked:
                'What does {term} mean?'

                The user's answer: "{user_answer}"

                Evaluate if the answer is correct. Respond with:
                - ✅ "Correct!" if the answer is mostly accurate.
                - ❌ "Incorrect" if it's wrong, followed by a brief correction.
                """

            messages = [{"role": "user", "content": prompt}]
            response = self.mistral.chat.complete(
                model="mistral-tiny", messages=messages)
            return response.choices[0].message.content.strip()

        except Exception as e:
            logging.error(f"Error communicating with MistralAI: {str(e)}")
            return "⚠️ Error evaluating the response. Please try again."
