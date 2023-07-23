from flask import Flask, request, jsonify, render_template
import json, time
import threading

app = Flask(__name__)

# Define the JSON file name
json_file = "jobs.json"

# Callback when a job is updated
job_update_cb = None

# Load the initial jobs from the JSON file
with open(json_file, 'r') as f:
    jobs_data = json.load(f)

def save_jobs_to_json(jobs):
    # Save the updated jobs to the JSON file
    with open(json_file, 'w') as f:
        json.dump(jobs, f, indent=4)

@app.route('/')
def home():
    # reload data from file
    with open(json_file, 'r') as f:
        jobs_data = json.load(f)
    # Render the home page with the list of jobs
    return render_template('index.html', jobs=jobs_data)

@app.route('/add_job', methods=['POST'])
def add_job():
    print(f"request {request.form}", flush=True)
    print(f"check weekday {request.form.getlist('weekday')}-{bool(request.form.getlist('weekday'))}, weekend {request.form.getlist('weekend')}-{bool(request.form.getlist('weekend'))}", flush=True)
    # Parse job details from the request
    job_name = request.form['name']
    job_time = request.form['time']
    job_parameters = {
        "action1": request.form['action1'],
        "delay": int(request.form['delay']),  # Convert to integer
        "action2": request.form['action2'],
        "weekday": bool(request.form.getlist('weekday')),
        "weekend": bool(request.form.getlist('weekend')),
    }

    # Check if a job with the same name already exists
    existing_job = next((job for job in jobs_data if job['name'] == job_name), None)

    if existing_job:
        # If the job exists, update its time and parameters
        existing_job['time'] = job_time
        existing_job['parameters'] = job_parameters
    else:
        # If the job does not exist, add it to the jobs_data list
        new_job = {
            'name': job_name,
            'time': job_time,
            'parameters': job_parameters
        }
        jobs_data.append(new_job)

    # Save the updated jobs to the JSON file
    save_jobs_to_json(jobs_data)

    if job_update_cb != None:
        job_update_cb()

    # Redirect to the home page after adding the job
    return home()

@app.route('/remove_job', methods=['POST'])
def remove_job():
    # Parse the job name from the request
    job_name = request.form['name']

    # Remove the job from the jobs_data list
    jobs_data[:] = [job for job in jobs_data if job['name'] != job_name]

    # Save the updated jobs to the JSON file
    save_jobs_to_json(jobs_data)

    if job_update_cb != None:
        job_update_cb()

    # Redirect to the home page after removing the job
    return home()

def web_thread(callback = None):
    print(f"set callback {callback}", flush=True)
    if callback != None:
        global job_update_cb
        job_update_cb = callback

    app.run(host='0.0.0.0', port=8080)

def start(callback = None):
    thread = threading.Thread(target=web_thread, args=(callback,))
    thread.start()

if __name__ == "__main__":
    
    web_thread()

    #start(cb)
    while(1):
        time.sleep(10)
