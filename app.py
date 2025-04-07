from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import threading
from datetime import datetime
import pytz  # Add pytz for timezone handling
from pi_flood import run_scheduler

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
socketio = SocketIO(app)

class FloodJob:
    def __init__(self, params):
        self.params = params
        self.status = 'pending'
        self.logs = []
        self.start_time = None
        self.end_time = None

    def log(self, message):
        self.logs.append(message)
        socketio.emit('job_update', {
            'job_id': self.params.get('job_id'),
            'logs': [message],
            'status': self.status
        })

    def run(self):
        self.status = 'running'
        self.start_time = datetime.now()
        self.log("Job started...")
        try:
            run_scheduler(self.params, self.log)
            self.status = 'completed'
            self.log("Job completed successfully! 🎉")
        except Exception as e:
            self.status = 'failed'
            self.log(f"❌ Job failed: {str(e).splitlines()[0]}")
        self.end_time = datetime.now()

jobs = {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/submit', methods=['POST'])
def submit():
    params = request.json
    job_id = datetime.now().strftime('%Y%m%d%H%M%S')
    params['job_id'] = job_id

    # Convert input time to UTC
    try:
        local_time = datetime.strptime(params['scheduled_time'], "%Y-%m-%d %H:%M:%S")
        local_tz = pytz.timezone("Etc/UTC")  # Replace with your local timezone if needed
        utc_time = local_tz.localize(local_time).astimezone(pytz.utc)
        params['scheduled_time'] = utc_time.strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        return jsonify({'error': f"Invalid time format: {str(e)}"}), 400

    job = FloodJob(params)
    jobs[job_id] = job
    
    def run_job():
        job.run()
        socketio.emit('job_update', {
            'job_id': job_id,
            'status': job.status,
            'logs': job.logs
        })

    thread = threading.Thread(target=run_job)
    thread.start()
    
    return jsonify({'job_id': job_id})

@app.route('/status/<job_id>')
def status(job_id):
    if job_id in jobs:
        job = jobs[job_id]
        return jsonify({
            'status': job.status,
            'logs': job.logs
        })
    return jsonify({'error': 'Job not found'}), 404

if __name__ == '__main__':
    socketio.run(app, debug=True)
