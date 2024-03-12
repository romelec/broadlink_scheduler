import json
import schedule
import datetime, time, re
import threading

import broadlink
from broadlink.const import DEFAULT_PORT
from broadlink.exceptions import ReadError, StorageError
from dateutil import tz
from datetime import datetime, timedelta, time, timezone
from suntime import Sun, SunTimeException

import web

json_data_file = "data.json"
json_jobs_file = "jobs.json"

scheduler_reset = None
json_data = None
device = None

sun = None
time_zone = None

def setup_dev(json_data):
    for itm in json_data:
        if itm['name'] == "device":
            devtype = int(itm['devtype'], 0)
            host = itm['host']
            mac = bytearray.fromhex(itm['mac'])

            print(f"Setup {devtype}, {host}, {mac}", flush=True)
            dev = broadlink.gendevice(devtype, (host, DEFAULT_PORT), mac)
            dev.auth()
            return dev

    print ("Setup data not found", flush=True)
    return None

def setup_sun(json_data):
    global time_zone
    for itm in json_data:
        if itm['name'] == "location":
            lat = itm['lat']
            long = itm['long']
            time_zone = tz.gettz(itm['timezone'])

            sun = Sun(lat, long)
            return sun

    print ("Setup sun not found", flush=True)
    return None

def get_signal(action):
    for itm in json_data:
        if itm['name'] == action:
            data = bytearray.fromhex(''.join(itm['data'])) 
            return data

    print (f"Data not found for '{action}'", flush=True)
    return None

def send_single (action):
    if (not action):
        print("Nothing to do", flush=True)
        return

    data = get_signal(action)
    print (f"Send {action}", flush=True)
    if data != None:
        device.send_data(data)

def send_irdata(job_name, job_param):
    print(f"Running '{job_name}' with parameters: {job_param}", flush=True)
    action1 = re.split(r',\s*', job_param['action1'])
    action2 = re.split(r',\s*', job_param['action2'])
    delay = job_param['delay']
    weekday = job_param['weekday']
    weekend = job_param['weekend']

    # Execute depending of the day
    week = datetime.datetime.today().isoweekday()
    if (weekday and week <= 5) or (weekend and week > 5):
        # action 1
        for action in action1:
            send_single(action)
            time.sleep(0.5)
        # pause
        print(f"Pause {delay}s", flush=True)
        time.sleep(delay)
        # action 2
        for action in action2:
            send_single(action)
            time.sleep(0.5)

def read_data_from_json(json_file):
    with open(json_file, 'r') as f:
        data = json.load(f)
    return data

def schedule_jobs(jobs):
    for job in jobs:
        # Schedule the job with the specified time and parameters
        job_name = job['name']
        job_time = job['time']
        job_param = job.get('parameters', None)

        if job_time == "sunset":
            job_time = sun.get_sunset_time(time_zone=time_zone).strftime('%H:%M')
        elif job_time == "sunrise":
            job_time = sun.get_sunrise_time(time_zone=time_zone).strftime('%H:%M')

        print(f"Schedule job '{job_name}' at {job_time}: '{job_param}'")
        schedule.every().day.at(job_time).do(send_irdata, job_name, job_param)

    # Restart scheduler every morning
    schedule.every().day.at("07:00").do(config_update)

def run_scheduler(interval=1):
    global scheduler_reset
    scheduler_reset = threading.Event()

    global json_data
    global device
    global sun

    # Read data file and configure the device
    json_data = read_data_from_json(json_data_file)
    device = setup_dev(json_data)
    sun = setup_sun(json_data)

    # Read jobs and configure scheduler
    jobs = read_data_from_json(json_jobs_file)
    schedule_jobs(jobs)

    # Run scheduler
    while not scheduler_reset.is_set():
        schedule.run_pending()
        time.sleep(interval)
    
    # Cancel all jobs before exiting
    schedule.clear()
    print("Scheduler stopped", flush=True)


def config_update():
    print("update config -> restart scheduler thread", flush=True)
    global scheduler_reset
    scheduler_reset.set()


def main():
    # Start the webserver
    web.start(config_update)

    # Run the scheduler forever
    while(1):
        run_scheduler()


if __name__ == "__main__":
    main()
