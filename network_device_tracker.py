import sys
import time
import signal
import sqlite3
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
            print("Uh Oh! Something is wrong with this line.")
            print(f"Line: {raw_list} \n Error: {e}")
    
    return devices


def log_devices(db, commit_frequency=10, scan_time_interval=30):
    
    db.connect(create=True, db_schema_path="db_schema.csv")
    cursor = db.conn.cursor()
    current_log_frequency = 0

    while True:
        scan_start_time = time.time() # Recording start and stop times for the sleep mechanism below

        timestamp = datetime.now().replace(tzinfo=timezone.utc).timestamp()
        devices = get_devices_on_network()

        for device in devices:
            try:
                query_string = f'''INSERT INTO devices(name,arpIdentifiedName,ipAddress,macAddress,timestamp) 
                                    VALUES (?,?,?,?,?);'''
                values = list(device.values())
                values.append(timestamp)
                
                print(f"Values: {values}") #:TODO: Log this
                cursor.execute(query_string, tuple(values))
                print("Record logged.") #:TODO: Log this
            except Exception as e:
                print(f"Unable to execute statement.")
                raise Exception(e)

        scan_end_time = time.time()
        
        # Sleep mechanism to make sure the device scans happen at the scan_time_interval points
        time_till_scan_time_interval = scan_time_interval - (scan_end_time - scan_start_time)
        if time_till_scan_time_interval > 0:
            time.sleep(time_till_scan_time_interval)
        
        if current_log_frequency == commit_frequency:
            db.conn.commit()
        current_log_frequency += 1

        print(f"scan time: {time.time() - scan_start_time}") #:TODO: log this


def terminate_handler(self, signum, frame):
    # Graceful exit handling logic
    print("\nRecieved kill signal, Closing database.")
    self.conn.close()
    sys.exit(0)


if __name__ == "__main__":
    db = db_creator.Database(db_path="network_device_logs.db")
    signal.signal(signal.SIGINT, partial(terminate_handler, db)) # Graceful exit handling call
    log_devices(db, commit_frequency=2, scan_time_interval=20)