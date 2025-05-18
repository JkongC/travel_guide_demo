import asyncio
import threading
import time
from dataclasses import dataclass

import gradio as gr

from model import Model
from info import AMAPInfoGetter, get_location_js, PreferenceInfoGetter, UserPreference


class ChatInterface:
    @dataclass
    class ClientInfo:
        info_getter: AMAPInfoGetter

    __instance = None
    __initialized = False

    __lock = threading.Lock()

    __client_infos: dict = {}
    __client_last_active: dict = {}

    __last_clean = time.time()

    def __new__(cls, *args, **kwargs):
        if not ChatInterface.__initialized:
            cls.__instance = super().__new__(cls)
            cls.__initialized = True
        return cls.__instance

    def __init__(self, model: Model, stream_output: bool = False, prompt: str = "You are a helpful assistant."):
        if not hasattr(self, "__model"):
            self.__model = model
        if not hasattr(self, "__stream_output"):
            self.__stream_output = stream_output
        if not hasattr(self, "__prompt"):
            self.__prompt = prompt

        if not hasattr(self, "__ui"):
            # Define the interface.
            with gr.Blocks() as gr_ui:
                chatbot = gr.Chatbot(type='messages', resizable=True, render_markdown=True)
                user_input = gr.Textbox(label='Ask anything...')
                use_location_info = gr.Checkbox(label='Tell me your location', value=False)
                fetch_more_data = gr.Checkbox(label='Fetch more data for you, but my reply would be slower', value=False)
                submit_btn = gr.Button("Send")
                clear_btn = gr.Button("Clear history")

                # Saves the conversations.
                history = gr.State([{"role": "system", "content": prompt}])
                user_longitude = gr.Number(visible=False, value=-0.1)
                user_latitude = gr.Number(visible=False, value=-0.1)

                # Add user message to history, then wait for chatbot's reply.
                submit_btn.click(
                    fn=self.__process_input,
                    inputs=[history, user_input, use_location_info, fetch_more_data, user_longitude, user_latitude],
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
                    fn=self.__process_input,
                    inputs=[history, user_input, use_location_info, fetch_more_data, user_longitude, user_latitude],
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

    def __del__(self):
        if ChatInterface.__initialized:
            ChatInterface.__instance = None
            ChatInterface.__initialized = False

    @classmethod
    def instance(cls, *args, **kwargs):
        if not ChatInterface.__initialized:
            ChatInterface.__instance = cls(*args, **kwargs)
            ChatInterface.__initialized = True
        return ChatInterface.__instance

    def launch(self, share: bool = False):
        self.__ui.queue(max_size=100, api_open=False)
        self.__ui.launch(share)

    def __process_input(self,
                        history: gr.State,
                        content: str,
                        use_location: bool,
                        fetch_more_data: bool,
                        user_longitude: float,
                        user_latitude: float,
                        request: gr.Request):
        if request:
            sid = request.session_hash
            if sid not in ChatInterface.__client_infos:
                with ChatInterface.__lock:
                    ChatInterface.__client_infos[sid] = ChatInterface.ClientInfo(info_getter=AMAPInfoGetter())
            ChatInterface.__client_last_active[sid] = time.time()

        if time.time() - ChatInterface.__last_clean > 60:
            ChatInterface.__clean_expired_info()

        if use_location:
            history = ChatInterface.__add_location_info(history, user_longitude, user_latitude, request)
            history = ChatInterface.__add_weather_info(history, request)
            history = ChatInterface.__add_date_time_info(history, request)

        history = ChatInterface.__add_user_message(history, content)

        if fetch_more_data:
            pref = PreferenceInfoGetter.get_preference(self.__model, content)
            history = ChatInterface.__add_poi_info(history, pref, request)

        return history, "", use_location, user_longitude, user_latitude

    # Wait for chatbot's reply until it's completely finished.
    def __wait_for_reply(self, history: gr.State) -> gr.State:
        if isinstance(history, list):
            answer = self.__model.normal_chat(history)
            history += [{"role": "assistant", "content": answer}]

        return history

    # Update chatbot's reply in a streaming manner.
    async def __wait_for_stream_reply(self, history: gr.State):
        try:
            if isinstance(history, list):
                async for reply in self.__model.stream_chat(history):
                    if history[-1]["role"] == "assistant":
                        history[-1]["content"] = reply
                    else:
                        history += [{"role": "assistant", "content": reply}]

                    yield history
                    await asyncio.sleep(0.001)  # Let gradio update the textbox.
            else:
                return
        except asyncio.CancelledError:
            raise

    def __empty_history(self, history: gr.State) -> gr.State:
        if isinstance(history, list):
            history = [{"role": "system", "content": self.__prompt}]

        return history

    @staticmethod
    def __add_user_message(history: gr.State,content: str):
        history += [{"role": "user", "content": content}]
        return history

    @staticmethod
    def __add_location_info(history: gr.State,
                            user_longitude: float,
                            user_latitude: float,
                            request: gr.Request):
        info_getter = ChatInterface.__client_infos[request.session_hash].info_getter
        if (address := info_getter.get_location_name()) is None:
            address = info_getter.get_location_name(user_longitude, user_latitude)
        if address is not None:
            history += [{"role": "system", "content": f"[[补充信息]] 用户的位置为：{address}"}]

        return history

    @staticmethod
    def __add_weather_info(history: gr.State, request: gr.Request):
        info_getter = ChatInterface.__client_infos[request.session_hash].info_getter
        data = info_getter.get_weather_info()
        if data is not None:
            weather_prompt = f"[[补充信息]] 用户位置的天气为：{data.weather}，气温为：{data.temperature}，" \
                             f"风向为：{data.wind_direction}，风力为：{data.wind_power}，湿度为：{data.humidity}"
            history += [{"role": "system", "content": weather_prompt}]

        return history

    @staticmethod
    def __add_date_time_info(history: gr.State, request: gr.Request):
        info_getter = ChatInterface.__client_infos[request.session_hash].info_getter
        data = info_getter.get_date_time_info()
        if data is not None:
            dt_prompt = f"[辅助信息] 用户的日期和时间（格式%Y-%m-%d %H-%M-%S）为：{data}"
            history += [{"role": "system", "content": dt_prompt}]

        return history

    @staticmethod
    def __add_poi_info(history: gr.State, pref: UserPreference, request: gr.Request):
        info_getter = ChatInterface.__client_infos[request.session_hash].info_getter
        if pref.poi_name is not None:
            if (pois := info_getter.get_keyword_info(pref)) is not None:
                poi_prompt = "[辅助信息] 与用户询问的地点相关的poi如下："
                for poi_str in pois:
                    poi_prompt += poi_str
                history += [{"role": "system", "content": poi_prompt}]
                print(poi_prompt)

        return history

    @staticmethod
    def __clean_expired_info():
        if ChatInterface.__instance is not None:
            expired = [sid for sid, last
                       in ChatInterface.__client_last_active.items()
                       if last - time.time() > 600]
            for sid in expired:
                with ChatInterface.__lock:
                    if sid in ChatInterface.__client_infos:
                        del ChatInterface.__client_infos[sid]
                    del ChatInterface.__client_last_active[sid]

