import os
from typing import List
from dotenv import load_dotenv, find_dotenv
import json
import openai
from app import DBHelper

load_dotenv(find_dotenv())
openai.api_key = os.getenv("OTHER_OPENAI_API_KEY")


class AIAssistant:
    __MODEL = 'gpt-3.5-turbo-0613'
    __SUMMARY_LENGTH = 150
    __CHAT_HISTORY_LENGTH = 15  # making this too high results in slower response and more token usage

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


