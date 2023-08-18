import os
from typing import List, Any
from dotenv import load_dotenv, find_dotenv
import json
import openai
from app import DBHelper

load_dotenv(find_dotenv())
openai.api_key = os.getenv("OTHER_OPENAI_API_KEY")


class AIAssistant:
    _MODEL = 'gpt-3.5-turbo'
    _SUMMARY_LENGTH = 150
    _CHAT_HISTORY_LENGTH = 15  # making this too high results in slower response and more token usage
    _FUNCTIONS = [
        {
            "name": "make_order",
            "description": "Create a new order for a restaurant.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_name": {
                        "type": "string",
                        "description": "Customer's name."
                    },
                    "user_phone": {
                        "type": "string",
                        "description": "Customer's phone number."
                    },
                    "user_email": {
                        "type": "string",
                        "format": "email",
                        "description": "Customer's email address."
                    },
                    "order_items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "item_name": {
                                    "type": "string",
                                    "description": "Item name."
                                },
                                "item_quantity": {
                                    "type": "integer",
                                    "minimum": 1,
                                    "description": "Item quantity."
                                },
                                "item_price": {
                                    "type": "number",
                                    "description": "Item price. Multiply this by the quantity to get the total price for the item."
                                }
                            },
                            "required": ["name", "quantity", "price"]
                        },
                        "description": "List of items in the order."
                    },
                    "payment_method": {
                        "type": "string",
                        "enum": ["cash", "credit_card"],
                        "description": "Payment method for the order."
                    },
                    "order_total": {
                        "type": "number",
                        "description": "Total amount for the order."
                    }
                },
                "required": ["user_name", "user_phone", "user_email", "order_items", "payment_method", "order_total"]
            }
        }
    ]

    def __init__(self):
        self._chat_holder: List[dict] = []
        self._db_helper = DBHelper.DBHandler()
        self._general_question_classifications = self._db_helper.get_all_field_names("FAQ")

    def _add_to_chat_history(self, input_role: str, input_msg: str) -> None:
        self._chat_holder.append({'role': input_role, 'content': input_msg})
        self._prune_chat_history()

    def _prune_chat_history(self) -> None:
        if len(self._chat_holder) > self._CHAT_HISTORY_LENGTH:
            response = openai.ChatCompletion.create(
                model=self._MODEL,
                messages=[
                    self._chat_holder.pop(0),
                    self._chat_holder.pop(0),
                    self._chat_holder.pop(0),
                    {'role': 'user',
                     'content': f'Summarize the main facts in the above chat in {self._SUMMARY_LENGTH} words or less.'},
                ],
                max_tokens=1000
            )
            response = response['choices'][0]['message']['content']
            self._chat_holder.insert(0, {'role': 'system', 'content': f'Previous chat summary: {response}'})

    # converts json file to a dictionary for use in setting context for the gpt model
    def _json_to_dict(self, file_name: str) -> dict:
        with open(file_name) as json_info:
            data = json.load(json_info)
        return data

    def get_response(self, user_prompt: str) -> str:
        background_context = self._json_to_dict('menu.json')
        self._add_to_chat_history('user', user_prompt)
        response = openai.ChatCompletion.create(
            model=self._MODEL,
            # messages=[
            #     # TODO: uncomment the two system lines when done messing around
            #     # {'role': 'system', 'content': 'You are an online assistant designed to help a customer at a brewery.'},
            #     # {'role': 'system', 'content': f'This is our menu: \'\'\'{context_prompt}\'\'\''},
            #     {'role': 'user', 'content': f'{self}'},
            #     # {'role': 'user', 'content': 'Return concise answer to user prompt.'}
            # ],
            messages=[chat for chat in self._chat_holder],
            max_tokens=128
        )
        print(response['usage'])
        response = response['choices'][0]['message']['content']
        self._add_to_chat_history('system', response)
        return response

    def print_chat_history(self) -> None:
        print("------------------------------------")
        for chat in self._chat_holder:
            print(chat)
        print("------------------------------------")

    ########################################################################################################################
    # The following functions are for the order processing section of the AI assistant.
    ########################################################################################################################


    def __user_name_extractor(self, user_prompt: str) -> Any | None:
        user_name = response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo-0613",
            messages=[
                {"role": "system",
                 "content": "You are a system who's purpose is to extract the name from a string of text. "
                            "You will output only the name of the user and nothing else. "
                            "If a name cannot be found, output \"\"\"None\"\"\"."},
                {"role": "user", "content": "My name is Preston."},
                {"role": "assistant", "content": "Preston"},
                {"role": "user", "content": "Hi, my name is Sandra, but you can call me Sandy."},
                {"role": "assistant", "content": "Sandy"},
                {"role": "user", "content": "can I get a towel?"},
                {"role": "assistant", "content": "None"},
                {"role": "user", "content": "im looking for an order. It should be under the name debra waters"},
                {"role": "assistant", "content": "Debra Waters"},
                {"role": "user", "content": "what time is it right now?"},
                {"role": "assistant", "content": "None"},
                {"role": "user", "content": "did you see lauren land that crazy high jump the other day?"},
                {"role": "assistant", "content": "Lauren"},
                {"role": "user", "content": "Hey, this is Dean. Can I place an order to be picked up?"},
                {"role": "assistant", "content": "Dean"},
                {"role": "user", "content": f"{user_prompt}"}
            ],
            temperature=0.5,
            max_tokens=24,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0
        )
        user_name = user_name['choices'][0]['message']['content']
        if user_name == "None":
            return None
        return user_name

    def make_order(self, user_name: str, user_phone: str, user_email: str, order_items: List[dict],
                   payment_method: str, order_total: float):
        order = {
            "user_name": user_name,
            "user_phone": user_phone,
            "user_email": user_email,
            "order_items": order_items,
            "payment_method": payment_method,
            "order_total": order_total
        }
        self._db_helper.insert_order(order)

    def _get_order_arguments(self, API_output: dict):
        output = API_output['choices'][0]['message']['function_call']['arguments']
        output = json.loads(output)
        user_name = output['user_name']
        user_phone = output['user_phone']
        user_email = output['user_email']
        items = output['items']
        payment_method = output['payment_method']
        order_total = output['order_total']
        return user_name, user_phone, user_email, items, payment_method, order_total

    def order_convo(self, user_prompt: str) -> str:
        self._add_to_chat_history('user', user_prompt)
        print("Before chat call")
        context_messages = [
            {'role': 'system', 'content': 'You are an online assistant designed to help a customer at a brewery.'},
            {'role': 'system', 'content': 'You need to ask the user for all of the information to make an order, '
                                          'but don\'t ask for information that the user has already provided.'
                                          'Also, only ask for small chunks of information at a time.'},
            {'role': 'system', 'content': f'Here is our menu: {self._db_helper.get_menu()}'},
            {'role': 'system', 'content': 'The user can only order items that are on the menu.'},
            {'role': 'system', 'content': 'When confirm and order before submitting it, ask the user if they want to '
                                          'add anything else to their order.'},
            {'role': 'system', 'content': 'Here is what has been said in the conversation so far: '},
        ] + [chat for chat in self._chat_holder] + [
            {'role': 'system', 'content': 'Here is what the user just said: '},
            {'role': 'user', 'content': f'{user_prompt}'}
        ]
        for chat in self._chat_holder:
            print(chat)
        response = openai.ChatCompletion.create(
            model=self._MODEL,
            messages=context_messages,
            functions=self._FUNCTIONS,
            function_call="auto",
        )
        print(response)
        # add response message to chat history if it is not None (None caused by function_call)
        stripped_response = response['choices'][0]['message']['content']
        if stripped_response is not None:
            self._add_to_chat_history('system', stripped_response)
            response = stripped_response
        else:
            # This is the branch if a function call is made
            # if the response is a function call, then we need to have an output message for the user
            params = json.loads(response['choices'][0]['message']['function_call']['arguments'])
            chosen_function = eval("self." + response['choices'][0]['message']['function_call']['name'])
            chosen_function(**params)
            print("Your order has been placed. You will be contacted when it is ready for pickup.")
        return response

    ########################################################################################################################
    # The following functions are for the general questions section of the AI assistant.
    ########################################################################################################################

    # Classifies the question and returns the classification.
    # Classification is based on fields found in the FAQ collection.
    def __get_general_question_classification(self, user_prompt: str) -> str:
        response = openai.ChatCompletion.create(
            model=self._MODEL,
            messages=[
                {'role': 'system',
                 'content': f'Determine the classification of the following question and choose '
                            f'from {self._general_question_classifications} or NONE'},
                {'role': 'user', 'content': f'{user_prompt}'},
            ],
            max_tokens=500
        )
        response = response['choices'][0]['message']['content']
        print("Classification: " + response)
        return response

    # Returns a response to a general question.
    def general_questions(self, user_prompt: str) -> str:
        self._add_to_chat_history('user', user_prompt)
        prompt_classification = self.__get_general_question_classification(user_prompt)
        if prompt_classification == "NONE":
            message = [
                {'role': 'system',
                 'content': f'Inform the customer to please call the brewery 555-987-6543 or reach out on social media/email to get an answer to their question.'},
                {'role': 'system', 'content': 'Return a concise answer to the user prompt.'},
                {'role': 'system',
                 'content': 'If the user prompt is not answered, ask the user to rephrase their question or contact the brewery directly.'},
                {'role': 'user', 'content': f'{user_prompt}'}
            ]
        else:
            context = self._db_helper.read_all(prompt_classification, "FAQ")
            message = [
                {'role': 'system', 'content': f'The following is information about the brewery: {context}.'},
                {'role': 'system', 'content': 'Return a concise answer to the user prompt.'},
                {'role': 'system',
                 'content': 'If the user prompt is not answered, ask the user to rephrase their question or contact the brewery directly.'},
                {'role': 'user', 'content': f'{user_prompt}'}
            ]
        response = openai.ChatCompletion.create(
            model=self._MODEL,
            messages=message,
            max_tokens=500
        )
        print(response['usage'])
        response = response['choices'][0]['message']['content']
        self._add_to_chat_history('system', response)
        self.print_chat_history()
        return response
