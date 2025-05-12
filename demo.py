from chat import ChatInterface
from model import Model


model = Model()
demo = ChatInterface(model, stream_output=True)

demo.launch()
