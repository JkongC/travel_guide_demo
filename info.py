import datetime
import json
import threading
import time
from dataclasses import dataclass

import pytz
import requests
from timezonefinder import TimezoneFinder

from model import Model


def get_location_js() -> str:
    return """
    async function (history, user_input, use_location_info, fetch_more_data, user_longitude, user_latitude) {
        let geoLocation = null;
        
        if (use_location_info === true) {
            const getPosition = new Promise((resolve, reject) => {
                if ("geolocation" in navigator) {
                    navigator.geolocation.getCurrentPosition(
                        pos => resolve({longitude: pos.coords.longitude, latitude: pos.coords.latitude}), 
                        err => resolve(null),
                        { enableHighAccuracy: true }
                    );
                } else {
                    use_location_info = false;
                    resolve(null);
                }
            });
        
            geoLocation = await getPosition;
            if (geoLocation === null) {
                use_location_info = false;
            } else {
                user_longitude = geoLocation.longitude;
                user_latitude = geoLocation.latitude;
            }
        }
        
        return [history, user_input, use_location_info, fetch_more_data, user_longitude, user_latitude];
    }
    """


@dataclass
class WeatherData:
    weather: str
    temperature: str
    wind_direction: str
    wind_power: str
    humidity: str

@dataclass
class LocationData:
    longitude: float
    latitude: float

@dataclass
class UserPreference:
    poi_type: str | None
    poi_name: str | None
    scope: str | None
    distance: float | None

class AMAPInfoGetter:
    __key = None
    __lock = threading.Lock()

    __time_last_update = 0

    @staticmethod
    def init_key():
        with AMAPInfoGetter.__lock:
            if AMAPInfoGetter.__key is None:
                try:
                    with open('amap_key.txt', 'r') as f:
                        AMAPInfoGetter.__key = f.readline().strip()
                except FileNotFoundError:
                    print("AMAP key not found! Please check if amap_key.txt exists!")
                    raise

    def __init__(self):
        self.__location_cache = None
        self.__location_name_cache = None
        self.__adcode_cache = None

        self.__weather_cache = None

        self.__date_time_cache = None

    def get_location(self):
        if self.__location_cache is None:
            return None
        else:
            return self.__location_cache

    def get_location_name(self, longitude: float | None = None, latitude: float | None = None) -> str | None:
        if longitude is None and latitude is None:
            if self.__location_name_cache is not None:
                return self.__location_name_cache
            else:
                return None

        self.__location_cache = LocationData(longitude, latitude)
        url = f"https://restapi.amap.com/v3/geocode/regeo?key={self.__key}&location={longitude},{latitude}"
        response = requests.get(url)
        data = response.json()
        if data['status'] != '1':
            return None
        self.__adcode_cache = data['regeocode']['addressComponent']['adcode']
        self.__location_name_cache = data['regeocode']['formatted_address']
        return self.__location_name_cache

    @staticmethod
    def get_adcode(location: str) -> str | None:
        url = f"https://restapi.amap.com/v3/geocode/geo?key={AMAPInfoGetter.__key}&address={location}"
        response = requests.get(url)
        data = response.json()
        if data['status'] != '1':
            return None
        return data['geocodes']['adcode']

    def get_weather_info(self):
        if self.__weather_cache is not None:
            return self.__weather_cache

        if self.__adcode_cache is None:
            return None

        url = f"https://restapi.amap.com/v3/weather/weatherInfo?key={self.__key}&city={self.__adcode_cache}&extensions=base"
        response = requests.get(url)
        data = response.json()
        if data['status'] != '1':
            return None

        self.__weather_cache = WeatherData(weather=data['lives'][0]['weather'],
                                          temperature=data['lives'][0]['temperature_float'],
                                          wind_direction=data['lives'][0]['winddirection'],
                                          wind_power=data['lives'][0]['windpower'],
                                          humidity=data['lives'][0]['humidity_float'])

        return self.__weather_cache

    def get_date_info(self) -> str | None:
        if self.__try_update_date_time():
            return f"{self.__date_time_cache.strftime('%Y-%m-%d')}"

        return None

    def get_time_info(self) -> str | None:
        if self.__try_update_date_time():
            return f"{self.__date_time_cache.strftime('%H:%M:%S')}"

        return None

    def get_date_time_info(self) -> str | None:
        if self.__try_update_date_time():
            return f"{self.__date_time_cache.strftime('%Y-%m-%d %H:%M:%S')}"

        return None

    def __try_update_date_time(self) -> bool:
        if self.__location_cache is not None and time.time() - self.__time_last_update > 60:
            self.__time_last_update = time.time()
            tf = TimezoneFinder()
            tz_str = tf.timezone_at(lng=self.__location_cache.longitude, lat=self.__location_cache.latitude)
            tz = pytz.timezone(tz_str)
            self.__date_time_cache = datetime.datetime.now(tz=tz)

            return True

        return False

    def get_keyword_info(self, pref: UserPreference) -> list[str] | None:
        if pref.scope is not None:
            adcode = AMAPInfoGetter.get_adcode(pref.scope)
            url = f"https://restapi.amap.com/v5/place/text?key={AMAPInfoGetter.__key}&keywords={pref.poi_name}&region={adcode}"
        else:
            if self.__location_cache is None:
                return None
            url = (f"https://restapi.amap.com/v5/place/around?key={AMAPInfoGetter.__key}&keywords={pref.poi_name}"
                   f"&location={self.__location_cache.longitude},{self.__location_cache.latitude}&radius={int(pref.distance)}")

        response = requests.get(url)
        data = response.json()
        if data['status'] != '1':
            return None

        pois = []
        for i, poi in enumerate(data['pois']):
            pois.append(f"[{i+1}]名称：{poi['name']}，类型：{poi['type']}，"
                        f"地区：{poi['adname']}，地址：{poi['address']} ")

        return pois


class PreferenceInfoGetter:
    __prompt: dict

    def __init__(self):
        pass

    @staticmethod
    def get_preference(model: Model, user_input: str) -> UserPreference:
        history = [PreferenceInfoGetter.__prompt, {"role": "user", "content": user_input}]
        obj = json.loads(model.normal_chat(history))
        ret = UserPreference(poi_type=obj["poi_type"],
                             poi_name=obj["poi_name"],
                             scope=obj["scope"],
                             distance=obj["distance"])
        return ret

    @staticmethod
    def init_prompt():
        try:
            with open("parser_prompt.txt", "r", encoding="utf-8") as f:
                PreferenceInfoGetter.__prompt = {"role": "system", "content": f.read()}
        except FileNotFoundError:
            print("Parser prompt not found! Please check if parser_prompt.txt exists!")
            raise

AMAPInfoGetter.init_key()
PreferenceInfoGetter.init_prompt()
