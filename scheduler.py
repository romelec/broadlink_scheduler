import argparse
import json, schedule
import time, re, datetime, pytz
import threading
import broadlink

from broadlink.const import DEFAULT_PORT
from dateutil import tz
from timezonefinder import TimezoneFinder
from astral import LocationInfo
from astral.sun import sun

from web import web 
scheduler_reset = None

def setup_dev(json_data):
    for itm in json_data:
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

def get_sun(json_data):
    for itm in json_data:
        if itm['type'] == "location":
            itm = itm['settings']
            lat = itm['lat']
            long = itm['long']
            time_zone = tz.gettz(itm['timezone'])

            tf = TimezoneFinder()
            timezone_str = tf.timezone_at(lng=long, lat=lat)
            city = LocationInfo(name="", region="", timezone=time_zone,
                            latitude=lat, longitude=long)
            date = datetime.date.today()
            s = sun(city.observer, date=date, tzinfo=pytz.timezone(timezone_str))
            return s

    print ("Setup sun not found", flush=True)
    return None

def get_signal(json_data, action):
    for itm in json_data:
        if itm['type'] == 'command' and itm['name'] == action:
            data = bytearray.fromhex(''.join(itm['data'])) 
            return data

    print (f"Data not found for '{action}'", flush=True)
    return None

def get_time(job_time, s):
    once = False
    if job_time.startswith("sunset"):
        job_time = s['dusk'] + datetime.timedelta(minutes=extract_time_offset(job_time))
        job_time = job_time.strftime('%H:%M')
        once = True 
    elif job_time.startswith("sunrise"):
        job_time = s['dawn'] + datetime.timedelta(minutes=extract_time_offset(job_time))
        job_time = job_time.strftime('%H:%M')
        once = True 
    return job_time, once

def send_single (device, action):
    if (not action):
        print("Nothing to do", flush=True)
        return

    data = get_signal(action)
    print (f"Send {action}", flush=True)
    if data != None:
        device.send_data(data)

def send_rfdata(device, job):
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
            send_single(device, action)
            time.sleep(0.5)
        # pause
        print(f"Pause {delay}s", flush=True)
        time.sleep(delay)
        # action 2
        for action in action2:
            send_single(device, action)
            time.sleep(0.5)

def learn_rfdata(device, frequency):
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

def read_data_from_json(json_file):
    with open(json_file, 'r') as f:
        data = json.load(f)
    return data

def extract_time_offset(job_time):
    # Extract the numeric value at the end of the string
    match = re.search(r'([-+]?\d+)$', job_time)
    if match:
        time_offset = int(match.group(1))
        if job_time[-1] == '-':
            time_offset *= -1
        return time_offset
    else:
        return 0

def schedule_jobs(jobs, data, device):
    s = get_sun(data)

    for job in jobs:
        # Schedule the job with the specified time and parameters
        job_name = job['name']
        job_time = job['time']
        job_param = job.get('parameters', None)

        job_time, once = get_time(job_time, s)

        print(f"Schedule job '{job_name}' at {job_time}: '{job_param}'")
        schedule.every().day.at(job_time).do(send_rfdata, device, job)

    # Restart scheduler every morning
    schedule.every().day.at("06:00").do(config_update)

def run_scheduler(args):
    global scheduler_reset
    scheduler_reset = threading.Event()

    while True:
        # Read data file and configure the device
        data = read_data_from_json(args.data)
        device = setup_dev(data)

        # Read jobs and configure scheduler
        jobs = read_data_from_json(args.jobs)
        schedule_jobs(jobs, data, device)

        # Run scheduler
        while not scheduler_reset.is_set():
            schedule.run_pending()
            time.sleep(1)

        # Cancel all jobs before exiting
        schedule.clear()
        scheduler_reset.clear()
        print("Scheduler restart", flush=True)


def config_update():
    print("update config -> restart scheduler thread", flush=True)
    global scheduler_reset
    scheduler_reset.set()


def main(argv=None):
    parser = argparse.ArgumentParser(fromfile_prefix_chars='@')
    parser.add_argument("-d", "--data", default='data.json', help="configuration file (signals)")
    parser.add_argument("-j", "--jobs", default='jobs.json', help="jobs list file")
    args = parser.parse_args()

    # Start the webserver
    webserv = web(args.data, args.jobs) 
    webserv.start(config_update)

    # Run the scheduler forever
    run_scheduler(args)


if __name__ == "__main__":
    main(argv=None) 
