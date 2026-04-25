from flask import Flask, render_template, request, Response
from flask_socketio import SocketIO, emit
import os
import re
import requests  # <--- This fixes the NameError
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlencode

app = Flask(__name__)
app.config['SECRET_KEY'] = 'video-chat-key'
socketio = SocketIO(app, cors_allowed_origins="*", logger=True, engineio_logger=True)

# Mapping of username -> session_id
user_sessions = {}

@app.route('/')
def index():
    return render_template('index.html')

# --- PROXY ROUTE FOR THE BROWSER TAB ---
@app.route('/proxy')
def proxy():
    url = request.args.get('url')
    if not url: return "No URL provided", 400
    if not url.startswith('http'): url = 'https://' + url

    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'}
        resp = requests.get(url, headers=headers, timeout=10)
        
        # Only rewrite if the content is HTML
        if 'text/html' in resp.headers.get('Content-Type', ''):
            soup = BeautifulSoup(resp.content, 'html.parser')
            
            # Find all tags with links (scripts, images, links, etc.)
            for tag in soup.find_all(lambda t: t.has_attr('src') or t.has_attr('href')):
                attr = 'src' if tag.has_attr('src') else 'href'
                original_url = tag[attr]
                
                # Turn relative paths (/_Incapsula...) into absolute ones (https://pokemon.com/...)
                full_url = urljoin(url, original_url)
                
                # Rewrite the link to route through your proxy again
                # This ensures sub-resources aren't blocked by the local network
                tag[attr] = f"/proxy?{urlencode({'url': full_url})}"
            
            content = soup.encode()
        else:
            content = resp.content

        # Strip security headers
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection', 
                            'x-frame-options', 'content-security-policy', 'strict-transport-security']
        headers = [(name, value) for (name, value) in resp.raw.headers.items()
                   if name.lower() not in excluded_headers]

        return Response(content, resp.status_code, headers)
        
    except Exception as e:
        return f"Proxy Error: {str(e)}", 500

# --- SOCKET.IO LOGIC ---
@socketio.on('join')
def on_join(data):
    sid = request.sid
    username = data.get('username')
    user_sessions[username] = sid
    data['id'] = sid 
    emit('user-joined', data, broadcast=True, include_self=False)

@socketio.on('signal')
def on_signal(data):
    recipient_sid = data.get('to')
    emit('signal', data, room=recipient_sid)

@socketio.on('chat-message')
def handle_message(data):
    emit('chat-message', data, broadcast=True)

@socketio.on('admin-command')
def handle_admin(data):
    cmd_text = data.get('command', '')
    
    # !open command
    open_match = re.search(r'!open\s+["\']?([^"\s]+)["\']?\s+(\S+)', cmd_text)
    if open_match:
        url = open_match.group(1)
        target_user = open_match.group(2)
        if target_user in user_sessions:
            emit('force-redirect', {'url': url}, room=user_sessions[target_user])

    # !type command
    type_match = re.search(r'!type\s+["\']?([^"\']+)["\']?\s+(\S+)(?:\s+(\d+))?', cmd_text)
    if type_match:
        sequence = type_match.group(1)
        target_user = type_match.group(2)
        delay = int(type_match.group(3)) if type_match.group(3) else 0
        if target_user in user_sessions:
            emit('remote-type', {'sequence': sequence, 'delay': delay}, room=user_sessions[target_user])

    # !kick command
    kick_match = re.search(r'!kick\s+(\S+)', cmd_text)
    if kick_match:
        target_user = kick_match.group(1)
        if target_user in user_sessions:
            emit('force-kick', {}, room=user_sessions[target_user])

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port)
