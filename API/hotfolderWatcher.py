import time
import re
import shutil
import sqlite3
import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from rdflib import Graph
from subprocess import Popen, PIPE

g_paths = []
g_items = 0

#########
# STORE #
#########

class RDFStore:

    def __init__(self, dbPath):
        self.graph = Graph(store='BerkeleyDB')
        self.dbPath = dbPath
        self.graph.open(self.dbPath, create=True)

    def close():
        self.graph.close();

#############
# HOTFOLDER #
#############

class HotfolderWatcher:

    def __init__(self, directory, period, staticPath):
        self.observer = Observer()
        self.rdfStore = RDFStore("/tmp/store")
        self.directory = directory
        self.period = period
        self.staticPath = staticPath
        self.configDB = None
        self.saveConfig()

    def saveConfig(self):

        # Create database
        self.configDB = sqlite3.connect('hotfolder.db')

        # Create SQLite config table
        cur = self.configDB.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS `config` (
            `option` VARCHAR(250),
            `value` VARCHAR(250)
        );""")

        # Save hotfolder path
        cur = self.configDB.cursor()
        cur.execute("INSERT INTO config VALUES ('hotfolderPath', '" + self.directory.replace("'", "\\'") + "')")
        self.configDB.commit()
        self.configDB.close()

    def sync(self, paths, items):

        createdPaths = []
        print("[SYNC] Exiftool get RDF output from :")
        for path in paths:
            print("\t| " + path[1])
            if path[0] == 0:
                createdPaths.append(path[1])
        process = Popen(['exiftool', '-X'] + createdPaths, stdout=PIPE)
        (output, err) = process.communicate()
        exit_code = process.wait()
        print("[SYNC] Synchronize " + self.directory +  " hotfolder")
        self.rdfStore.graph.parse(data=output.decode("utf-8"), format="xml")

        # Copy files in static directory
        for file in createdPaths:
            filename = os.path.basename(file)
            if not os.path.isfile(self.staticPath + filename):
                shutil.copyfile(file, self.staticPath + filename)


    def run(self):

        global g_paths
        global g_items

        event_handler = HotfolderHandler()
        self.observer.schedule(event_handler, self.directory, recursive = True)
        self.observer.start()
        try:
            while True:
                time.sleep(self.period)
                items = g_items
                if items > 0 and g_paths != []:
                    self.sync(g_paths, items)
                    g_paths = g_paths[items:]
                    g_items -= items

        except Exception as e:
            self.observer.stop()
            print("Observer Stopped")
            print(e)

        self.observer.join()

class HotfolderHandler(FileSystemEventHandler):

    @staticmethod
    def on_any_event(event):

        global g_paths
        global g_items

        # Inside _paths_ property, first index :
        # 0 => New created file
        # 1 => New modified file
        # 2 => New deleted file
        # second index :
        # This is the absolute path

        if event.is_directory:
            return None
        elif event.event_type == 'created':
            # Event is created, you can process it now
            g_items += 1
            g_paths.append((0, event.src_path))
            print("Watchdog received created event - % s." % event.src_path)
        elif event.event_type == 'modified':
            # Event is modified, you can process it now
            print("Watchdog received modified event - % s." % event.src_path)

########
# MAIN #
########

# Don't forget '/' for the static path
watch = HotfolderWatcher("/tmp/hotfolder", 5, os.path.dirname(__file__) + "/static/")
watch.run()
