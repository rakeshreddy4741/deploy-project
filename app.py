from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
import os
import subprocess
import json
from dotenv import load_dotenv
import re
import time

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')
jwt = JWTManager(app)
app.config['JWT_TOKEN_LOCATION'] = ['cookies']
app.config['JWT_ACCESS_COOKIE_NAME'] = 'access_token'
app.config['JWT_COOKIE_CSRF_PROTECT'] = False

# Hardcoded credentials (from .env)
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD')

# Add this near the top of the file with other configurations
PROJECT_PATHS = {
    'portfolio': '/home/rakesh/Documents/Projects/portfolio-web/build.sh',
    # Add more projects and their build script paths
}

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            access_token = create_access_token(identity=username)
            response = redirect(url_for('home'))
            response.set_cookie('access_token', access_token, httponly=True, secure=True)
            return response
        else:
            return render_template('login.html', error="Invalid credentials")
    
    return render_template('login.html')

@app.route('/home')
@jwt_required()
def home():
    try:
        current_user = get_jwt_identity()
        result = subprocess.run(['pm2', 'jlist'], capture_output=True, text=True)
        processes = json.loads(result.stdout)
        
        # Transform the data to match our template
        formatted_processes = []
        for process in processes:
            memory_in_mb = process.get('monit', {}).get('memory', 0) / (1024 * 1024)
            uptime = process.get('pm2_env', {}).get('pm_uptime', 0)
            formatted_process = {
                "id": process.get('pm_id'),
                "name": process.get('name'),
                "status": process.get('pm2_env', {}).get('status', 'unknown'),
                "cpu": process.get('monit', {}).get('cpu', '0'),
                "memory": f"{memory_in_mb:.1f} MB",
                "restarts": process.get('pm2_env', {}).get('restart_time', 0),
                "uptime": format_uptime(uptime)
            }
            formatted_processes.append(formatted_process)
            
        return render_template('home.html', processes=formatted_processes, current_user=current_user)
    except Exception as e:
        print(f"Error: {str(e)}")
        return render_template('home.html', error=str(e), processes=[], current_user=get_jwt_identity())

@app.route('/logout')
def logout():
    response = redirect(url_for('login'))
    response.delete_cookie('access_token')
    return response

def format_uptime(uptime):
    # Calculate uptime duration in seconds
    seconds = int((uptime - time.time() * 1000)) // 1000 if uptime else 0
    seconds = abs(seconds)
    if seconds < 60:
        return f"{seconds} Secs"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes} Mins"
    else:
        hours = seconds // 3600
        return f"{hours} Hrs"

@app.route('/project/<action>/<project_id>', methods=['POST'])
@jwt_required()
def project_action(action, project_id):
    try:
        # Get project name from ID first
        result = subprocess.run(['pm2', 'jlist'], capture_output=True, text=True)
        processes = json.loads(result.stdout)
        project_name = None
        
        # Find project name by ID
        for process in processes:
            if str(process.get('pm_id')) == str(project_id):
                project_name = process.get('name')
                break
                
        if not project_name:
            print(f"Project not found with ID: {project_id}")
            return jsonify({'status': 'error', 'message': 'Project not found'}), 404

        print(f"Executing {action} on project {project_name} (ID: {project_id})")
        
        if action == 'build':
            # Check if build script exists for this project
            build_script = PROJECT_PATHS.get(project_name)
            if not build_script:
                return jsonify({'status': 'error', 'message': f'No build script found for {project_name}'}), 404
                
            # Execute build script
            print(f"Running build script: {build_script}")
            result = subprocess.run(['bash', build_script], capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"Build failed: {result.stderr}")
                return jsonify({'status': 'error', 'message': 'Build failed'}), 500
            
        elif action == 'stop':
            subprocess.run(['pm2', 'stop', project_id])
        elif action == 'start':
            subprocess.run(['pm2', 'start', project_id])
        elif action == 'restart':
            subprocess.run(['pm2', 'restart', project_id])
            
        return jsonify({'status': 'success'})
    except Exception as e:
        print(f"Error in project_action: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True) 