#!/usr/bin/env python3
import argparse
import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from seed import seed

ROOT = Path(__file__).resolve().parent
ABILITIES = ('recognition', 'listening', 'construction', 'retrieval')
TABLES = {'word': 'words', 'sense': 'word_senses', 'chunk': 'chunks'}

def now():
    return datetime.now(timezone.utc)

def stamp(value):
    return value.isoformat(timespec='seconds')

class Connection(sqlite3.Connection):
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()

def connect(path):
    db = sqlite3.connect(path, timeout=10, factory=Connection)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    return db

def initialize(path):
    with connect(path) as db:
        db.executescript((ROOT / 'schema.sql').read_text())
        seed(db, stamp(now()))

class APIError(Exception):
    def __init__(self, message, status=400):
        self.status = status
        super().__init__(message)

def rows(db, sql, args=()):
    return [dict(r) for r in db.execute(sql, args)]

def require_item(db, kind, item_id):
    if kind not in TABLES or type(item_id) is not int or not db.execute(f'SELECT 1 FROM {TABLES[kind]} WHERE id=?', (item_id,)).fetchone():
        raise APIError('学习对象不存在', 404)

def practice(db, data, clock=None):
    kind, item_id = data.get('item_type'), data.get('item_id')
    require_item(db, kind, item_id)
    ability, grade = data.get('ability'), data.get('grade')
    if ability not in ABILITIES or type(grade) is not int or not 0 <= grade <= 3:
        raise APIError('ability 或 grade 无效')
    answer, error = data.get('answer', ''), data.get('error', '')
    if not all(isinstance(x, str) and len(x) <= 4000 for x in (answer, error)):
        raise APIError('answer/error 必须为不超过 4000 字的文本')
    clock = clock or now()
    ts = stamp(clock)
    old = db.execute("SELECT * FROM learning_progress WHERE user_id='local' AND item_type=? AND item_id=?", (kind, item_id)).fetchone()
    previous = old['interval_days'] if old else 0
    interval = 10 / 1440 if grade == 0 else (1 if previous < 1 else previous * {1: 1.2, 2: 2, 3: 2.5}[grade])
    due = stamp(clock + timedelta(days=interval))
    db.execute("INSERT OR IGNORE INTO learning_progress(user_id,item_type,item_id,next_review,updated_at) VALUES('local',?,?,?,?)", (kind, item_id, due, ts))
    db.execute(f"UPDATE learning_progress SET {ability}=?,repetitions=repetitions+1,interval_days=?,next_review=?,updated_at=? WHERE user_id='local' AND item_type=? AND item_id=?", (grade, interval, due, ts, kind, item_id))
    db.execute("INSERT INTO practice_events(user_id,item_type,item_id,ability,grade,answer,error,created_at) VALUES('local',?,?,?,?,?,?,?)", (kind, item_id, ability, grade, answer, error, ts))
    return dict(db.execute("SELECT * FROM learning_progress WHERE user_id='local' AND item_type=? AND item_id=?", (kind, item_id)).fetchone())

def chunk_detail(db, item):
    item['slots'] = json.loads(item['slots'])
    item['senses'] = rows(db, 'SELECT s.*,w.lemma,cs.role FROM chunk_senses cs JOIN word_senses s ON s.id=cs.sense_id JOIN words w ON w.id=s.word_id WHERE cs.chunk_id=?', (item['id'],))
    item['contexts'] = rows(db, 'SELECT cc.*,i.name intent,s.name scenario FROM chunk_contexts cc JOIN intents i ON i.id=cc.intent_id JOIN scenarios s ON s.id=cc.scenario_id WHERE cc.chunk_id=?', (item['id'],))
    return item

