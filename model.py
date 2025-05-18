from openai import OpenAI


class Model:
    def __init__(self, url: str, name: str):
        try:
            with open("api_key.txt", "r", encoding="utf-8") as f:
                key = f.readline().strip()
        except FileNotFoundError:
            print("API key not found! Please check if \"api_key.txt\" exists!\"")
            raise

        self.__client = OpenAI(api_key=key, base_url=url)
        self.__name = name

    async def stream_chat(self, history: list):
        response = self.__client.chat.completions.create(
            model=self.__name,
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
            model=self.__name,
            messages=history,
            stream=False
        )

        return response.choices[0].message.content

class DSModel(Model):
    def __init__(self):
        super().__init__(url="https://api.deepseek.com/", name="deepseek-chat")




