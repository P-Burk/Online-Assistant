from app import ai_assistant as ai

chatbot = ai.AIAssistant()

print(chatbot.bot_entry_point())
while True:
    user_input = input("You: ")
    print(chatbot.bot_entry_point(user_input))