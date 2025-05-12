from openai import OpenAI


class Model:
    def __init__(self):
        with open("api_key.txt", "r", encoding="utf-8") as f:
            key = f.readline().strip()

        self.__client = OpenAI(api_key=key, base_url="https://api.deepseek.com")

    async def stream_chat(self, history: list):
        response = self.__client.chat.completions.create(
            model="deepseek-chat",
            messages=history,
            stream=True
        )

        full_reply = ""
        for chunk in response:
            if chunk.choices[0].delta.content:
                full_reply += chunk.choices[0].delta.content
                yield full_reply

    def normal_chat(self, history: list) -> str:
        response = self.__client.chat.completions.create(
            model="deepseek-chat",
            messages=history,
            stream=False
        )

        return response.choices[0].message.content