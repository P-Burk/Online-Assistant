import json
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

    def __submit_order(self) -> None:
        if self.__order_complete_flag:
            self.__order_holder['order_total'] = self.__order_total_calculator(self.__order_holder)
            self.__db_helper.insert_order(self.__order_holder)
            self.__reset_order()
        else:
            print("Order is not complete.")

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
        self.__add_to_chat_history('system', f"Order update: {key} = {value}")
        self.__order_flag_raise()

    def __order_items_total_calculator(self, order_items: dict) -> dict:
        beer_menu = {}
        food_menu = {}
        db_menu = json.loads(self.__db_helper.get_menu())

        for section in db_menu:
            beer_menu = section.get("beer_menu", {})
            food_menu = section.get("food_menu", {})

        for item in order_items.keys():
            # beer check
            if item in beer_menu.keys():
                order_items[item]["item_price"] = beer_menu[item]["price"]
                order_items[item]["item_total_price"] = beer_menu[item]["price"] * order_items[item]["item_qty"]

            # food check
            for category in food_menu.values():
                if item in category.keys():
                    order_items[item]["item_price"] = category[item]["price"]
                    order_items[item]["item_total_price"] = category[item]["price"] * order_items[item]["item_qty"]

        return order_items

    def __order_total_calculator(self, user_order: dict) -> float:
        total = 0.0
        for item in user_order['order_items'].keys():
            total += user_order['order_items'][item]["item_total_price"]
        return total

    def bot_entry_point(self, *args):

        # Initial welcome message
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

        # after the conversation has started
        else:
            user_input = args[0]
            # user_input = input("User: ")
            self.__add_to_chat_history('user', user_input)

            # run all extractors before feeding input to the classifier
            self.__user_name_extractor(user_input)
            self.__user_phone_extractor(user_input)
            self.__payment_method_extractor(user_input)
            self.__user_email_extractor(user_input)

            # classify the user input
            classification = self.__intent_chooser(user_input)
            match classification:
                case "order food":
                    order_items = self.__order_items_extractor(user_input)
                    self.__print_chat_history()
                    return "What is your name?"
                case "get menu":
                    self.__print_chat_history()
                    return "Here is the menu."
                case "question answer":
                    question_answer = self.__general_questions_entry_point(user_input)
                    self.__print_chat_history()
                    return f"PLACE HOLDER: {question_answer}"
                # case "None":
                #     self.__print_chat_history()
                #     return "I'm sorry, I don't understand. Can you rephrase that?"
                case _:
                    default_response = self.__just_a_nice_response(user_input)
                    self.__print_chat_history()
                    return default_response

    def __order_items_extractor(self, user_prompt: str) -> dict | None:
        order_items = openai.ChatCompletion.create(
            model=self.__MODEL,
            messages=[
                {"role": "system",
                 "content": "You are a system whose purpose is to extract the items from an order and the quantity "
                            "of said items out of a string of text. You will output only the items and their "
                            "quantities and nothing else. The output will be in the following format:"
                            "\n```\n"
                            "{\"ITEM NAME\": {\"item_qty\": INTEGER}, "
                            "\"SECOND ITEM NAME\": {\"item_qty\": INTEGER}}"
                            "\n```\n"
                            "If no food items are ordered, return ```None```."},
                {"role": "user", "content": "I'd like to order 2 cheeseburgers and 3 fries."},
                {"role": "assistant",
                 "content": "{\"cheeseburger\": {\"item_qty\": 2}, \"fries\": {\"item_qty\": 3}}"},
                {"role": "user", "content": "Can I please get one apple pie and one blueberry tart?"},
                {"role": "assistant",
                 "content": "{\"apple pie\": {\"item_qty\": 1}, \"blueberry tart\": {\"item_qty\": 1}}"},
                {"role": "user", "content": "I'm done eating. Let's go to the movies and then head home."},
                {"role": "assistant", "content": "None"},
                {"role": "user", "content": "I'll take 10 beef tacos, and he'll have five chicken quesadillas."},
                {"role": "assistant",
                 "content": "{\"beef taco\": {\"item_qty\": 10}, \"chicken quesadilla\": {\"item_qty\": 5}}"},
                {"role": "user",
                 "content": "We'd like to order 2 chicken buckets, 5 dinner rolls, a side of mac n' cheese, "
                            "a side of mashed potatoes, and 2 fudge brownies."},
                {"role": "assistant",
                 "content": "{\"chicken bucket\": {\"item_qty\": 2}, "
                            "\"dinner rolls\": {\"item_qty\": 5}, "
                            "\"mac n' cheese\": {\"item_qty\": 1}, "
                            "\"mashed potatoes\": {\"item_qty\": 1}}"},
                {"role": "user", "content": "can i get two large fries and 5 orders of chicken nuggets?"},
                {"role": "assistant",
                 "content": "{\"large fries\": {\"item_qty\": 2}, \"chicken nuggets\": {\"item_qty\": 5}}"},
                {"role": "user",
                 "content": "I forgot what I want to order. Maybe I will come back later and get a brownie."},
                {"role": "assistant", "content": "None"},
                {'role': 'user', 'content': f'{user_prompt}'}
            ],
            temperature=0.5,
            max_tokens=512,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0
        )
        order_items = order_items['choices'][0]['message']['content']
        if order_items == "None":
            return None
        order_items = json.loads(order_items)
        order_items = self.__order_items_gpt_cross_check(order_items)
        order_items = self.__order_items_total_calculator(order_items)
        self.__order_update("order_items", order_items)
        return order_items

    def __order_items_gpt_cross_check(self, order_items: dict) -> dict:
        beer_menu = {}
        food_menu = {}
        db_menu = json.loads(self.__db_helper.get_menu())
        output_items = {}

        for section in db_menu:
            beer_menu = section.get("beer_menu", {})
            food_menu = section.get("food_menu", {})

        for item in order_items:
            determination = openai.ChatCompletion.create(
                model=self.__MODEL,
                messages=[
                    {"role": "system",
                     "content": "You are a system whose purpose is to cross check whether an item in the order is "
                                "on the provided menus. If the order item is not on the menu, "
                                "output ```None``` If the order item is on the menu, you will correct its "
                                "spelling and then output the corrected order item. If the order item is on "
                                "the menu and doesn't need correction, output the order item."
                                f"\nThe beer menu is:\n```\n{beer_menu}\n```\n"
                                f"The food menu is:\n```\n{food_menu}\n```"
                     },
                    {"role": "user", "content": "cheeseburger"},
                    {"role": "assistant", "content": "Classic Cheeseburger"},
                    {"role": "user", "content": "Loaded Nachos"},
                    {"role": "assistant", "content": "Loaded Nachos"},
                    {"role": "user", "content": "mushrom swis burger"},
                    {"role": "assistant", "content": "Mushroom Swiss Burger"},
                    {"role": "user", "content": "grilled cheese sandwich"},
                    {"role": "assistant", "content": "None"},
                    {"role": "user", "content": "Cocacola"},
                    {"role": "assistant", "content": "None"},
                    {"role": "user", "content": "Beer"},
                    {"role": "assistant", "content": "None"},
                    {"role": "user", "content": "velvet lager"},
                    {"role": "assistant", "content": "Velvet Lager"},
                    {"role": "user", "content": f"{item}"}
                ],
                temperature=0.5,
                max_tokens=20,
                top_p=1,
                frequency_penalty=0,
                presence_penalty=0
            )
            determination = determination['choices'][0]['message']['content']
            if determination == "None":
                output_items[item] = None
            else:
                output_items[determination] = order_items[item]
        return output_items

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

    def __just_a_nice_response(self, user_prompt: str) -> str:
        response = openai.ChatCompletion.create(
            model=self.__MODEL,
            messages=[
                {"role": "system", "content": "You are a nice assistant that responds to the user's input. "
                 "Just supply a brief response to the user to continue the conversation."},
                {"role": "user", "content": f"{user_prompt}"}
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

    ##################################################
    ################ ORDER FUNCTIONS ################
    ##################################################
    def __user_name_extractor(self, user_prompt: str) -> str | None:
        user_name = response = openai.ChatCompletion.create(
            model=self.__MODEL,
            messages=[
                {"role": "system",
                 "content": "You are a system whose purpose is to extract the name from a string of text. "
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
        else:
            self.__order_update("user_name", user_name)
            return user_name

    def __user_phone_extractor(self, user_prompt: str) -> str | None:
        user_phone = openai.ChatCompletion.create(
            model=self.__MODEL,
            messages=[
                {"role": "system",
                 "content": "You are a system whose purpose is to extract the phone number from a string of text."
                            "You will output only the phone number of the user and nothing else. "
                            "If a phone number cannot be found, output \"\"\"000-000-0000\"\"\"."},
                {"role": "user", "content": "My phone number is 123-456-7890."},
                {"role": "assistant", "content": "123-456-7890"},
                {"role": "user", "content": "hey, can you call be back at 8529517536?"},
                {"role": "assistant", "content": "852-951-7536"},
                {"role": "user", "content": "Do you know Brad's phone number?"},
                {"role": "assistant", "content": "000-000-0000"},
                {"role": "user",
                 "content": "you've reached Bill at 741-124-8965, please leave a message and I'll get back to you."},
                {"role": "assistant", "content": "741-124-8965"},
                {"role": "user", "content": "what time is it right now?"},
                {"role": "assistant", "content": "000-000-0000"},
                {"role": "user", "content": "I tried calling John at 9996582350, but no one picked up."},
                {"role": "assistant", "content": "999-658-2350"},
                {"role": "user", "content": "Do you remember Janice's phone number? I think I have the wrong one."},
                {"role": "assistant", "content": "000-000-0000"},
                {"role": "user", "content": "If you have any questions, "
                                            "feel free to reach out to me at (555) 123-4567."},
                {"role": "assistant", "content": "555-123-4567"},
                {"role": "user", "content": f"{user_prompt}"}
            ],
            temperature=0.5,
            max_tokens=24,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0
        )
        user_phone = user_phone['choices'][0]['message']['content']
        if user_phone == "000-000-0000":
            return None
        else:
            self.__order_update("user_phone", user_phone)
            return user_phone

    def __payment_method_extractor(self, user_prompt: str) -> str | None:
        payment_method = openai.ChatCompletion.create(
            model=self.__MODEL,
            messages=[
                {"role": "system",
                 "content": "You are a system whose purpose is to extract the payment method from a string of text. "
                            "You will output only the payment method of the user and nothing else. "
                            "If a payment method cannot be found, output \"\"\"None\"\"\". "
                            "The three payment methods are:\nCash,\nCard,\nBoth"},
                {"role": "user", "content": "I'll be paying with cash."},
                {"role": "assistant", "content": "Cash"},
                {"role": "user", "content": "My debit card number is 1234 5678 9012 3456."},
                {"role": "assistant", "content": "Card"},
                {"role": "user", "content": "can you put it on my credit card?"},
                {"role": "assistant", "content": "Card"},
                {"role": "user", "content": "I'll pay for it tomorrow."},
                {"role": "assistant", "content": "None"},
                {"role": "user", "content": "I'm ready to make a purchase. "
                                            "What payment options do you accept – cash or card?"},
                {"role": "assistant", "content": "Both"},
                {"role": "user", "content": "Is it possible to split the bill between cash and card payments "
                                            "for our dinner tonight?"},
                {"role": "assistant", "content": "Both"},
                {"role": "user", "content": "I'm planning to attend the event. Should I bring cash for tickets?"},
                {"role": "assistant", "content": "Cash"},
                {"role": "user", "content": "Do you know if the store down the road takes card?"},
                {"role": "assistant", "content": "Card"},
                {"role": "user", "content": "I don't have my card with me. Can I pay with cash?"},
                {"role": "assistant", "content": "Cash"},
                {"role": "user", "content": "do you guys take cash?"},
                {"role": "assistant", "content": "Cash"},
                {"role": "user", "content": "I'm not sure if I should pay with cash or card. "
                                            "I think this time I will use my card. I want to get the points."},
                {"role": "assistant", "content": "Card"},
                {"role": "user", "content": f"{user_prompt}"}
            ],
            temperature=0.5,
            max_tokens=8,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0
        )
        payment_method = payment_method['choices'][0]['message']['content']
        if payment_method == "None":
            return None
        else:
            self.__order_update("payment_method", payment_method)
            return payment_method

    def __user_email_extractor(self, user_prompt: str) -> str | None:
        user_email = openai.ChatCompletion.create(
            model=self.__MODEL,
            messages=[
                {"role": "system",
                 "content": "You are a system whose purpose is to extract the email from a string of text. "
                            "You will output only the email of the user and nothing else. "
                            "If an email cannot be found, output \"\"\"None\"\"\". \n"
                            "Common email domain names are:\n@gmail.com,\n@yahoo.com,\n@outlook.com,\n@hotmail.com,"
                            "\n@aol.com,\n@icloud.com,\n@mail.com,\n@protonmail.com,\n@yandex.com,\n@gmx.com,"
                            "\n@zoho.com"},
                {"role": "user",
                 "content": "Could you please send me the details at john.doe@example.com? "
                            "I'm looking forward to reviewing the information."},
                {"role": "assistant", "content": "john.doe@example.com"},
                {"role": "user",
                 "content": "I'll be available for the call tomorrow. "
                            "You can reach me at sarah.smith@emailprovider.net. Thanks!"},
                {"role": "assistant", "content": "sarah.smith@emailprovider.net"},
                {"role": "user",
                 "content": "If you have any questions, don't hesitate to email me at info@companyname.com. "
                            "I'll be glad to assist you."},
                {"role": "assistant", "content": "info@companyname.com"},
                {"role": "user",
                 "content": "can you please send me your email. "
                            "I want to forward you the message the supervisor sent."},
                {"role": "assistant", "content": "None"},
                {"role": "user",
                 "content": "The document is attached. Let me know if you need any changes. "
                            "My email is jane.roberts@gmail.com."},
                {"role": "assistant", "content": "jane.roberts@gmail.com"},
                {"role": "user",
                 "content": "I'd like to subscribe to your newsletter. "
                            "Please add me using my personal address: news.subscriber@hotmail.com."},
                {"role": "assistant", "content": "news.subscriber@hotmail.com"},
                {"role": "user",
                 "content": "is your email mikejones@gmail.com? I keep getting a \"no delivered\" error."},
                {"role": "assistant", "content": "mikejones@gmail.com"},
                {"role": "user",
                 "content": "can you please forward that message to fakeemail@outlook.com? I want to save it."},
                {"role": "assistant", "content": "fakeemail@outlook.com"},
                {"role": "user", "content": f"{user_prompt}"}
            ],
            temperature=0.5,
            max_tokens=48,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0
        )
        user_email = user_email['choices'][0]['message']['content']
        if user_email == "None":
            return None
        else:
            self.__order_update("user_email", user_email)
            return user_email

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
