# CS 153 - QuizAI
Our final project is an agent to help with flashcard based studying -- simply put, we aimed to emulate the experience of going over flashcards with a knowledgable (and patient!) partner. While regular flashcards promote rote memorization, we have built our agent to prompt critical thinking in the response to each quesion. Our agent is accessible through the QuizAI discord channel, and its very easy to both give the agent your terms and to begin practice.

## Ingestion
There are three ways for the agent to recieve the terms you would like to study.

### No. 1: PDF
Give the agent a pdf containing material that you would like to review, and the agent will extract relevant terms for your session and create definitions for those terms. 
### No. 2: User List
You can message the agent with a list of terms seperated by commas, and the agent will create definitions for those terms.
### No. 3: Subject Mode
Instead of giving the agent a full list of terms, you can simply give one term that refers to the general area of study, such as "linguistic determinism," and the agent will generate terms related to that specific concept as well as their definitions.

# Review
Reviewing takes the form of three distinct modes which the user picks.

### No. 1: Free Response
The user will be given a term and the user will respond to the term will be a short definition. The agent will determine if that answer is mostly correct.
### No. 2: Fill in the Blank
The user will be given a sentence with a blank space for a fitting term. The user should respond with the correct term,
### No 3: Multiple Choice
The user will be given a term and four potential definitions. Three will be plausible distractors and one will be the correct answer. 

