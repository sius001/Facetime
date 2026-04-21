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
