import asyncio

import gradio as gr
from model import Model


class ChatInterface:
    def __init__(self, model: Model, stream_output: bool = False):
        self.__model = model
        self.__stream_output = stream_output

        # Define the interface.
        with gr.Blocks() as gr_ui:
            chatbot = gr.Chatbot(type='messages', resizable=True, render_markdown=True)
            user_input = gr.Textbox(label='Ask anything...')
            submit_btn = gr.Button("Send")
            clear_btn = gr.Button("Clear history")

            # Saves the conversations.
            history = gr.State([])

            # Add user message to history, then wait for chatbot's reply.
            submit_btn.click(
                fn=ChatInterface.__add_user_message,
                inputs=[history, user_input],
                outputs=[chatbot, user_input],
                queue=False
            ).then(
                fn=self.__wait_for_stream_reply if self.__stream_output else self.__wait_for_reply,
                inputs=history,
                outputs=chatbot
            )

            # Same. This is to support pressing Enter to send messages.
            user_input.submit(
                fn=ChatInterface.__add_user_message,
                inputs=[history, user_input],
                outputs=[chatbot, user_input],
                queue=False
            ).then(
                fn=self.__wait_for_stream_reply if self.__stream_output else self.__wait_for_reply,
                inputs=history,
                outputs=chatbot
            )

            clear_btn.click(
                fn=ChatInterface.__empty_history,
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

    @staticmethod
    def __empty_history(history: gr.State) -> gr.State:
        if isinstance(history, list):
            history.clear()

        return history

    @staticmethod
    def __add_user_message(history: gr.State, content: str) -> tuple[gr.State, str]:
        history += [{"role": "user", "content": content}]
        return history, ""

