import requests
import json
import sqlite3
from datetime import datetime, timedelta
import os
import logging
import configparser

class AbuseIPDBDownloader:
    def __init__(self, api_key, download_interval_hours, confidence_minimum):
        self.api_key = api_key
        self.confidence_minimum = confidence_minimum
        self.url = "https://api.abuseipdb.com/api/v2/blacklist"
        self.headers = {
            "Key": self.api_key,
            "Accept": "application/json"
        }
        self.download_interval_hours = download_interval_hours
        self.last_download_time = None  # Initialize last download time to None

        # Configure logging
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)

        # Create file handler
        file_handler = logging.FileHandler('abuseipdb.log')
        file_handler.setLevel(logging.INFO)

        # Create console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # Create formatter and add it to the handlers
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # Add handlers to the logger
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)



    def download_blacklist(self):
        confidence_minimum = self.confidence_minimum
        self.logger.info(f"confidenceMinimum: {confidence_minimum}")
        params = {
            "confidenceMinimum": confidence_minimum
        }

        try:
            response = requests.get(self.url, headers=self.headers, params=params)
            response.raise_for_status()  # Raise an exception for HTTP errors

            if response.status_code == 200:
                self.last_download_time = datetime.now()  # Update last download time
                return response.json()
            else:
                self.logger.error(f"Failed to download blacklist: {response.status_code}")
                return None

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to connect to the AbuseIPDB API: {e}")
            return None

    def is_database_empty(self):
        if not os.path.exists('abuseipdb.db'):
            return True

        conn = sqlite3.connect('abuseipdb.db')
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM blacklist")
        count = c.fetchone()[0]
        conn.close()
        return count == 0

    def save_to_file(self, data, filename):
        with open(filename, 'w') as file:
            json.dump(data, file)

    def process_file_and_save_to_database(self, filename):
        with open(filename, 'r') as file:
            blacklist_data = json.load(file)

        if blacklist_data:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            processed_data = []

            for entry in blacklist_data['data']:
                formatted_entry = [
                    entry['ipAddress'],
                    entry['countryCode'],
                    entry['abuseConfidenceScore'],
                    entry['lastReportedAt'],
                    timestamp
                ]
                processed_data.append(formatted_entry)

            self.save_to_database(processed_data)

    def save_to_database(self, data):
        if not os.path.exists('abuseipdb.db'):
            conn = sqlite3.connect('abuseipdb.db')
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS blacklist
                         (ipAddress TEXT, countryCode TEXT, confidence INTEGER, lastReportedAt TEXT, timestamp TEXT)''')
            conn.commit()
            conn.close()

        conn = sqlite3.connect('abuseipdb.db')
        c = conn.cursor()

        for entry in data:
            c.execute(
                "INSERT INTO blacklist (ipAddress, countryCode, confidence, lastReportedAt, timestamp) VALUES (?, ?, ?, ?, ?)",
                (entry[0], entry[1], entry[2], entry[3], entry[4]))

        conn.commit()
        conn.close()

    def delete_old_data(self):
        conn = sqlite3.connect('abuseipdb.db')
        c = conn.cursor()

        threshold_time = datetime.now() - timedelta(hours=self.download_interval_hours)

        c.execute("DELETE FROM blacklist WHERE timestamp < ?", (threshold_time.strftime("%Y-%m-%d %H:%M:%S"),))

        conn.commit()
        conn.close()

    def create_database(self):
        conn = sqlite3.connect('abuseipdb.db')
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS blacklist
                     (ipAddress TEXT, countryCode TEXT, confidence INTEGER, lastReportedAt TEXT, timestamp TEXT)''')
        conn.commit()
        conn.close()

def main():
    # Set up logging for the main function
    logging.basicConfig(filename='abuseipdb.log', level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s')

    config = configparser.ConfigParser()
    config.read('config.ini')

    if 'API' not in config or 'api_key' not in config['API'] or 'download_interval_hours' not in config['API']:
        logging.error("API key or download interval not found in config.ini")
        return

    api_key = config['API']['api_key']
    download_interval_hours = int(config['API']['download_interval_hours'])
    confidence_minimum = int(config['API']['confidence_minimum'])

    logging.info(f"Download Interval: {download_interval_hours} h")
    logging.info(f"confidenceMinimum: {confidence_minimum}")

    manager = AbuseIPDBDownloader(api_key, download_interval_hours, confidence_minimum)

    # Check if the file exists and its last modification time
    if os.path.exists('blacklist.json'):
        last_modified_time = datetime.fromtimestamp(os.path.getmtime('blacklist.json'))
        current_time = datetime.now()
        time_difference = current_time - last_modified_time

        # Check if the time difference is greater than the download interval
        if time_difference.total_seconds() / 3600 >= download_interval_hours:
            blacklist_data = manager.download_blacklist()

            if blacklist_data:
                manager.save_to_file(blacklist_data, 'blacklist.json')
                logging.info("Blacklist data downloaded to file successfully!")

                manager.process_file_and_save_to_database('blacklist.json')

                if not manager.is_database_empty():
                    manager.delete_old_data()
                    logging.info("Old data deleted successfully!")

            else:
                logging.error("Failed to download blacklist data")
        else:
            logging.info("Not enough time has passed since the last download. Skipping download.")
    else:
        logging.error("blacklist.json file does not exist!")

    if not os.path.exists('abuseipdb.db'):
        logging.error("Database: %s does not exist!" % 'abuseipdb.db')
        manager.create_database()

        if os.path.exists('blacklist.json'):
            manager.process_file_and_save_to_database('blacklist.json')


if __name__ == "__main__":
    main()

