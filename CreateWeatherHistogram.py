import re
import datetime
import requests
import json
import csv
import argparse
import logging
import time
import os
import matplotlib.pyplot as plt

class WeatherHistogram:
    def __init__(self, input, output, bucket_count):
        self.input_file = input
        self.output_file = output
        self.bucket_count = bucket_count
        self.data = ''
        self.date = ''
        self.ip_addresses = set()
        self.ip_locations = {}
        self.temperatures = []
        self.weather_key = ""
        self.darksky_key = ""
        self.visualcrossing_key = ""
        self.darksky_limit_reached = False
        self.visualcrossing_limit_reached = False
        self.current_vc_api_call_count = 0
        self.max_limit_calls = 950
        self.api_calls_available = True
        self.api_lookup_failures = 0
        self.invalid_ips = set()
        self.logger_setup()
        self.get_date()
        self.read_files()
        self.get_keys()
        self.get_ips()
        self.read_vc_limit_date()

    ''' Configures the logger. '''
    def logger_setup(self):
        logging.basicConfig(
        	filename='output.log',
        	level=logging.DEBUG,
        	filemode='w',
        	format='%(asctime)s: %(levelname)s - %(message)s',
        	datefmt='%d-%b-%y %H:%M:%S')

    ''' Reads in data from input file and cached ip address info. '''
    def read_files(self):
        try:
            with open(self.input_file) as file:
                self.data = file.read()
        except FileNotFoundError:
            logging.critical("Input file was not found - please ensure file exists.\n", exc_info=True)
            exit()
        try:
            with open("ip_locations.txt", 'r') as file:
                self.ip_locations = json.load(file)
        except:
            logging.info('Previously cached locations not found - now proceeding with location search.\n')

    ''' Retrieves API keys. '''
    def get_keys(self):
        with open("api_keys.json", "r") as file:
            keys = json.load(file)
            self.weather_key = keys['weather']
            self.darksky_key = keys['darksky']
            self.visualcrossing_key = keys['visualcrossing']

    ''' Gets tomorrow's date to use for retrieving the forecast. '''
    def get_date(self):
        # Initially retrieved the dates from the input files.
        # match = re.search(r'\d{4}-\d{2}-\d{2}', self.data[0])
        # dateObject = datetime.strptime(match.group(), '%Y-%m-%d').date()
        # self.date = str(dateObject)

        # Get tomorrow's Date:
        tmr = datetime.date.today() + datetime.timedelta(days=1)
        self.date = tmr.strftime("%s")

    ''' Stores today's date so we don't make any Visual Crossing API calls until it's at least a day from now. '''
    def store_vc_limit_date(self):
        with open("VC_limit_date.txt", 'w') as file:
            file.write(str(datetime.date.today()))

    ''' Checks if the daily API limit has been refreshed by comparing today's date with the stored date. '''
    def read_vc_limit_date(self):
        date = ""
        if not os.path.exists('VC_limit_date.txt'):
            date = 'empty'
        else:
            with open('VC_limit_date.txt', 'r') as file:
                line = file.readline()
                date = datetime.datetime.strptime(line, "%Y-%m-%d")
        # If today isn't at least 1 day after the stored date, then it's still too soon to make any calls.
        if date != 'empty' and datetime.date.today() <= date.date():
            logging.error(f"Visual Crossing API limit has already been reached today.\n")
            self.visualcrossing_limit_reached = True

    ''' Finds all ip addresses located within the input file. '''
    def get_ips(self):
        octet = r'(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)'
        pattern=re.compile(r"\b(?!10\.|192\.168\.|172\.(?:1[6-9]|2[0-9]|3[01])\.){0}(?:\.{0}){{3}}\b".format(octet))
        self.ip_addresses = set(pattern.findall(self.data))

    ''' Retrieves the latitude/longitude for a ip address. '''
    def get_location(self, ip):
        BASE_URL = 'http://api.weatherapi.com/v1/ip.json'
        query = {'key':self.weather_key, 'q':ip}
        response = requests.get(BASE_URL, params=query)
        if response.status_code == 200:
            location = {'lat':str(response.json()['lat']), 'lon':str(response.json()['lon'])}
            return location
        elif response.status_code == 429:
            logging.warning("Weather API 60 calls/minute reached. Taking a break...\n")
            time.sleep(61)
            return self.get_location(ip)
        else:
            self.api_lookup_failures += 1
            self.invalid_ips.add(ip)
            logging.error(f"Error Code {response.status_code}: {ip} is a invalid ip address.\n")
            return {}

    ''' Caches the info found on ip addresses. '''
    def write_ip_locations_file(self):
        with open('ip_locations.txt', 'w') as outfile:
            json.dump(self.ip_locations, outfile, indent=4, sort_keys=True)

    ''' Makes an API call for each ip address if not already previously found and caches them. '''
    def store_ip_location(self):
        logging.info('Searching for locations...\n')
        for ip in self.ip_addresses:
            if ip not in self.ip_locations:
                location = self.get_location(ip)
                if location:
                    self.ip_locations[ip] = location
                    self.ip_locations[ip]['temperature'] = 0
        self.write_ip_locations_file()

    ''' Uses DarkSky API to find the forecast. '''
    def use_darksky_api(self, lat, lon):
        BASE_URL = f'https://api.darksky.net/forecast/{self.darksky_key}/'
        EXCLUDE = '?exclude=currently,minutely,hourly,alerts,flags'
        REQUEST_URL = f"{BASE_URL}{lat},{lon},{self.date}{EXCLUDE}"
        response = requests.get(REQUEST_URL)
        if response.status_code == 200:
            forecast = response.json()['daily']['data'][0]['temperatureHigh']
            return forecast
        elif response.status_code == 403:
            logging.error(f"Error Code {response.status_code}: DarkSky API limit reached.\n")
            self.darksky_limit_reached = True
            return None

    ''' Uses Visual Crossing API to find the forecast. '''
    def use_visualcrossing_api(self, lat, lon):
        if self.current_vc_api_call_count > self.max_limit_calls:
            logging.warning("Visual Crossing API limit reached.\n")
            self.visualcrossing_limit_reached = True
            return None
        self.current_vc_api_call_count += 1
        REQUEST_URL = f'https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/{lat}%2C{lon}/today?unitGroup=us&key={self.visualcrossing_key}'
        response = requests.get(REQUEST_URL)
        if response.status_code == 200:
            forecast = response.json()['days'][0]['tempmax']
            return forecast
        elif response.status_code == 400:
            self.store_vc_limit_date()
            self.visualcrossing_limit_reached = True
            logging.error(f"Error Code {response.status_code}: Visual Crossing API limit reached.\n")
            return None

    ''' Retrieves forecast through the next available API. '''
    def get_temperature(self, lat, lon):
        temperature = None
        if not self.darksky_limit_reached:
            temperature = self.use_darksky_api(lat, lon)
            if temperature is None:
                temperature = self.use_visualcrossing_api(lat, lon)
        elif not self.visualcrossing_limit_reached:
            temperature = self.use_visualcrossing_api(lat, lon)
        elif self.darksky_limit_reached and self.visualcrossing_limit_reached:
            self.api_calls_available = False
        return temperature

    ''' Retrieves either the cached temperature or makes an API call for it. '''
    def store_temperature(self):
        logging.info('Searching for the forecast...\n')
        temperatures = []
        for ip in self.ip_locations:
            if self.api_calls_available and self.ip_locations[ip]['temperature'] == 0:
                lat = self.ip_locations[ip]['lat']
                lon = self.ip_locations[ip]['lon']
                temp = self.get_temperature(lat, lon)
            else:
                temp = self.ip_locations[ip]['temperature']
            if temp is not None and temp != 0:
                temperatures.append(temp)
                self.ip_locations[ip]['temperature'] = temp
        self.temperatures = temperatures
        self.write_ip_locations_file()

    ''' Creates the tsv file containing the frequency table from the histogram plot. '''
    def write_tsv_file(self):
        self.store_ip_location()
        self.store_temperature()
        if len(set(self.temperatures)) == 1:
            logging.critical("Could not complete histogram file due to API limits being reached. Try again tomorrow.\n")
            return
        n, bins, patches = plt.hist(self.temperatures, bins = self.bucket_count)
        with open(self.output_file, 'w') as outfile:
            tsv_writer = csv.writer(outfile, delimiter='\t')
            tsv_writer.writerow(['bucketMin', 'bucketMax', 'Count'])
            for bin in range(self.bucket_count):
                if bin != 0:
                    tsv_writer.writerow([bins[bin-1], bins[bin], n[bin]])
                else:
                    tsv_writer.writerow(['0', bins[bin], n[bin]])
        logging.info('Histogram file complete!\n')
        print(f"Total API Lookup Failures: {self.api_lookup_failures}")
        print(f"Invalid IP Addresses: {self.invalid_ips}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str, default="./histogram_input")
    parser.add_argument("--output", type=str, default="./histogram.tsv")
    parser.add_argument("--bucket-count", type=int, default=5)
    args = parser.parse_args()
    temphisto = WeatherHistogram(args.input, args.output, args.bucket_count)
    temphisto.write_tsv_file()

if __name__ == "__main__":
    main()
