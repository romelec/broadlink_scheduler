import socket
from flask import Flask, request, jsonify, render_template, redirect, url_for
import json, time
import threading
import broadlink

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
        self.app.route('/discover_devices', methods=['POST'])(self.discover_devices)
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
        self.app.run(host='::', port=8080)
        #self.app.run(host='0.0.0.0', port=8080)

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
        try:
            original_name = request.form.get('original_name')
            new_name = request.form['name']
            
            delay = request.form.get('delay', '0')
            delay = int(delay) if delay else 0

            job = {
                "name": new_name,
                "time": request.form['time'],
                "enabled": 'enabled' in request.form,
                "parameters": {
                    "action1": request.form.getlist('action1'),
                    "delay": delay,
                    "action2": request.form.getlist('action2'),
                    "weekday": 'weekday' in request.form,
                    "weekend": 'weekend' in request.form
                }
            }

            # If editing an existing job, update it in place
            if original_name:
                for i, existing_job in enumerate(self.jobs_data):
                    if existing_job['name'] == original_name:
                        self.jobs_data[i] = job
                        break
            else:
                # Add new job at the end
                self.jobs_data.append(job)
        
            # Save the updated jobs to the JSON file
            self.save_jobs_to_json()

            if self.job_update_cb is not None:
                self.job_update_cb()

            return redirect(url_for('home'))
        except Exception as e:
            print(f"Error adding/updating job: {e}", flush=True)
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
    
    def discover_devices(self):
        try:
            print("Starting device discovery...", flush=True)
            
            # Try discovering on local subnet
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            print(f"Local IP: {local_ip}", flush=True)
            devices = broadlink.discover(timeout=5, local_ip_address=local_ip)
            device_list = []
            print(f"Found {len(devices)} devices", flush=True)
            
            for device in devices:
                try:
                    print(f"Found device: type={hex(device.devtype)}, host={device.host[0]}", flush=True)
                    device_list.append({
                        'devtype': hex(device.devtype),
                        'host': device.host[0],
                        'mac': ':'.join(format(x, '02x') for x in device.mac)
                    })
                except Exception as e:
                    print(f"Error processing device: {e}", flush=True)
        
            # If no devices found, add the currently connected device
            if len(device_list) == 0 and self.device is not None:
                print("No new devices found, adding current device", flush=True)
                device_list.append({
                    'devtype': hex(self.device.devtype),
                    'host': self.device.host[0],
                    'mac': ':'.join(format(x, '02x') for x in self.device.mac)
                })
            
            return jsonify({
                'success': True,
                'devices': device_list
            })
        except Exception as e:
            print(f"Discovery error: {str(e)}", flush=True)
            return jsonify({
                'success': False,
                'message': str(e)
            })

    def update_data(self):
        try:
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
                
            # Check if this is an AJAX request
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': True, 'message': 'Settings updated successfully'})
            else:
                return redirect(url_for('settings'))
                
        except Exception as e:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': str(e)})
            else:
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
