import os
from dotenv import load_dotenv, find_dotenv
import openai

load_dotenv(find_dotenv())
openai.api_key = os.getenv("OPENAI_API_KEY")


def main():
    user_input = input("Ask a question: ")
    output = get_response(user_input)
    print(output)
    pass


def get_response(prompt: str) -> str:
    response = openai.ChatCompletion.create(
        model='gpt-3.5-turbo',
        messages=[{'role': 'user', 'content': f'{prompt}'}],
        max_tokens=128
    )
    response = response['choices'][0]['message']['content']
    return response


if __name__ == "__main__":
    main()
