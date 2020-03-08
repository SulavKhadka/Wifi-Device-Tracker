import sys
import time
import signal
import sqlite3
import logging
import subprocess
from datetime import datetime, timezone
from functools import partial

import db_creator


def get_devices_on_network():
    nmap = subprocess.Popen(['arp', '-a'], stdout=subprocess.PIPE)
    ipout = nmap.communicate()[0].decode("utf-8")
    
    devices = []
    for i in ipout.strip().split("\n"):
        
        raw_list = i.split(" ")
        try:
            devices.append({
            "AssignedDeviceName" : "",
            "IdentifiedDeviceName": raw_list[0],
            "IpAddress": raw_list[1][1:-1],
            "MacAddress": raw_list[3]
            })
        except Exception as e:
            logger.error(f"Line: {raw_list} \n Error: {e}")
            logger.exception(f"Zoinks!")
    
    return devices


def log_devices(db, commit_frequency=10, scan_time_interval=30):
    
    db.connect(create=True, db_schema_path="db_schema.csv")
    cursor = db.conn.cursor()
    current_log_frequency = 0

    logger.info("Starting network scan...")
    logger.info(f"Commit frequency: {commit_frequency}")
    logger.info(f"Scan-time interval: {scan_time_interval}")

    while True:
        scan_start_time = time.time() # Recording start and stop times for the sleep mechanism below

        timestamp = datetime.now().replace(tzinfo=timezone.utc).timestamp()
        devices = get_devices_on_network()
        logger.info(f"{len(devices)} device(s) found.")

        for device in devices:
            try:
                query_string = f'''INSERT INTO devices(name,arpIdentifiedName,ipAddress,macAddress,timestamp) 
                                    VALUES (?,?,?,?,?);'''
                values = list(device.values())
                values.append(timestamp)
                logger.debug(f"Insert values: {values}")
                
                cursor.execute(query_string, tuple(values))
                logger.debug("Record logged.")
            except Exception as e:
                logger.exception("Unable to execute statement.")
                raise Exception(e)
        
        if current_log_frequency == commit_frequency:
            db.conn.commit()
        current_log_frequency += 1

        scan_end_time = time.time()
        logger.info(f"Scan time: {scan_end_time - scan_start_time}")

        # Sleep mechanism to make sure the device scans happen at the scan_time_interval points
        time_till_scan_time_interval = scan_time_interval - (scan_end_time - scan_start_time)
        if time_till_scan_time_interval > 0:
            time.sleep(time_till_scan_time_interval)

def terminate_handler(self, signum, frame):
    # Graceful exit handling logic
    self.logger.info("Recieved kill signal, Closing database.")
    print("\nRecieved kill signal, Closing database.")
    self.conn.close()
    sys.exit(0)


if __name__ == "__main__":

    # Logging setup
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    file_handler = logging.FileHandler(f"{__name__}.log", mode='a')
    formatter = logging.Formatter('%(asctime)s :: %(filename)s :: %(levelname)s :: %(message)s')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    consoleHandler = logging.StreamHandler(sys.stdout)
    consoleHandler.setLevel(logging.INFO)
    consoleHandler.setFormatter(formatter)
    logger.addHandler(consoleHandler)

    db = db_creator.Database(db_path="network_device_logs.db")
    signal.signal(signal.SIGINT, partial(terminate_handler, db)) # Graceful exit handling call
    log_devices(db, commit_frequency=2, scan_time_interval=20)