def write_chunk(db, data, item_id=None):
    source = data.get('source')
    if not isinstance(source, str) or not source.strip() or len(source)>200:
        raise APIError('必须提供 source（修改来源）')
    before = None
    if item_id is not None:
        before = db.execute('SELECT * FROM chunks WHERE id=?', (item_id,)).fetchone()
        if not before:
            raise APIError('语块不存在',404)
        before = dict(before)
        if type(data.get('version')) is not int or data['version'] != before['version']:
            raise APIError('版本冲突，请重新读取后修改',409)
    fields = {}
    for key in ('expression','meaning_zh','pattern','usage_notes'):
        value = data.get(key, before[key] if before else ('' if key=='usage_notes' else None))
        if not isinstance(value,str) or (key!='usage_notes' and not value.strip()) or len(value)>4000:
            raise APIError('无效字段：'+key)
        fields[key] = value.strip()
    slots = data.get('slots', json.loads(before['slots']) if before else [])
    if not isinstance(slots,list) or not all(isinstance(x,str) and len(x)<=100 for x in slots) or len(slots)>30:
        raise APIError('slots 必须为文本数组（最多 30 项）')
    version = before['version']+1 if before else 1
    ts = stamp(now())
    values = (*fields.values(),json.dumps(slots,ensure_ascii=False),version,ts,source)
    if before:
        db.execute('UPDATE chunks SET expression=?,meaning_zh=?,pattern=?,usage_notes=?,slots=?,version=?,updated_at=?,source=? WHERE id=?',values+(item_id,))
    else:
        item_id = db.execute('INSERT INTO chunks(expression,meaning_zh,pattern,usage_notes,slots,version,updated_at,source) VALUES(?,?,?,?,?,?,?,?)',values).lastrowid
    # 新增时可一次关联义项和语境，失败则整个事务回滚。
    if not before:
        senses = data.get('sense_ids',[])
        contexts = data.get('contexts',[])
        if not isinstance(senses,list) or not isinstance(contexts,list):
            raise APIError('sense_ids/contexts 必须为数组')
        for sid in senses:
            require_item(db,'sense',sid)
            db.execute('INSERT INTO chunk_senses VALUES(?,?,?)',(item_id,sid,'core'))
        for context in contexts:
            if not isinstance(context,dict) or not isinstance(context.get('example'),str) or not context['example'].strip():
                raise APIError('语境需要 example')
            for key,table in [('intent_id','intents'),('scenario_id','scenarios')]:
                if type(context.get(key)) is not int or not db.execute(f'SELECT 1 FROM {table} WHERE id=?',(context[key],)).fetchone():
                    raise APIError('无效语境关联')
            db.execute('INSERT INTO chunk_contexts(chunk_id,intent_id,scenario_id,example) VALUES(?,?,?,?)',(item_id,context['intent_id'],context['scenario_id'],context['example']))
    after = dict(db.execute('SELECT * FROM chunks WHERE id=?',(item_id,)).fetchone())
    db.execute('INSERT INTO audit_log(entity,item_id,source,before_json,after_json,version,created_at) VALUES(?,?,?,?,?,?,?)',('chunk',item_id,source,json.dumps(before,ensure_ascii=False) if before else None,json.dumps(after,ensure_ascii=False),version,ts))
    return chunk_detail(db,after)

def get_api(db,path,q):
    if path == '/api/words':
        return rows(db,'SELECT * FROM words WHERE instr(lower(lemma),lower(?))>0 ORDER BY id',(q.get('q',''),))
    if path.startswith('/api/words/'):
        wid = int(path.rsplit('/',1)[1]); require_item(db,'word',wid)
        word = dict(db.execute('SELECT * FROM words WHERE id=?',(wid,)).fetchone())
        word['senses'] = rows(db,'SELECT * FROM word_senses WHERE word_id=? ORDER BY sense_rank,id',(wid,))
        word['chunks'] = rows(db,'SELECT DISTINCT c.* FROM chunks c JOIN chunk_senses cs ON cs.chunk_id=c.id JOIN word_senses s ON s.id=cs.sense_id WHERE s.word_id=?',(wid,))
        return word
    if path == '/api/chunks':
        sql='SELECT c.* FROM chunks c WHERE (instr(lower(c.expression),lower(?))>0 OR instr(c.meaning_zh,?)>0)'
        args=[q.get('q',''),q.get('q','')]
        for key,column in [('intent_id','intent_id'),('scenario_id','scenario_id')]:
            if q.get(key):
                sql+=f' AND EXISTS(SELECT 1 FROM chunk_contexts cc WHERE cc.chunk_id=c.id AND cc.{column}=?)'; args.append(int(q[key]))
        if q.get('word_id'):
            sql+=' AND EXISTS(SELECT 1 FROM chunk_senses cs JOIN word_senses s ON s.id=cs.sense_id WHERE cs.chunk_id=c.id AND s.word_id=?)'; args.append(int(q['word_id']))
        return [chunk_detail(db,c) for c in rows(db,sql+' ORDER BY c.id',args)]
    if path.startswith('/api/chunks/'):
        cid=int(path.rsplit('/',1)[1]); require_item(db,'chunk',cid)
        return chunk_detail(db,dict(db.execute('SELECT * FROM chunks WHERE id=?',(cid,)).fetchone()))
    if path == '/api/meta':
        return {key:rows(db,'SELECT * FROM '+key) for key in ('intents','scenarios')}
    if path == '/api/progress':
        return rows(db,"SELECT * FROM learning_progress WHERE user_id='local' ORDER BY updated_at DESC")
    if path == '/api/events':
        return rows(db,"SELECT * FROM practice_events WHERE user_id='local' ORDER BY id DESC LIMIT 100")
    if path == '/api/review':
        return rows(db,"SELECT p.*,CASE p.item_type WHEN 'chunk' THEN c.meaning_zh WHEN 'sense' THEN s.definition_zh ELSE w.lemma END prompt FROM learning_progress p LEFT JOIN chunks c ON p.item_type='chunk' AND c.id=p.item_id LEFT JOIN word_senses s ON p.item_type='sense' AND s.id=p.item_id LEFT JOIN words w ON p.item_type='word' AND w.id=p.item_id WHERE p.user_id='local' AND p.next_review<=? ORDER BY p.next_review",(stamp(now()),))
    if path == '/api/stats':
        count=lambda sql: db.execute(sql).fetchone()[0]
        learned=count("SELECT count(DISTINCT word_id) FROM (SELECT item_id word_id FROM learning_progress WHERE item_type='word' UNION SELECT s.word_id FROM learning_progress p JOIN word_senses s ON p.item_type='sense' AND p.item_id=s.id) ")
        return {'target_words':1000,'words':count('SELECT count(*) FROM words'),'reviewed_words':count('SELECT count(*) FROM words WHERE reviewed=1'),'learned_words':learned,'senses':count('SELECT count(*) FROM word_senses'),'chunks':count('SELECT count(*) FROM chunks'),'practiced_chunks':count("SELECT count(*) FROM learning_progress WHERE item_type='chunk'"),'events':count('SELECT count(*) FROM practice_events'),'due':count("SELECT count(*) FROM learning_progress WHERE next_review<='"+stamp(now())+"'"),'abilities':{a:db.execute(f'SELECT avg({a}) FROM learning_progress').fetchone()[0] for a in ABILITIES},'sense_recognition':db.execute("SELECT avg(grade>=2) FROM practice_events WHERE item_type='sense' AND ability='recognition'").fetchone()[0],'chunk_retrieval':db.execute("SELECT avg(grade>=2) FROM practice_events WHERE item_type='chunk' AND ability='retrieval'").fetchone()[0]}
    raise APIError('接口不存在',404)

