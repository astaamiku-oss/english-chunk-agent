"""Rebuild the standalone Pages site from the original UI and a fresh seed database."""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app import initialize, connect, get_api

out = ROOT / 'docs'
out.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory() as temp:
    db_path = Path(temp) / 'seed.db'
    initialize(db_path)
    with connect(db_path) as db:
        words = get_api(db, '/api/words', {})
        data = {
            'words': [get_api(db, f'/api/words/{w["id"]}', {}) for w in words],
            'chunks': get_api(db, '/api/chunks', {}),
            'meta': get_api(db, '/api/meta', {}),
        }
(out / 'data.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
html = (ROOT / 'static/index.html').read_text().replace('href="/style.css"', 'href="./style.css"').replace('src="/app.js"', 'src="./app.js"')
html = html.replace('<script src="./app.js">', '<script src="./store.js"></script><script src="./app.js">')
html = html.replace('本地示例词库 · 内容待审核', '记录保存在本浏览器 · 内容待审核')
(out / 'index.html').write_text(html)
(out / 'style.css').write_bytes((ROOT / 'static/style.css').read_bytes())
js = (ROOT / 'static/app.js').read_text()
start = js.index('async function api(')
end = js.index('\nfunction run(', start)
js = js[:start] + 'async function api(path,data){return window.chunkStore.api(path,data);}' + js[end:]
(out / 'app.js').write_text(js)
(out / '.nojekyll').touch()
