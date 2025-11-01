import argparse
import json, schedule
import time, re, datetime, pytz
import threading
import broadlink

from broadlink.const import DEFAULT_PORT
from astral import LocationInfo
from astral.sun import sun
from web import web 

class Scheduler:
    def __init__(self, data_file, jobs_file):
        self.data_file = data_file
        self.jobs_file = jobs_file
        self.json_data = self.read_data_from_json(self.data_file)
        self.json_jobs = self.read_data_from_json(self.jobs_file)
        self.suntime = self.get_sun()
        self.device = None
        self.scheduler_reset = threading.Event()
        if not self.setup_device():
            print("Failed to initialize device, will try later", flush=True)
        
    def setup_device(self):
        with open(self.data_file, 'r') as f:
            data = json.load(f)
            for item in data:
                if item['type'] == "device":
                    settings = item['settings']
                    devtype = int(settings['devtype'], 0)
                    host = settings['host']
                    # Clean the MAC address string before converting to hex
                    mac_str = settings['mac'].replace(':', '').strip()
                    try:
                        mac = bytearray.fromhex(mac_str)
                        self.device = broadlink.gendevice(devtype, (host, DEFAULT_PORT), mac)
                        self.device.auth()
                    except Exception as e:
                        print(f"Failed to setup device: {e}", flush=True)
                        self.device = None
                        return False
                    return True
        return False

    def run(self):
        while not self.device and not self.setup_device():
            print("Failed to initialize device, try agin", flush=True)
            time.sleep(10)

        while True:
            # Update data from files
            self.json_data = self.read_data_from_json(self.data_file)
            self.json_jobs = self.read_data_from_json(self.jobs_file)
            self.schedule_jobs()

            # Run scheduler
            while not self.scheduler_reset.is_set():
                schedule.run_pending()
                time.sleep(1)

            # Cancel all jobs before exiting
            schedule.clear()
            self.scheduler_reset.clear()
            print("Scheduler restart", flush=True)

    def setup_dev(self):
        for itm in self.json_data:
            if itm['type'] == "device":
                itm = itm['settings']
                devtype = int(itm['devtype'], 0)
                host = itm['host']
                mac = bytearray.fromhex(itm['mac'])

                print(f"Setup {devtype}, {host}, {mac}", flush=True)
                dev = broadlink.gendevice(devtype, (host, DEFAULT_PORT), mac)
                dev.auth()
                return dev

        print ("Setup data not found", flush=True)
        return None

    def get_sun(self):
        for itm in self.json_data:
            if itm['type'] == "location":
                itm = itm['settings']
                lat = itm['lat']
                long = itm['long']
                time_zone = itm['timezone']

                tzinfo=pytz.timezone(time_zone)
                city = LocationInfo(name="", region="", timezone=time_zone,
                                latitude=lat, longitude=long)
                date = datetime.date.today()
                s = sun(city.observer, date=date, tzinfo=tzinfo)
                return s

        print ("Setup sun not found", flush=True)
        return None

    def get_signal(self, action):
        for itm in self.json_data:
            if itm['type'] == 'command' and itm['name'] == action:
                data = bytearray.fromhex(''.join(itm['data'])) 
                return data

        print (f"Data not found for '{action}'", flush=True)
        return None

    def get_time(self, job_time):
        once = False
        if job_time.startswith("sunset"):
            job_time = self.suntime['dusk'] + datetime.timedelta(minutes=self.extract_time_offset(job_time))
            job_time = job_time.strftime('%H:%M')
            once = True 
        elif job_time.startswith("sunrise"):
            job_time = self.suntime['dawn'] + datetime.timedelta(minutes=self.extract_time_offset(job_time))
            job_time = job_time.strftime('%H:%M')
            once = True 
        return job_time, once

    def send_single (self, action):
        if (not action):
            print("Nothing to do", flush=True)
            return

        data = self.get_signal(action)
        print (f"Send {action}", flush=True)
        if data != None:
            self.device.send_data(data)

    def send_rfdata(self, job):
        job_name = job['name']
        job_time = job['time']
        job_param = job.get('parameters', None)
        print(f"Running '{job_name}' with parameters: {job_param}", flush=True)
        action1 = job_param['action1']
        action2 = job_param['action2']
        delay = job_param['delay']
        weekday = job_param['weekday']
        weekend = job_param['weekend']

        # Execute depending of the day
        week = datetime.datetime.today().isoweekday()
        if (weekday and week <= 5) or (weekend and week > 5):
            # action 1
            for action in action1:
                self.send_single(action)
                time.sleep(0.5)
            # pause
            print(f"Pause {delay}s", flush=True)
            time.sleep(delay)
            # action 2
            for action in action2:
                self.send_single(action)
                time.sleep(0.5)

    def learn_rfdata(self, device, frequency):
        print(f"Entering learning mode. Please send the RF signal now...", flush=True)
        device.find_rf_packet(frequency)
        time.sleep(5)  # Wait for the signal to be received
        data = device.check_data()
        if data is not None:
            print(f"RF signal learned: {data}", flush=True)
            return data
        else:
            print("No RF signal received.", flush=True)
            return None

    def read_data_from_json(self, json_file):
        with open(json_file, 'r') as f:
            data = json.load(f)
        return data

    def extract_time_offset(self, job_time):
        # Extract the numeric value at the end of the string
        match = re.search(r'([-+]?\d+)$', job_time)
        if match:
            time_offset = int(match.group(1))
            if job_time[-1] == '-':
                time_offset *= -1
            return time_offset
        else:
            return 0

    def schedule_jobs(self):
        for job in self.json_jobs:
            # Schedule the job with the specified time and parameters
            job_name = job['name']
            job_time = job['time']
            enabled = job.get('enabled', True)
            if not enabled:
                print(f"Job '{job_name}' is disabled, skipping scheduling.", flush=True)
                continue
            job_param = job.get('parameters', None)

            job_time, once = self.get_time(job_time)

            print(f"Schedule job '{job_name}' at {job_time}: '{job_param}'", flush=True)
            schedule.every().day.at(job_time).do(self.send_rfdata, job)

        # Restart scheduler every morning to update the sunrise/sunset times
        schedule.every().day.at("04:00").do(self.reschedule)

    def reschedule(self):
        print("Rescheduling jobs...", flush=True)
        self.suntime = self.get_sun()
        self.scheduler_reset.set()

    def update_jobs(self):
        print("update jobs -> restart scheduler thread", flush=True)
        self.scheduler_reset.set()

    def update_device(self):
        print("update broadlink device", flush=True)
        self.json_data = self.read_data_from_json(self.data_file)
        del self.device
        if self.setup_device():
            print("Device updated", flush=True)
            return self.device
        return None

def main(argv=None):
    parser = argparse.ArgumentParser(fromfile_prefix_chars='@')
    parser.add_argument("-d", "--data", default='data.json', help="configuration file (signals)")
    parser.add_argument("-j", "--jobs", default='jobs.json', help="jobs list file")
    args = parser.parse_args()

    scheduler = Scheduler(args.data, args.jobs)

    # Start web server with initialized device
    web_server = web(args.data, args.jobs, scheduler.device, scheduler.update_jobs, scheduler.update_device)
    web_server.start()

    scheduler.run()


if __name__ == "__main__":
    main()
