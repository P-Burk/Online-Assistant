import os
from typing import List
from dotenv import load_dotenv, find_dotenv
import openai
from app import DBHelper

load_dotenv(find_dotenv())
openai.api_key = os.getenv("OPENAI_API_KEY")


class AIAssistant:
    __MODEL = 'gpt-3.5-turbo-0613'
    __SUMMARY_LENGTH = 150
    __CHAT_HISTORY_LENGTH = 6  # making this too high results in slower response and more token usage

    def __init__(self):
        self.__chat_holder: List[dict] = []
        self.__db_helper = DBHelper.DBHandler()
        self.__general_question_classifications = self.__db_helper.get_all_field_names("FAQ")
        self.__order_holder = {
            "user_name": None,
            "user_phone": None,
            "user_email": None,
            "order_items": None,
            "payment_method": None,
            # "order_total": None  # gets added later
        }
        self.__order_complete_flag = False

    ##################################################
    ################ HELPER FUNCTIONS ################
    ##################################################

    def __print_chat_history(self) -> None:
        print("------------------------------------")
        for chat in self.__chat_holder:
            print(chat)
        print("------------------------------------")

    def __reset_order(self):
        self.__order_holder = {
            "user_name": None,
            "user_phone": None,
            "user_email": None,
            "order_items": None,
            "payment_method": None,
            # "order_total": None  # gets added later
        }
        self.__order_flag_raise()

    def __order_flag_raise(self):
        if None not in self.__order_holder.values():
            self.__order_complete_flag = True
        else:
            self.__order_complete_flag = False
        print(self.__order_complete_flag)

    def __order_update(self, key, value):
        self.__order_holder[key] = value
        self.__order_flag_raise()

    def bot_entry_point(self):
        if len(self.__chat_holder) == 0:
            response = openai.ChatCompletion.create(
                model=self.__MODEL,
                messages=[
                    {"role": "system",
                     "content": "You are a helpful assistant that answers questions about the brewpub. "
                                "Give the user a short greeting and ask them how you can help them."},
                ],
                temperature=0.5,
                max_tokens=50,
                top_p=1,
                frequency_penalty=0,
                presence_penalty=0
            )
            response = response['choices'][0]['message']['content']
            self.__add_to_chat_history('assistant', response)
            return response
        else:
            user_input = input("User: ")
            self.__add_to_chat_history('user', user_input)
            classification = self.__intent_chooser(user_input)
            match classification:
                case "order food":
                    self.__print_chat_history()
                    return "What is your phone number?"
                case "get menu":
                    self.__print_chat_history()
                    return "Here is the menu."
                case "question answer":
                    question_answer = self.__general_questions_entry_point(user_input)
                    self.__print_chat_history()
                    return "PLACE HOLDER: Question answered"
                case "None":
                    self.__print_chat_history()
                    return "I'm sorry, I don't understand. Can you rephrase that?"
                case _:
                    self.__print_chat_history()
                    return "DEFAULT: I'm sorry, I don't understand. Can you rephrase that?"

    ##################################################
    ################ CONVO FUNCTIONS  ################
    ##################################################
    def __add_to_chat_history(self, input_role: str, input_msg: str) -> None:
        self.__chat_holder.append({'role': input_role, 'content': input_msg})
        self.__prune_chat_history()

    def __prune_chat_history(self) -> None:
        if len(self.__chat_holder) > self.__CHAT_HISTORY_LENGTH:
            response = openai.ChatCompletion.create(
                model=self.__MODEL,
                messages=[
                    self.__chat_holder.pop(0),
                    self.__chat_holder.pop(0),
                    self.__chat_holder.pop(0),
                    {'role': 'user',
                     'content': f'Summarize the main facts in the above chat in {self.__SUMMARY_LENGTH} words or less.'},
                ],
                max_tokens=1000
            )
            response = response['choices'][0]['message']['content']
            self.__chat_holder.insert(0, {'role': 'system', 'content': f'Previous chat summary: {response}'})

    def __intent_chooser(self, user_prompt: str) -> str:
        response = openai.ChatCompletion.create(
            model=self.__MODEL,
            messages=[
                {"role": "system",
                 "content": "You are a system that assigns an intent to the user's input. "
                            "You can only pick intents from the options. "
                            "The intent options are as follows:"
                            "\n```\n"
                            "order food,\n"
                            "get menu,\n"
                            "question answer,"
                            "\n```\n"
                            "Only output the user's intent. If an intent can't be determined, output ```None```."},
                {"role": "system", "content": "This is the start of the test."},
                {"role": "user", "content": "how are you today?"},
                {"role": "assistant", "content": "None"},
                {"role": "user", "content": "can I take a look at the menu?"},
                {"role": "assistant", "content": "get menu"},
                {"role": "user", "content": "When are you guys open?"},
                {"role": "assistant", "content": "question answer"},
                {"role": "user", "content": "id like to place an order to be picked up."},
                {"role": "assistant", "content": "order food"},
                {"role": "user", "content": "can I get a cheeseburger?"},
                {"role": "assistant", "content": "order food"},
                {"role": "user", "content": "What beer do you guys have?"},
                {"role": "assistant", "content": "get menu"},
                {"role": "system", "content": "This is the end of the test. "
                                              "You can now start the actual conversation."},
                {"role": "system", "content": "This is the user's input: "},
                {"role": "user", "content": f"{user_prompt}"}
            ],
            temperature=0.5,
            max_tokens=10,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0
        )
        response = response['choices'][0]['message']['content']
        self.__add_to_chat_history('system', f"Current intent: {response}")
        return response

    ##################################################
    ################ ORDER FUNCTIONS ################
    ##################################################

    ##################################################
    ################ GENERAL QUESTIONS ###############
    ##################################################

    # Classifies the question and returns the classification.
    # Classification is based on fields found in the FAQ collection.
    def __get_general_question_classification(self, user_prompt: str) -> str:
        question_classification = openai.ChatCompletion.create(
            model=self.__MODEL,
            messages=[
                {'role': 'system',
                 'content': f'Determine the classification of the following question and choose '
                            f'from {self.__general_question_classifications} or NONE'},
                {'role': 'user', 'content': f'{user_prompt}'},
            ],
            max_tokens=500
        )
        question_classification = question_classification['choices'][0]['message']['content']
        print(f"General Question Classification: {question_classification}")
        return question_classification

    # Returns a response to a general question.
    def __general_questions_entry_point(self, user_prompt: str) -> str:
        prompt_classification = self.__get_general_question_classification(user_prompt)
        if prompt_classification == "NONE":
            message = [
                {'role': 'system',
                 'content': f'Inform the customer to please call the brewery 555-987-6543 or reach out on '
                            f'social media/email to get an answer to their question.'},
                {'role': 'system', 'content': 'Return a concise answer to the user prompt.'},
                {'role': 'system',
                 'content': 'If the user prompt is not answered, ask the user to rephrase their question or '
                            'contact the brewery directly.'},
                {'role': 'user', 'content': f'{user_prompt}'}
            ]
        else:
            context = self.__db_helper.read_all(prompt_classification, "FAQ")
            message = [
                {'role': 'system', 'content': f'The following is information about the brewery: {context}.'},
                {'role': 'system', 'content': 'Return a concise answer to the user prompt.'},
                {'role': 'system',
                 'content': 'If the user prompt is not answered, ask the user to rephrase their question or '
                            'contact the brewery directly.'},
                {'role': 'user', 'content': f'{user_prompt}'}
            ]
        response = openai.ChatCompletion.create(
            model=self.__MODEL,
            messages=message,
            max_tokens=500
        )
        response = response['choices'][0]['message']['content']
        self.__add_to_chat_history('assistant', response)
        return response