class Handler(BaseHTTPRequestHandler):
    def send_json(self,status,data):
        body=json.dumps(data,ensure_ascii=False).encode()
        self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(body))); self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        parsed=urlsplit(self.path)
        if parsed.path.startswith('/api/'):
            self.handle_api(parsed)
        elif parsed.path in ('/','/app.js','/style.css'):
            name={'/':'index.html','/app.js':'app.js','/style.css':'style.css'}[parsed.path]
            body=(ROOT/'static'/name).read_bytes()
            self.send_response(200); self.send_header('Content-Type',{'/':'text/html; charset=utf-8','/app.js':'text/javascript; charset=utf-8','/style.css':'text/css; charset=utf-8'}[parsed.path]); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
        else:
            self.send_json(404,{'error':'页面不存在'})

    def do_POST(self):
        self.handle_api(urlsplit(self.path))

    def do_PUT(self):
        self.handle_api(urlsplit(self.path))

    def handle_api(self,parsed):
        try:
            with connect(self.server.db_path) as db:
                if self.command=='GET':
                    result=get_api(db,parsed.path,{k:v[0] for k,v in parse_qs(parsed.query).items()}); status=200
                else:
                    # 浏览器跨站写入保护；本地 Agent 无 Origin 可调用。
                    origin=self.headers.get('Origin')
                    if origin and origin not in {scheme + '://' + self.headers.get('Host', '') for scheme in ('http', 'https')}:
                        raise APIError('拒绝跨站写入',403)
                    if self.headers.get_content_type()!='application/json':
                        raise APIError('需要 application/json',415)
                    size=int(self.headers.get('Content-Length','0'))
                    if not 0<size<=65536: raise APIError('请求大小无效',413)
                    data=json.loads(self.rfile.read(size))
                    if not isinstance(data,dict): raise APIError('请求必须为 JSON 对象')
                    status=200
                    if self.command=='POST' and parsed.path=='/api/practice': result=practice(db,data); status=201
                    elif self.command=='POST' and parsed.path=='/api/chunks': result=write_chunk(db,data); status=201
                    elif self.command=='PUT' and parsed.path.startswith('/api/chunks/'): result=write_chunk(db,data,int(parsed.path.rsplit('/',1)[1]))
                    else: raise APIError('接口不存在',404)
            self.send_json(status,result)
        except APIError as exc: self.send_json(exc.status,{'error':str(exc)})
        except (ValueError,TypeError): self.send_json(400,{'error':'参数或 JSON 格式无效'})
        except sqlite3.IntegrityError: self.send_json(409,{'error':'数据重复或关联约束冲突'})
        except sqlite3.Error: self.send_json(503,{'error':'数据库暂时不可用'})

def create_server(path,host='127.0.0.1',port=8000):
    initialize(path)
    server=ThreadingHTTPServer((host,port),Handler)
    server.db_path=str(path)
    return server

if __name__=='__main__':
    parser=argparse.ArgumentParser(description='英语语块学习')
    parser.add_argument('--port',type=int,default=int(os.environ.get('PORT', '8000')))
    parser.add_argument('--host',default='0.0.0.0',help='默认监听所有网络接口；仅本机可用 127.0.0.1')
    parser.add_argument('--db',default=str(ROOT/'learning.db'))
    args=parser.parse_args()
    server=create_server(args.db,host=args.host,port=args.port)
    print(f'电脑打开 http://127.0.0.1:{server.server_port} （Ctrl+C 停止）',flush=True)
    print(f'监听 {args.host}:{server.server_port}', flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
