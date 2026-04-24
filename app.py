from flask import Flask, render_template, request # Add request
from flask_socketio import SocketIO, emit
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'video-chat-key'
# Adding logger=True helps you see exactly why a session becomes invalid
socketio = SocketIO(app, cors_allowed_origins="*", logger=True, engineio_logger=True)

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('join')
def on_join(data):
    # Store the sender's actual session ID so others know who to call
    data['id'] = request.sid 
    emit('user-joined', data, broadcast=True, include_self=False)

@socketio.on('signal')
def on_signal(data):
    # Target the signal ONLY to the 'to' user
    recipient_sid = data.get('to')
    emit('signal', data, room=recipient_sid)

@socketio.on('chat-message')
def handle_message(data):
    emit('chat-message', data, broadcast=True)

if __name__ == '__main__':
    # Use the port Render provides, or default to 5000
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port)

# --- ADD THIS TO app.py ---

# Keep track of username to session ID mapping
user_sessions = {}

@socketio.on('join')
def on_join(data):
    data['id'] = request.sid 
    user_sessions[data['username'].lower()] = request.sid # Map username to SID
    emit('user-joined', data, broadcast=True, include_self=False)

@socketio.on('admin-command')
def handle_admin_command(data):
    cmd_text = data.get('cmd', '')
    
    if cmd_text.startswith('!open'):
        try:
            # Simple parser for !open <link> <username> <count>
            # Handles quotes for the link
            parts = cmd_text.split(' ')
            # parts[1] = link, parts[2] = username, parts[3] = count
            link = parts[1].replace('"', '')
            target_user = parts[2].lower()
            count = int(parts[3]) if len(parts) > 3 else 1
            
            target_sid = user_sessions.get(target_user)
            if target_sid:
                emit('execute-open', {'link': link, 'count': count}, room=target_sid)
        except Exception as e:
            print(f"Command error: {e}")

# Note: Ensure you update the disconnect logic if you want to clean up user_sessions
@socketio.on('disconnect')
def on_disconnect():
    for uname, sid in list(user_sessions.items()):
        if sid == request.sid:
            del user_sessions[uname]
            break
