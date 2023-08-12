from typing import Union
from app import ai_assistant as assist

from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/items/{item_id}")
def read_item(item_id: int, q: Union[str, None] = None):
    return {"item_id": item_id, "q": q}

@app.get("/get_response/{user_prompt}")
async def get_response(user_prompt: str):
    ai_response = assist.get_response(assist.json_to_dict('app/menu.json'), user_prompt)
    return ai_response
