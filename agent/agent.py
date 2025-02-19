import logging
from mistralai import Mistral
import os
from dotenv import load_dotenv
import random

logging.basicConfig(level=logging.INFO)

load_dotenv()
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")


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
            logging.error(f"Error extracting terms and subject: {str(e)}")
            return {"terms": [], "subject": ""}

    def start_session(self, user_id, user_message):
        extracted = self.extract_terms_and_subject(user_message)
        terms = extracted.get("terms", [])
        subject = extracted.get("subject", "")

        if not terms:
            return None, "⚠️ I couldn't extract any study terms. Please list them clearly."

        self.sessions[user_id] = {
            "terms": terms, "current_term": 0, "subject": subject, "format": None}
        confirmation_message = self.generate_custom_confirmation(
            terms, subject)

        format_message = (
            "Choose either Free Response or Multiple Choice format"
            "In Free Response, you answer in your own words. "
            "In Multiple Choice, you'll choose from four given options."
        )
        return terms[0], f"{confirmation_message} {format_message}"

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

    def set_study_format(self, user_id, chosen_format):
        if chosen_format in ["Free Response", "Multiple Choice"]:
            self.sessions[user_id]["format"] = chosen_format
            return f"You have chosen the {chosen_format} format. Let's get started!"
        else:
            return "⚠️ Invalid format. Please choose either 'Free Response' or 'Multiple Choice'."

    def generate_multiple_choice_question(self, term):
        question = f"What does '{term}' mean?"

        correct_answer = ""
        distractors = self.generate_distractors(term)

        options = [correct_answer] + distractors
        random.shuffle(options)

        return {
            "question": question,
            "options": options,
            "correct_answer": correct_answer
        }

    def generate_correct_answer(self, term):
        prompt = f"Generate the correct definition for the term '{term}'."
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
        prompt = f"Generate three incorrect definitions for the term '{term}'. Make these terms sound plausable"
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

    def check_answer(self, term, user_answer, user_id, mcq_questions):
        session = self.sessions.get(user_id)
        if session["format"] == "Multiple Choice":
            correct_answer = self.generate_correct_answer(term)
            prompt = f"""
            You are an AI tutor. The user was asked:
            'What does {term} mean?'

            The user's answer: "{user_answer}"
            The correct answer is: "{correct_answer}"
            The other options are: {', '.join(mcq_questions)}

            Evaluate if the answer is correct and explain why the other options are incorrect. Respond with:
            - ✅ "Correct!" if the answer is mostly accurate.
            - ❌ "Incorrect" if it's wrong, followed by a brief correction and explanations for the other options.
            """

            try:
                messages = [{"role": "user", "content": prompt}]
                response = self.mistral.chat.complete(
                    model="mistral-tiny",
                    messages=messages
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                logging.error(f"Error communicating with MistralAI: {str(e)}")
                return "⚠️ Error evaluating the response. Please try again."
        else:
            prompt = f"""
            You are an AI tutor. The user was asked:
            'What does {term} mean?'

            The user's answer: "{user_answer}"

            Evaluate if the answer is correct. Respond with:
            - ✅ "Correct!" if the answer is mostly accurate.
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
                logging.error(f"Error communicating with MistralAI: {str(e)}")
                return "⚠️ Error evaluating the response. Please try again."
