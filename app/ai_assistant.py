import os
from dotenv import load_dotenv, find_dotenv
import json
import openai

load_dotenv(find_dotenv())
openai.api_key = os.getenv("OPENAI_API_KEY")


def main():
    user_input = input("Ask a question: ")
    prompt_context = json_to_dict('menu.json')
    output = get_response(prompt_context, user_input)
    print(output)

# converts json file to a dictionary for use in setting context for the gpt model
def json_to_dict(file_name: str) -> dict:
    with open(file_name) as json_info:
        data = json.load(json_info)
    return data


def get_response(context_prompt: dict, user_prompt: str) -> str:
    response = openai.ChatCompletion.create(
        model='gpt-3.5-turbo',
        messages=[
            {'role': 'system', 'content': 'You are an online assistant designed to help a customer at a brewery.'},
            {'role': 'system', 'content': f'This is our menu: \'\'\'{context_prompt}\'\'\''},
            {'role': 'user', 'content': f'{user_prompt}'},
            {'role': 'user', 'content': 'Return concise answer to user prompt.'}
        ],
        max_tokens=128
    )
    print(response['usage'])
    response = response['choices'][0]['message']['content']
    return response


if __name__ == "__main__":
    main()
