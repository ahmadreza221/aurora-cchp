"""Drive Autodesk Fusion from a shell through its local MCP server (Preferences > General > API, http://127.0.0.1:27182/mcp).

  python3 fusion/tools/fusion_mcp.py script FILE.py [--ro]          run a Fusion API script (must define run(_context))
  python3 fusion/tools/fusion_mcp.py asm SECTION [SECTION ...]      run sections of fusion/GR180_Engine_Assembly
        constants of that script can be overridden by env vars: DOC_NAME, VARIANT, ENGINE_DIR, VB_DIR, VC_DIR, VC2_DIR
  python3 fusion/tools/fusion_mcp.py shot DIRECTION OUT.png         screenshot of the active view (iso-top-left, front, ...)
"""
import base64, json, os, re, sys, urllib.request

URL = 'http://127.0.0.1:27182/mcp'
HERE = os.path.dirname(os.path.abspath(__file__))
ASM = os.path.join(HERE, '..', 'GR180_Engine_Assembly', 'GR180_Engine_Assembly.py')


def post(body, sid=None):
    h = {'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream'}
    if sid:
        h['MCP-Session-Id'] = sid
    r = urllib.request.urlopen(urllib.request.Request(URL, json.dumps(body).encode(), h), timeout=900)
    return r.headers.get('MCP-Session-Id'), r.read().decode()


def call(tool, args):
    sid, _ = post(dict(jsonrpc='2.0', id=1, method='initialize',
                       params=dict(protocolVersion='2025-03-26', capabilities={}, clientInfo=dict(name='gr180', version='1'))))
    post(dict(jsonrpc='2.0', method='notifications/initialized'), sid)
    _, t = post(dict(jsonrpc='2.0', id=2, method='tools/call', params=dict(name=tool, arguments=args)), sid)
    return json.loads(t)


def script(src, ro=False):
    obj = dict(script=src)
    if ro:
        obj['readOnly'] = True
    d = call('fusion_mcp_execute', dict(featureType='script', object=obj))
    for c in d.get('result', {}).get('content', []):
        print(c.get('text', c))
    if 'result' not in d:
        print(d)


def asm(sections):
    src = open(ASM, encoding='utf-8').read()
    src = src.replace('SECTIONS = None', 'SECTIONS = %r' % sections, 1)
    for var in ('DOC_NAME', 'VARIANT', 'ENGINE_DIR', 'VB_DIR', 'VC_DIR', 'VC2_DIR'):
        v = os.environ.get(var)
        if v:
            src, n = re.subn(r'^%s = .*$' % var, '%s = %r' % (var, v), src, count=1, flags=re.M)
            assert n, var
    script(src)


def shot(direction, out):
    d = call('fusion_mcp_read', dict(queryType='screenshot', direction=direction, width=1400, height=900))
    for c in d['result']['content']:
        if c.get('data'):
            open(out, 'wb').write(base64.b64decode(c['data'])); print('saved', out)


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'script':
        script(open(sys.argv[2], encoding='utf-8').read(), '--ro' in sys.argv)
    elif cmd == 'asm':
        asm(sys.argv[2:])
    elif cmd == 'shot':
        shot(sys.argv[2], sys.argv[3])
