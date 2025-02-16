import logging
from mistralai import Mistral
import os
from dotenv import load_dotenv


logging.basicConfig(level=logging.INFO)

load_dotenv()
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

class StudyAgent:
    
    def __init__(self):
        self.sessions = {}  
        self.mistral = Mistral(api_key=MISTRAL_API_KEY)

    def start_session(self, user_id, terms):
        self.sessions[user_id] = {"terms": terms, "current_term": 0}

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