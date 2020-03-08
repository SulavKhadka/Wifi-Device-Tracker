import os
import csv
import sqlite3
from pprint import pprint
from collections import defaultdict

class Database(object):
    def __init__(self, db_path):
        self.db_path = db_path
        self.table_info = None
        self.conn = None


    def parse_table_info(self, table_info_csv) -> defaultdict:

        table_headers = defaultdict(str)
        previous_table_name = ""
        for counter, line in enumerate(table_info_csv):
            if previous_table_name != line["table_name"]:
                counter = 0

            if counter == 0:
                table_headers[line["table_name"]] += f'{line["column_name"]} {line["column_type"]}'
            else:
                table_headers[line["table_name"]] += f', {line["column_name"]} {line["column_type"]}'

            previous_table_name = line["table_name"]
            
        return table_headers
    
    def make_db(self, table_info=None):

        if os.path.exists(self.db_path):
            print("Database already exists. Opening...") # :TODO: log this
        else:
            print(f"Creating database at {self.db_path}")

        db_creator_conn = sqlite3.connect(self.db_path)
        print("Database connected")

        c = db_creator_conn.cursor()
        if table_info:
            print("Found table_info. Making db tables...")

            # :TODO: Move this logic elsewhere
            for table_name, column_info in table_info.items():
                try:
                    query_string = f"CREATE TABLE IF NOT EXISTS {table_name} ({column_info})"
                    print(query_string)
                    c.execute(query_string)
                except sqlite3.OperationalError:
                    print(f"{table_name} already exists")
            
            db_creator_conn.commit()
        db_creator_conn.close()
    
    def connect(self, create=False, db_schema_path=None):
        if not os.path.exists(self.db_path):
            print(f"Database not found at {self.db_path}") # :TODO: log this
            if create:
                if db_schema_path:
                    with open(db_schema_path, "r") as schema_file:
                        table_info_csv = csv.DictReader(schema_file)
                        try:
                            table_info = self.parse_table_info(table_info_csv)
                        except:
                            raise Exception(f"Unable to parse database schema file. Path: {db_schema_path}")
                        self.make_db(table_info)
                else:
                    raise Exception("'db_schema_path' flag is needed for 'create' flag to be True")
            else:
                return

        self.conn = sqlite3.connect(self.db_path)

if __name__ == "__main__":
    print("This script is not setup to run from the command line. Please use it as a part of a script through import.")