from flask import Flask, request, jsonify, render_template, redirect, url_for
import json, time
import threading

class web:
    def __init__(self, data_file, jobs_file, device, job_update_cb, update_device_cb):
        self.data_file = data_file
        self.jobs_file = jobs_file
        self.device = device
        self.app = Flask(__name__)

        # Callback when a job is updated
        self.job_update_cb = job_update_cb
        self.update_device_cb = update_device_cb

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
        self.app.route('/learn_command', methods=['POST'])(self.learn_command)
        self.app.route('/toggle_job', methods=['POST'])(self.toggle_job)

    def save_jobs_to_json(self):
        # Save the updated jobs to the JSON file
        with open(self.jobs_file, 'w') as f:
            json.dump(self.jobs_data, f, indent=4)

    def web_thread(self):
        self.app.run(host='0.0.0.0', port=8080)

    def start(self):
        thread = threading.Thread(target=self.web_thread)
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
        enabled = bool(request.form.getlist('enabled'))
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
            existing_job['enabled'] = enabled
            existing_job['parameters'] = job_parameters
        else:
            # If the job does not exist, add it to the jobs_data list
            new_job = {
                'name': job_name,
                'time': job_time,
                'enabled': enabled,
                'parameters': job_parameters
            }
            self.jobs_data.append(new_job)

        # Save the updated jobs to the JSON file
        self.save_jobs_to_json()

        if self.job_update_cb is not None:
            self.job_update_cb()

        # Redirect to the home page after adding the job
        return redirect(url_for('home'))

    def remove_job(self):
        # Parse the job name from the request
        job_name = request.form['name']

        # Remove the job from the jobs_data list
        self.jobs_data[:] = [job for job in self.jobs_data if job['name'] != job_name]

        # Save the updated jobs to the JSON file
        self.save_jobs_to_json()

        if self.job_update_cb is not None:
            self.job_update_cb()

        # Redirect to the home page after removing the job
        return redirect(url_for('home'))
    
    def toggle_job(self):
        job_name = request.form['name']
        
        # Find and update the job's enabled status
        for job in self.jobs_data:
            if job['name'] == job_name:
                job['enabled'] = not job.get('enabled', True)
                break
        
        self.save_jobs_to_json()
        
        if self.job_update_cb is not None:
            self.job_update_cb()
    
        return redirect(url_for('home'))

    def settings(self):
        with open(self.data_file, 'r') as f:
            data = json.load(f)
        return render_template('settings.html', data=data)

    def update_data(self):
        data_name = request.form.get('name', '')
        data_type = request.form.get('type', '')
        
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

        if data_type == 'device' and self.update_device_cb is not None:
            self.device = self.update_device_cb()
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

    def learn_command(self):
        name = request.form['name']
        if not name:
            return jsonify({"success": False, "message": "Command name is required"})

        if self.device is None:
            return jsonify({"success": False, "message": "Device not initialized"})

        # Get frequency from device settings
        with open(self.data_file, 'r') as f:
            data = json.load(f)
            frequency = next((item['settings']['frequency'] for item in data if item['type'] == "device"), None)

        if not frequency:
            return jsonify({"success": False, "message": "Device frequency not found"})

        try:
            print(f"Learning RF command '{name}' at {frequency}Hz...", flush=True)
            self.device.find_rf_packet(frequency)
            time.sleep(5)  # Wait for signal
            data = self.device.check_data()
            
            if data is None:
                return jsonify({"success": False, "message": "No RF signal received"})

            # Convert data to hex string
            hex_data = ''.join(format(x, '02x') for x in data)

            # Add new command to data.json
            with open(self.data_file, 'r') as f:
                json_data = json.load(f)

            json_data.append({
                "name": name,
                "type": "command",
                "data": hex_data
            })

            with open(self.data_file, 'w') as f:
                json.dump(json_data, f, indent=4)

            return jsonify({"success": True, "message": f"Command '{name}' learned successfully"})

        except Exception as e:
            return jsonify({"success": False, "message": f"Error learning command: {str(e)}"})
