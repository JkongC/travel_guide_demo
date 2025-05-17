from chat import ChatInterface
from model import DSModel

model = DSModel()

with open("prompt.txt", "r", encoding="utf-8") as f:
    prompt = f.read()

demo = ChatInterface.instance(model, stream_output=True, prompt=prompt)

demo.launch()
