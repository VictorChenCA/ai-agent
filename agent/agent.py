import pdfplumber
import colorlog
import logging
from mistralai import Mistral

import os
import random
from dotenv import load_dotenv
load_dotenv()

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

    def start_session(self, user_id, user_message, subject=None):
        if user_id in self.sessions and "terms" in self.sessions[user_id]:
            session = self.sessions[user_id]
            terms = session["terms"]
            subject = session.get("subject", "")
        else:
            if subject:
                terms = self.generate_terms_from_subject(subject)
                if not terms:
                    return "⚠️ I couldn't generate any study terms for the given subject."
                self.sessions[user_id] = {
                    "terms": terms, "current_term": 0, "subject": subject}
            else:
                extracted = self.extract_terms_and_subject(user_message)
                terms = extracted.get("terms", [])
                subject = extracted.get("subject", "")
                if not terms:
                    return "⚠️ I couldn't extract any study terms. Please list them clearly."

                self.sessions[user_id] = {
                    "terms": terms, "current_term": 0, "subject": subject}

        self.sessions[user_id]["setup"] = True
        confirmation_message = self.generate_custom_confirmation(
            terms, subject)
        format_message = (
            "First, select your mode: \n"
            "Free Response: answer in your own words. \n"
            "Multiple Choice: choose from four given options. \n"
            "Fill-in-the-Blank: provide the missing term in the sentence. \n"
        )
        return f"{confirmation_message}\n{format_message}"

    def generate_custom_confirmation(self, terms, subject):
        subject_text = f"{subject}" if subject else ""
        return f"Sounds great! I'll help you quickly study these {subject_text} terms. Let's get started! \n"

    def extract_format(self, user_message):
        prompt = f"""
        Extract the study format from the following user message:
        {user_message}
        The format should be either "Free Response" or "Multiple Choice" or "Fill-in-the-Blank"
        Respond in JSON format:
        {{
        "format": "Free Response" or "Multiple Choice" or "Fill-in-the-Blank"
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
        extracted_format = self.extract_format(user_message)

        if user_id not in self.sessions or "setup" not in self.sessions[user_id]:
            return "⚠️ No active study session found. Please start a session first."

        if extracted_format not in ["Free Response", "Multiple Choice", "Fill-in-the-Blank"]:
            return "⚠️ Invalid format. Please choose 'Free Response', 'Multiple Choice', or 'Fill-in-the-Blank'."

        session = self.sessions[user_id]
        if "terms" in session and session["terms"]:
            self.sessions[user_id]["format"] = extracted_format
            self.sessions[user_id]["setup"] = False

            return f"You have chosen the {extracted_format} format using extracted study terms. Let's get started!"

        self.sessions[user_id]["format"] = extracted_format
        self.sessions[user_id]["setup"] = False

        return f"You have chosen the {extracted_format} format. Let's get started!"

    def get_current_term(self, user_id):
        session = self.sessions.get(user_id)
        if not session:
            return None
        num_questions = session.get('num_questions', len(session["terms"]))
        return session["terms"][session["current_term"]] if session["current_term"] < num_questions else None

    def next_term(self, user_id):
        session = self.sessions.get(user_id)
        if not session:
            return None

        num_questions = session.get('num_questions', len(session["terms"]))
        session["current_term"] += 1

        if session["current_term"] >= num_questions:
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

    def generate_fill_in_the_blank_question(self, term):
        prompt = f"""
        Generate a fill-in-the-blank sentence where the blank is the term '{term}'. The sentence 
        should provide enough context that the user can reasonably guess the correct term. Return
        only the sentence with the blank. The blank should be represented as '**___**', with the number
        of underscores used equivalent to half the number of letters in the word. The blank is be in bold.
        """
        try:
            messages = [{"role": "user", "content": prompt}]
            response = self.mistral.chat.complete(
                model="mistral-tiny", messages=messages
            )
            sentence = response.choices[0].message.content.strip()
            return sentence
        except Exception as e:
            logging.error(
                f"Error generating fill-in-the-blank sentence: {str(e)}")
            return f"___ is an important term in this topic."

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

            elif session["format"] == "Fill-in-the-Blank":
                if user_answer.strip().lower() == term.lower():
                    return "✅ Correct!"
                return f"❌ Incorrect. The correct answer was: {term}"

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

    def process_pdf(self, pdf_path):
        if not os.path.exists(pdf_path):
            logger.error(f"❌ PDF file not found at path: {pdf_path}")
            return "❌ Error: PDF file not found."

        extracted_text = ""

        try:
            with pdfplumber.open(pdf_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    page_text = page.extract_text()

                    if page_text:
                        extracted_text += page_text + "\n"

            if not extracted_text.strip():
                return "⚠ No readable text found in the PDF."

            return extracted_text

        except Exception as e:
            return "❌ An error occurred while processing the PDF."

    def extract_study_terms(self, user_id, text):
        """Uses Mistral AI to extract key study terms and stores them in the session."""
        prompt = (
            f"Extract exactly {self.sessions[user_id].get('num_questions', 10)} important single-word or short-phrase terms from the following text.\n\n"
            f"{text}\n\n"
            "Requirements:\n"
            "1. Terms should be 1-3 words maximum\n"
            "2. Avoid full sentences or numbered items\n"
            "3. Focus on key technical terms or concepts\n\n"
            "Return only the list of terms, one per line"
        )

        try:
            messages = [{"role": "system", "content": prompt}]
            response = self.mistral.chat.complete(
                model="mistral-tiny",
                messages=messages
            )

            response_text = response.choices[0].message.content.strip()
            terms = response_text.split("\n") if response_text else []

            if user_id not in self.sessions:
                self.sessions[user_id] = {}

            self.sessions[user_id].update({
                "terms": terms,
                "current_term": 0,
                "format": None,
                "setup": True
            })

            return terms

        except Exception as e:
            logger.error(f"Error calling Mistral AI: {e}")
            return ["❌ An error occurred while processing the text."]

    def generate_terms_from_subject(self, subject):
        prompt = f"Generate a list of 10 important study terms related to the subject '{subject}'. Each term should be 1-3 words maximum. Avoid full sentences. Focus on key technical terms or concepts. Return the terms as a list, one per line."

        try:
            messages = [{"role": "user", "content": prompt}]
            response = self.mistral.chat.complete(
                model=MISTRAL_MODEL,
                messages=messages
            )

            response_text = response.choices[0].message.content.strip()
            terms = [term.strip()
                     for term in response_text.split("\n") if term.strip()]
            terms = terms[:10]  # Limit to 10 terms
            return terms

        except Exception as e:
            logger.error(f"Error generating terms from subject: {e}")
            return []
