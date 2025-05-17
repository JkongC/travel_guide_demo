from chat import ChatInterface
from model import Model


model = Model()

with open("prompt.txt", "r", encoding="utf-8") as f:
    prompt = f.read()

demo = ChatInterface(model, stream_output=True, prompt=prompt)

demo.launch()
