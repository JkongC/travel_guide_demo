from dataclasses import dataclass

import requests

def get_location_js() -> str:
    return """
    async function (history, user_input, use_location_info, user_longitude, user_latitude) {
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
        
        return [history, user_input, use_location_info, user_longitude, user_latitude];
    }
    """

class AMAPInfoGetter:
    @dataclass
    class WeatherData:
        weather: str
        temperature: str
        wind_direction: str
        wind_power: str
        humidity: str

    def __init__(self):
        try:
            with open('amap_key.txt', 'r') as f:
                self.__key = f.readline().strip()
        except FileNotFoundError:
            print("AMAP key not found! Please check if amap_key.txt exists!")
            raise

        self.__location_cache = None
        self.__adcode_cache = None

    def get_location_name(self, longitude: float | None = None, latitude: float | None = None) -> str | None:
        if longitude is None and latitude is None:
            if self.__location_cache is not None:
                return self.__location_cache
            else:
                return None

        url = f"https://restapi.amap.com/v3/geocode/regeo?key={self.__key}&location={longitude},{latitude}"
        response = requests.get(url)
        data = response.json()
        if data['status'] != '1':
            return None
        self.__adcode_cache = data['regeocode']['addressComponent']['adcode']
        return data['regeocode']['formatted_address']

    def get_weather_info(self):
        if self.__adcode_cache is None:
            return None

        url = f"https://restapi.amap.com/v3/weather/weatherInfo?key={self.__key}&city={self.__adcode_cache}&extensions=base"
        response = requests.get(url)
        data = response.json()
        if data['status'] != '1':
            return None

        data = AMAPInfoGetter.WeatherData(weather=data['lives'][0]['weather'],
                                          temperature=data['lives'][0]['temperature_float'],
                                          wind_direction=data['lives'][0]['winddirection'],
                                          wind_power=data['lives'][0]['windpower'],
                                          humidity=data['lives'][0]['humidity_float'])

        return data

