from flask import Flask, request, jsonify, render_template, redirect, url_for
import json, time
import threading

class web:
    def __init__(self, data_file, jobs_file):
        self.data_file = data_file
        self.jobs_file = jobs_file
        self.app = Flask(__name__)

        # Callback when a job is updated
        self.job_update_cb = None

        # Load the initial jobs from the JSON file
        with open(self.jobs_file, 'r') as f:
            self.jobs_data = json.load(f)

        # Setup routes
        self.app.route('/')(self.home)
        self.app.route('/add_job', methods=['POST'])(self.add_job)
        self.app.route('/remove_job', methods=['POST'])(self.remove_job)
        self.app.route('/settings')(self.settings)
        self.app.route('/update_data', methods=['POST'])(self.update_data)
        self.app.route('/add_data', methods=['POST'])(self.add_data)
        self.app.route('/remove_data', methods=['POST'])(self.remove_data)

    def save_jobs_to_json(self):
        # Save the updated jobs to the JSON file
        with open(self.jobs_file, 'w') as f:
            json.dump(self.jobs_data, f, indent=4)

    def web_thread(self, callback = None):
        print(f"set callback {callback}", flush=True)
        if callback != None:
            global job_update_cb
            job_update_cb = callback
        self.app.run(host='0.0.0.0', port=8080)

    def start(self, callback = None):
        thread = threading.Thread(target=self.web_thread, args=(callback,))
        thread.start()

    def home(self):
        # reload data from file
        with open(self.jobs_file, 'r') as f:
            jobs_data = json.load(f)

        # Get available commands from data.json
        with open(self.data_file, 'r') as f:
            data = json.load(f)
            commands = [entry['name'] for entry in data if entry['type'] == 'command']
    
        # Render the home page with the list of jobs and commands
        return render_template('index.html', jobs=jobs_data, commands=commands)

    def add_job(self):
        print(f"request {request.form}", flush=True)
        print(f"check weekday {request.form.getlist('weekday')}-{bool(request.form.getlist('weekday'))}, weekend {request.form.getlist('weekend')}-{bool(request.form.getlist('weekend'))}", flush=True)
        # Parse job details from the request
        job_name = request.form['name']
        job_time = request.form['time']
        job_parameters = {
            "action1": request.form.getlist('action1'),
            "delay": int(request.form['delay']),
            "action2": request.form.getlist('action2'),
            "weekday": bool(request.form.getlist('weekday')),
            "weekend": bool(request.form.getlist('weekend')),
        }

        # Check if a job with the same name already exists
        existing_job = next((job for job in self.jobs_data if job['name'] == job_name), None)

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
            self.jobs_data.append(new_job)

        # Save the updated jobs to the JSON file
        self.save_jobs_to_json()

        if job_update_cb != None:
            job_update_cb()

        # Redirect to the home page after adding the job
        return redirect(url_for('home'))

    def remove_job(self):
        # Parse the job name from the request
        job_name = request.form['name']

        # Remove the job from the jobs_data list
        self.jobs_data[:] = [job for job in self.jobs_data if job['name'] != job_name]

        # Save the updated jobs to the JSON file
        self.save_jobs_to_json()

        if job_update_cb != None:
            job_update_cb()

        # Redirect to the home page after removing the job
        return redirect(url_for('home'))

    def settings(self):
        with open(self.data_file, 'r') as f:
            data = json.load(f)
        return render_template('settings.html', data=data)

    def update_data(self):
        data_name = request.form['name']
        data_type = request.form.get('type', 'command')
        
        with open(self.data_file, 'r') as f:
            data = json.load(f)
        
        # Update existing data entry
        for entry in data:
            if entry.get('type') == data_type:
                if data_type == 'command' and data_name == entry['name']:
                    entry['data'] = request.form['data']
                    break
                elif data_type == 'device':
                    entry['settings'] = {
                        'devtype': request.form['devtype'],
                        'host': request.form['host'],
                        'mac': request.form['mac'],
                        'frequency': float(request.form['frequency'])
                    }
                    break
                elif data_type == 'location':
                    entry['settings'] = {
                        'timezone': request.form['timezone'],
                        'lat': float(request.form['lat']),
                        'long': float(request.form['long'])
                    }
                    break
        
        with open(self.data_file, 'w') as f:
            json.dump(data, f, indent=4)
    
        return redirect(url_for('settings'))

    def add_data(self):
        data_name = request.form['name']
        data_value = request.form['data']
        
        with open(self.data_file, 'r') as f:
            data = json.load(f)
        
        # Add new data entry
        data.append({
            'type': 'command',
            'name': data_name,
            'data': data_value
        })
        
        with open(self.data_file, 'w') as f:
            json.dump(data, f, indent=4)
    
        return redirect(url_for('settings'))

    def remove_data(self):
        data_name = request.form['name']
        
        with open(self.data_file, 'r') as f:
            data = json.load(f)
        
        # Remove data entry
        data[:] = [entry for entry in data if entry.get('name') != data_name]
        
        with open(self.data_file, 'w') as f:
            json.dump(data, f, indent=4)
    
        return redirect(url_for('settings'))
