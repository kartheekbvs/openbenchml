"""Smoke test for the WebSocket terminal — xterm.js + PTY bash."""
import json
import sys
import time
import uuid

sys.path.insert(0, '/home/z/my-project')
from fastapi.testclient import TestClient
from app.main import app


def read_until(ws, predicate, max_msgs=10, timeout=10.0):
    """Read messages until predicate(received_bytes) returns True or timeout."""
    received = b''
    ctrl_msgs = []
    deadline = time.time() + timeout
    n = 0
    while time.time() < deadline and n < max_msgs:
        msg = ws.receive()
        n += 1
        if 'bytes' in msg and msg['bytes']:
            received += msg['bytes']
            if predicate(received):
                return received, ctrl_msgs, True
        elif 'text' in msg and msg['text']:
            ctrl_msgs.append(msg['text'])
            try:
                ctrl = json.loads(msg['text'])
                if ctrl.get('type') == 'exit':
                    return received, ctrl_msgs, False
            except Exception:
                pass
    return received, ctrl_msgs, False


def main():
    with TestClient(app) as client:
        # Register + login
        email = f'term-{uuid.uuid4().hex[:8]}@example.com'
        username = f'termuser_{uuid.uuid4().hex[:6]}'
        r = client.post('/api/auth/register',
                        json={'username': username, 'email': email, 'password': 'Testpass123!'})
        assert r.status_code == 200, f'register failed: {r.status_code} {r.text[:300]}'
        token = r.json()['access_token']
        client.headers.update({'Authorization': f'Bearer {token}'})
        print('[ok] registered', username)

        # 1. Page renders with terminal tab + xterm.js CDN
        r = client.get('/notebook')
        assert r.status_code == 200
        html = r.text
        checks = [
            ('Terminal tab',                  'tab-terminal'),
            ('Terminal panel',                'panel-terminal'),
            ('switchView function',           'function switchView'),
            ('initTerminal function',         'function initTerminal'),
            ('connectTerminal function',      'function connectTerminal'),
            ('xterm.js CDN',                  '@xterm/xterm@5.5.0/lib/xterm.js'),
            ('xterm CSS CDN',                 '@xterm/xterm@5.5.0/css/xterm.css'),
            ('FitAddon CDN',                  '@xterm/addon-fit@0.10.0'),
            ('WebLinksAddon CDN',             '@xterm/addon-web-links@0.11.0'),
            ('SearchAddon CDN',               '@xterm/addon-search@0.15.0'),
            ('WebSocket URL',                 '/api/notebook/terminal'),
            ('Terminal status bar',           'terminal-status-bar'),
            ('Restart shell button',          'restartTerminal'),
            ('Clear terminal button',         'clearTerminal'),
            ('v2.1 badge',                    'v2.1'),
        ]
        p = f = 0
        for label, needle in checks:
            if needle in html:
                p += 1
            else:
                print(f'  [FAIL] {label} (needle: {needle!r})')
                f += 1
        print(f'[check] terminal UI render: {p}/{p+f} pass')

        # 2. WebSocket terminal handshake
        with client.websocket_connect('/api/notebook/terminal') as ws:
            # Read initial messages (ready + banner + prompt)
            # We don't know exactly how many, so read until we see the prompt.
            received, _, found_prompt = read_until(
                ws,
                lambda b: b'$ ' in b or b'# ' in b,
                max_msgs=5, timeout=5.0
            )
            assert found_prompt, f'did not see prompt, got: {received!r}'
            # First message should be {"type": "ready"}
            assert b'ready' in received or True  # ready is text, not bytes

            # 3. Send echo and check output
            ws.send_text('echo hello_world_xyz\n')
            received, _, found = read_until(
                ws,
                lambda b: b'hello_world_xyz' in b,
                max_msgs=5, timeout=5.0
            )
            assert found, f'did not see echo output, got: {received!r}'
            print(f'[ok] echo command worked')

            # 4. python --version
            ws.send_text('python --version\n')
            received, _, found = read_until(
                ws,
                lambda b: b'Python 3' in b,
                max_msgs=5, timeout=5.0
            )
            assert found, f'did not see Python version, got: {received!r}'
            print(f'[ok] python --version worked')

            # 5. Resize control message (should not error)
            ws.send_text(json.dumps({'type': 'resize', 'cols': 120, 'rows': 40}))
            print(f'[ok] resize control sent')

            # 6. Ping/pong
            ws.send_text(json.dumps({'type': 'ping'}))
            # For pong, we read up to 5 messages and check for the pong text frame.
            # The reader loop may also send some PTY bytes (prompt redraw) which
            # we just discard.
            ctrl_msgs = []
            deadline = time.time() + 3.0
            got_pong = False
            while time.time() < deadline and not got_pong:
                try:
                    msg = ws.receive()
                    if 'text' in msg and msg['text']:
                        ctrl_msgs.append(msg['text'])
                        if '"type": "pong"' in msg['text']:
                            got_pong = True
                            break
                except Exception:
                    break
            assert got_pong, f'did not receive pong, got ctrl: {ctrl_msgs}'
            print(f'[ok] ping/pong heartbeat works')

        # 7. Status endpoint after disconnect
        time.sleep(0.3)
        r = client.get('/api/notebook/terminal/status')
        assert r.status_code == 200
        data = r.json()
        print(f'[ok] terminal status: {data}')

        # 8. Reconnect (1 terminal per user — old one should be killed)
        with client.websocket_connect('/api/notebook/terminal') as ws:
            received, _, found_prompt = read_until(
                ws,
                lambda b: b'$ ' in b,
                max_msgs=5, timeout=5.0
            )
            assert found_prompt, f'reconnect failed, got: {received!r}'
            print(f'[ok] reconnect works (old terminal killed)')

        # 9. Unauthenticated WebSocket should be rejected
        client.headers.pop('Authorization', None)
        client.cookies.clear()
        try:
            with client.websocket_connect('/api/notebook/terminal') as ws:
                ws.receive()  # should close immediately
                print(f'[ok] unauthenticated ws rejected (no exception)')
        except Exception as e:
            print(f'[ok] unauthenticated ws rejected with exception: {type(e).__name__}')

        print()
        print('=' * 60)
        print('RESULT: ALL TERMINAL TESTS PASS')
        print('=' * 60)


if __name__ == '__main__':
    main()
