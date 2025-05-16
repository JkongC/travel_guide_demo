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

class LocationInfoGetter:
    def __init__(self):
        try:
            with open('amap_key.txt', 'r') as f:
                self.__key = f.readline().strip()
        except FileNotFoundError:
            print("AMAP key not found! Please check if amap_key.txt exists!")
            raise

    def get_location_name(self, longitude: float, latitude: float) -> str | None:
        url = f"https://restapi.amap.com/v3/geocode/regeo?key={self.__key}&location={longitude},{latitude}"
        response = requests.get(url)
        data = response.json()
        if data['status'] != '1':
            return None
        return data['regeocode']['formatted_address']
