import sys
import time
import json
import uuid
import signal
import sqlite3
import logging
import subprocess
from datetime import datetime, timezone
from functools import partial

import db_creator


class DeviceTracker():

    def __init__(self, db_path):
        # Logging setup
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.DEBUG)
        file_name = __file__.split(".")[0]
        file_handler = logging.FileHandler(f"{file_name}.log", mode='a')
        formatter = logging.Formatter('%(asctime)s :: %(filename)s :: %(levelname)s :: %(message)s')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        consoleHandler = logging.StreamHandler(sys.stdout)
        consoleHandler.setLevel(logging.INFO)
        consoleHandler.setFormatter(formatter)
        logger.addHandler(consoleHandler)
        self.logger = logger

        db = db_creator.Database(db_path=db_path)
        db.connect(create=True, db_schema_path="db_schema.csv")
        self.db = db
        self.conn = self.db.conn
        self.cursor = None
        if self.conn is None:
            self.logger.error("Cannot get cursor. self.conn is None.")
            raise Exception("Cannot get cursor. self.conn is None.")
        self.cursor = self.conn.cursor()

        self.device_file = self.load_device_file()

        if self.device_file is not None:
            self.devices = json.load(self.device_file)
        else:
            self.devices = {}

        self.all_devices = {
            "device_correlation" : {},
            "device_ips_set" : set(),
            "device_macs_set" : set()
        }
        

    def load_device_file(self, new=False):
        mode = "w+" if new else "r+"
        try:
            self.device_file = open("devices.json", mode)
        except Exception as e:
            self.logger.debug(f"Error opening file. Error:\n {e}")
            self.logger.info("Unable to open device file. Initializing empty dict")
            self.device_file = None


    def get_devices_on_network(self):
        nmap = subprocess.Popen(['arp', '-a'], stdout=subprocess.PIPE)
        ipout = nmap.communicate()[0].decode("utf-8")
        self.logger.debug(f"nmap output (all): {ipout}")

        devices = []
        for i in ipout.strip().split("\n"):
            add_device = False
            raw_list = i.split(" ")
            self.logger.debug(f"nmap output (single device): {raw_list}")
            # Correlating the device to the db device ID.
            name = self.all_devices.get('device_correlation').get(raw_list[1][1:-1])
            if name is None:
                name = self.all_devices.get('device_correlation').get(raw_list[3])
                if name is None:
                    self.logger.warning(f"Unable to find device id from IP: {raw_list[1][1:-1]} | MAC: {raw_list[3]}.")
                    name = f"device{uuid.uuid4()}"
                    add_device = True

            try:
                device = {
                "AssignedDeviceName" : name,
                "IdentifiedDeviceName": raw_list[0],
                "IpAddress": raw_list[1][1:-1],
                "MacAddress": raw_list[3]
                }

            except Exception as e:
                self.logger.error(f"Line: {raw_list} \n Error: {e}")
                self.logger.exception(f"Zoinks!")

            if add_device:
                self.add_new_device(device)
            
            devices.append(device)
        
        return devices


    def add_device_to_file(self, device):
        device_name = device.get('AssignedDeviceName')
        self.logger.debug(f"Adding {device_name} to file.")

        try:
            self.devices[device_name] = {
                "name": device_name,
                "arpIdentifiedName": device.get('IdentifiedDeviceName'),
                "ipAddress" : device.get('IpAddress'),
                "macAddress" : device.get('MacAddress')
            }
            self.logger.debug(f"{device_name} added to device dict.")
        except:
            self.logger.exception(f"Failed to write {device_name} to dict.")


    def add_device_to_db(self, device):
        device_name = device.get('AssignedDeviceName')
        query_string = f'''INSERT INTO devices (name, arpIdentifiedName, ipAddress, macAddress) 
                            VALUES (?,?,?,?);'''
        values = list(device.values())
        self.logger.debug(f"Insert values: {values}")
        
        try:
            self.cursor.execute(query_string, tuple(values))
            self.logger.debug(f"{device_name} added to db")
        except:
            self.logger.exception(f"Failed to add {device_name} to db.")


    def get_all_devices(self):
        self.logger.debug("getting all devices...")
        query_string = f'''SELECT id,ipAddress,macAddress FROM devices '''       
        self.cursor.execute(query_string)
        devices = self.cursor.fetchall()
        self.logger.debug(f"all devices from db: {devices}")

        self.all_devices['device_correlation'] = {i[1]:i[0] for i in devices}
        self.all_devices['device_correlation'] = {i[2]:i[0] for i in devices}
        self.all_devices['device_ips_set'] = set([i[1] for i in devices])
        self.all_devices['device_macs_set'] = set([i[2] for i in devices])

        self.logger.debug(f"all_devices: {self.all_devices}")


    def add_new_device(self, device):
        self.logger.info("New device found.")
        self.logger.debug(device)

        self.add_device_to_file(device)
        self.add_device_to_db(device)
        self.get_all_devices()


    def log_devices(self, commit_frequency=10, scan_time_interval=30):
        
        total_logs = 0
        current_log_frequency = 0

        self.logger.info("Starting network scan...")
        self.logger.info(f"Commit frequency: {commit_frequency}")
        self.logger.info(f"Scan-time interval: {scan_time_interval}")

        while True:
            scan_start_time = time.time() # Recording start and stop times for the sleep mechanism below

            timestamp = datetime.now().replace(tzinfo=timezone.utc).timestamp()
            devices = self.get_devices_on_network()
            self.logger.info(f"{len(devices)} device(s) found.")
            
            for device in devices:

                try:
                    query_string = f'''INSERT INTO devicelogs (deviceId,timestamp) 
                                        VALUES (?,?);'''
                    values = [device.get('AssignedDeviceName')]
                    values.append(timestamp)
                    self.logger.debug(f"Insert values: {values}")
                    
                    self.cursor.execute(query_string, tuple(values))
                    self.logger.debug("Record logged.")
                except Exception as e:
                    self.logger.exception("Unable to execute statement.")
                    raise Exception(e)
            
            if current_log_frequency == commit_frequency:
                self.logger.info(f"Committing {current_log_frequency} records.")
                self.db.conn.commit()
                current_log_frequency = -1
            current_log_frequency += 1
            total_logs += 1

            scan_end_time = time.time()
            self.logger.info(f"Record #{total_logs}")
            self.logger.info(f"Scan time: {scan_end_time - scan_start_time}")

            # Sleep mechanism to make sure the device scans happen at the scan_time_interval points
            time_till_scan_time_interval = scan_time_interval - (scan_end_time - scan_start_time)
            if time_till_scan_time_interval > 0:
                time.sleep(time_till_scan_time_interval)

def terminate_handler(self, signum, frame):
    # Graceful exit handling logic
    self.logger.info("Recieved kill signal, Closing database.")
    if self.device_file is None:
        self.load_device_file(new=True)
    json.dump(self.devices, self.device_file, indent = 4, sort_keys=True)
    self.device_file.close()
    self.db.conn.commit()
    self.db.conn.close()
    sys.exit(0)


if __name__ == "__main__":
    tracker = DeviceTracker(db_path="network_device_logs.db")
    signal.signal(signal.SIGINT, partial(terminate_handler, tracker)) # Graceful exit handling call
    tracker.log_devices(commit_frequency=5, scan_time_interval=10)