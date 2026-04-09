import http.server
import socketserver
import sqlite3
import configparser
import logging
import time
import os
import threading
from datetime import datetime, timedelta
from abuseidp_file_downloader import AbuseIPDBDownloader


def is_running_in_docker():
    # Check if /.dockerenv file exists
    if os.path.exists('/.dockerenv'):
        return True

    # Check if environment variable 'DOCKER_CONTAINER' is set
    if os.getenv('DOCKER_CONTAINER'):
        return True

    # Check if '/proc/1/cgroup' file contains '/docker/'
    if os.path.isfile('/proc/1/cgroup'):
        with open('/proc/1/cgroup', 'r') as f:
            for line in f:
                if '/docker/' in line:
                    return True

    # Docker container not detected
    return False


class BlacklistHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/ip_list' or self.path == '/ip_list/':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()

            # Connect to the SQLite database
            conn = sqlite3.connect('abuseipdb.db')
            c = conn.cursor()

            # Query the database to retrieve the IP addresses from the blacklist
            c.execute("SELECT ipAddress FROM blacklist")
            rows = c.fetchall()

            # Close the database connection
            conn.close()

            # Convert the list of tuples to a list of strings
            ip_addresses = [row[0] for row in rows]

            # Convert the IP list to a string
            plain_text_content = "\n".join(ip_addresses)

            self.wfile.write(plain_text_content.encode())
        else:
            # Serve files using the default behavior
            super().do_GET()

    def list_directory(self, path):
        # Disable directory listing
        self.send_error(404, "Directory listing is disabled")


def download_data_periodically(manager, interval_hours):
    while True:
        # Check if the file exists and its last modification time
        if os.path.exists('blacklist.json'):
            last_modified_time = datetime.fromtimestamp(os.path.getmtime('blacklist.json'))
            current_time = datetime.now()
            time_difference = current_time - last_modified_time

            # Check if the time difference is greater than the download interval
            if time_difference.total_seconds() / 3600 >= interval_hours:
                # Download data
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
            # File does not exist, download data
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

        # Sleep for the specified interval before downloading again
        logging.info(f"Waiting for {interval_hours} hours before next download...")
        time.sleep(interval_hours * 3600)


def main():
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger(__name__)
    logger.info("Blacklist Server script started.")

    config = configparser.ConfigParser()
    if is_running_in_docker():
        config_path = '/app/config/config.ini'
    else:
        config_path = 'config.ini'

    if not os.path.exists(config_path):
        print("Error: config.ini file not found.")
        exit()

    config.read(config_path)
    port = int(config['Server']['port'])

    # Initialize AbuseIPDBDownloader
    api_key = config['API']['api_key']
    download_interval_hours = int(config['API']['download_interval_hours'])
    confidence_minimum = int(config['API']['confidence_minimum'])

    print(f"Download Interval: {download_interval_hours} h")
    print(f"confidenceMinimum: {confidence_minimum}")

    manager = AbuseIPDBDownloader(api_key, download_interval_hours, confidence_minimum)

    # Start a thread to download data periodically
    download_thread = threading.Thread(target=download_data_periodically, args=(manager, download_interval_hours))
    download_thread.daemon = True
    download_thread.start()

    # Set up the HTTP server with the custom request handler
    handler = BlacklistHandler
    with socketserver.TCPServer(("", port), handler) as httpd:
        print("Serving at port", port)
        httpd.serve_forever()


if __name__ == "__main__":
    main()
