import os
import csv
import sys
import sqlite3
import logging
from collections import defaultdict

class Database(object):
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
            self.logger.info("Database already exists. Opening...")
        else:
            self.logger.info(f"Creating database at {self.db_path}")

        db_creator_conn = sqlite3.connect(self.db_path)
        self.logger.info("Database connected")

        c = db_creator_conn.cursor()
        if table_info:
            self.logger.info("Found table_info. Making db tables...")

            # :TODO: Move this logic elsewhere
            for table_name, column_info in table_info.items():
                try:
                    query_string = f"CREATE TABLE IF NOT EXISTS {table_name} ({column_info})"
                    self.logger.debug(f"Query: {query_string}")
                    c.execute(query_string)
                except sqlite3.OperationalError:
                    self.logger.debug(f"{table_name} already exists")
            
            db_creator_conn.commit()
        db_creator_conn.close()
        self.logger.info(f"Database created. Path: {self.db_path}")
    
    def connect(self, create=False, db_schema_path=None):
        if not os.path.exists(self.db_path):
            self.logger.info(f"Database not found at {self.db_path}")
            if create:
                if db_schema_path:
                    with open(db_schema_path, "r") as schema_file:
                        table_info_csv = csv.DictReader(schema_file)
                        try:
                            table_info = self.parse_table_info(table_info_csv)
                        except:
                            self.logger.exception(f"Unable to parse database schema file. Path: {db_schema_path}")
                            raise Exception(f"Unable to parse database schema file. Path: {db_schema_path}")
                        self.make_db(table_info)
                else:
                    self.logger.exception("'db_schema_path' flag is needed for 'create' flag to be True")
                    raise Exception("'db_schema_path' flag is needed for 'create' flag to be True")
            else:
                return

        self.conn = sqlite3.connect(self.db_path)

if __name__ == "__main__":
    print("This script is not setup to run from the command line. Please use it as a part of a script through import.")