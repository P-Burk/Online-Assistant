import os
from typing import List
from dotenv import load_dotenv, find_dotenv
import json
import openai

load_dotenv(find_dotenv())
openai.api_key = os.getenv("OPENAI_API_KEY")


class AIAssistant:
    _SUMMARY_LENGTH = 150
    _CHAT_HISTORY_LENGTH = 6    # making this too high results in slower response and more token usage

    def __init__(self):
        self._chat_holder: List[dict] = []
        pass

    def _add_to_chat_history(self, input_role: str, input_msg: str) -> None:
        self._chat_holder.append({'role': input_role, 'content': input_msg})
        self._prune_chat_history()

    def _prune_chat_history(self) -> None:
        if len(self._chat_holder) > self._CHAT_HISTORY_LENGTH:
            response = openai.ChatCompletion.create(
                model='gpt-3.5-turbo',
                messages=[
                    self._chat_holder.pop(0),
                    self._chat_holder.pop(0),
                    self._chat_holder.pop(0),
                    {'role': 'user', 'content': f'Summarize the main facts in the above chat in {self._SUMMARY_LENGTH} words or less.'},
                ],
                max_tokens=1000
            )
            response = response['choices'][0]['message']['content']
            self._chat_holder.insert(0, {'role': 'system', 'content': f'Previous chat summary: {response}'})

    # def main():
    #     user_input = input("Ask a question: ")
    #     prompt_context = json_to_dict('menu.json')
    #     output = get_response(prompt_context, user_input)
    #     print(output)

    # converts json file to a dictionary for use in setting context for the gpt model
    def _json_to_dict(self, file_name: str) -> dict:
        with open(file_name) as json_info:
            data = json.load(json_info)
        return data

    def get_response(self, user_prompt: str) -> str:
        background_context = self._json_to_dict('menu.json')
        self._add_to_chat_history('user', user_prompt)
        response = openai.ChatCompletion.create(
            model='gpt-3.5-turbo',
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