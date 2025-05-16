import asyncio

import gradio as gr

from model import Model
from info import LocationInfoGetter, get_location_js


class ChatInterface:
    def __init__(self, model: Model, stream_output: bool = False, prompt: str = "You are a helpful assistant."):
        self.__model = model
        self.__stream_output = stream_output
        self.__prompt = prompt

        self.__location_getter = LocationInfoGetter()

        # Define the interface.
        with gr.Blocks() as gr_ui:
            chatbot = gr.Chatbot(type='messages', resizable=True, render_markdown=True)
            user_input = gr.Textbox(label='Ask anything...')
            use_location_info = gr.Checkbox(label='Do you want to tell me your location?', value=False)
            submit_btn = gr.Button("Send")
            clear_btn = gr.Button("Clear history")

            # Saves the conversations.
            history = gr.State([{"role": "system", "content": prompt}])
            user_longitude = gr.Number(visible=False, value=-0.1)
            user_latitude = gr.Number(visible=False, value=-0.1)

            # Add user message to history, then wait for chatbot's reply.
            submit_btn.click(
                fn=self.__add_user_message,
                inputs=[history, user_input, use_location_info, user_longitude, user_latitude],
                outputs=[chatbot, user_input, use_location_info, user_longitude, user_latitude],
                js=get_location_js(),
                queue=False
            ).then(
                fn=self.__wait_for_stream_reply if self.__stream_output else self.__wait_for_reply,
                inputs=history,
                outputs=chatbot
            )

            # Same. This is to support pressing Enter to send messages.
            user_input.submit(
                fn=self.__add_user_message,
                inputs=[history, user_input, use_location_info, user_longitude, user_latitude],
                outputs=[chatbot, user_input, use_location_info, user_longitude, user_latitude],
                js=get_location_js(),
                queue=False
            ).then(
                fn=self.__wait_for_stream_reply if self.__stream_output else self.__wait_for_reply,
                inputs=history,
                outputs=chatbot
            )

            clear_btn.click(
                fn=self.__empty_history,
                inputs=history,
                outputs=chatbot
            )

        self.__ui = gr_ui

    def launch(self, share: bool = False):
        self.__ui.launch(share)

    # Wait for chatbot's reply until it's completely finished.
    def __wait_for_reply(self, history: gr.State) -> gr.State:
        if isinstance(history, list):
            answer = self.__model.normal_chat(history)
            history += [{"role": "assistant", "content": answer}]

        return history

    # Update chatbot's reply in a streaming manner.
    async def __wait_for_stream_reply(self, history: gr.State):
        if isinstance(history, list):
            async for reply in self.__model.stream_chat(history):
                if history[-1]["role"] == "assistant":
                    history[-1]["content"] = reply
                else:
                    history += [{"role": "assistant", "content": reply}]

                yield history
                await asyncio.sleep(0.001) # Let gradio update the textbox.
        else:
            return

    def __empty_history(self, history: gr.State) -> gr.State:
        if isinstance(history, list):
            history = [{"role": "system", "content": self.__prompt}]

        return history

    def __add_user_message(self, history: gr.State, content: str, use_location: bool, user_longitude: float, user_latitude: float):
        history += [{"role": "user", "content": content}]
        if use_location:
            address = self.__location_getter.get_location_name(user_longitude, user_latitude)
            if address is not None:
                history += [{"role": "system", "content": f"[[补充信息]] 用户的位置为：{address}"}]
                use_location = False
        return history, "", use_location, user_longitude, user_latitude


