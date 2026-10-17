import json
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path
import app

class AppTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'test.db'
        app.initialize(self.path)
        self.db=app.connect(self.path)
    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()
    def test_seed_idempotent_and_relations(self):
        app.initialize(self.path)
        self.assertEqual(self.db.execute('SELECT count(*) FROM words').fetchone()[0],20)
        self.assertEqual(len(app.get_api(self.db,'/api/words/1',{})['senses']),4)
        chunks=app.get_api(self.db,'/api/chunks',{'word_id':'3'})
        self.assertTrue(any(len(c['senses'])>1 for c in chunks))
        self.assertEqual(self.db.execute('PRAGMA foreign_key_check').fetchall(),[])
    def test_schedule_history_and_independent_abilities(self):
        t=datetime(2026,1,1,tzinfo=timezone.utc)
        data={'item_type':'chunk','item_id':1,'ability':'retrieval','grade':2}
        p=app.practice(self.db,data,t)
        self.assertEqual(p['next_review'],app.stamp(t+timedelta(days=1)))
        p=app.practice(self.db,data,t+timedelta(days=1))
        self.assertEqual(p['interval_days'],2)
        p=app.practice(self.db,{**data,'ability':'construction','grade':0},t)
        self.assertEqual(p['next_review'],app.stamp(t+timedelta(minutes=10)))
        self.assertEqual(p['retrieval'],2)
        self.assertEqual(p['construction'],0)
        self.assertIsNone(p['listening'])
        self.assertEqual(self.db.execute('SELECT count(*) FROM practice_events').fetchone()[0],3)
        self.db.commit()
        with app.connect(self.path) as other:
            self.assertEqual(app.get_api(other,'/api/stats',{})['events'],3)
    def test_invalid_practice_and_due(self):
        for fields in [{'grade':4},{'grade':True},{'ability':'sql'},{'item_id':999},{'item_type':'bad'}]:
            with self.assertRaises(app.APIError):
                app.practice(self.db,{'item_type':'chunk','item_id':1,'ability':'retrieval','grade':2,**fields})
        self.assertEqual(len(app.get_api(self.db,'/api/events',{})),0)
        app.practice(self.db,{'item_type':'sense','item_id':1,'ability':'recognition','grade':2},app.now()-timedelta(days=2))
        self.assertEqual(len(app.get_api(self.db,'/api/review',{})),1)
        self.assertEqual(app.get_api(self.db,'/api/stats',{})['learned_words'],1)
    def test_chunk_audit_and_conflict(self):
        c=app.write_chunk(self.db,{'expression':'A new expression','meaning_zh':'新表达','pattern':'A {thing}','slots':['thing'],'source':'test','sense_ids':[1],'contexts':[{'intent_id':1,'scenario_id':1,'example':'A new idea.'}]})
        self.assertEqual(len(c['senses']),1)
        updated=app.write_chunk(self.db,{'version':1,'source':'test','meaning_zh':'更新释义'},c['id'])
        self.assertEqual(updated['version'],2)
        with self.assertRaises(app.APIError) as e:
            app.write_chunk(self.db,{'version':1,'source':'test'},c['id'])
        self.assertEqual(e.exception.status,409)
        audit=app.rows(self.db,'SELECT * FROM audit_log')
        self.assertEqual(len(audit),2)
        self.assertEqual(json.loads(audit[1]['before_json'])['meaning_zh'],'新表达')

class HTTPTests(unittest.TestCase):
    def test_live_server(self):
        with tempfile.TemporaryDirectory() as tmp:
            try:
                server=app.create_server(Path(tmp)/'live.db',port=0)
            except PermissionError:
                self.skipTest('当前环境不允许监听本地端口')
            thread=threading.Thread(target=server.serve_forever,daemon=True)
            thread.start()
            try:
                base=f'http://127.0.0.1:{server.server_port}'
                with urllib.request.urlopen(base+'/') as response:
                    self.assertEqual(response.status,200)
                    self.assertIn('viewport'.encode(),response.read())
                with urllib.request.urlopen(base+'/api/stats') as response:
                    self.assertEqual(json.load(response)['words'],20)
            finally:
                server.shutdown();server.server_close();thread.join()

    def test_http_handlers_without_socket(self):
        # 沙箱不允许 socket；使用原始 HTTP 请求流执行真实 Handler。
        import io
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'http.db'
            app.initialize(path)
            def request(route,data=None,method='GET',origin=None):
                body=json.dumps(data).encode() if data is not None else b''
                lines=[f'{method} {route} HTTP/1.0','Host: 127.0.0.1:8000','Content-Type: application/json',f'Content-Length: {len(body)}']
                if origin: lines.append('Origin: '+origin)
                raw=('\r\n'.join(lines)+'\r\n\r\n').encode()+body
                class Handler(app.Handler):
                    def setup(self):
                        self.rfile=io.BytesIO(raw)
                        self.wfile=io.BytesIO()
                    def finish(self): pass
                    def log_message(self,*args): pass
                handler=Handler(None,('127.0.0.1',1),SimpleNamespace(db_path=str(path)))
                head,payload=handler.wfile.getvalue().split(b'\r\n\r\n',1)
                return int(head.split()[1]),payload
            self.assertIn('语块'.encode(),request('/')[1])
            for asset in ('/app.js','/style.css'):
                self.assertEqual(request(asset)[0],200)
            self.assertEqual(len(json.loads(request('/api/words')[1])),20)
            self.assertEqual(request('/api/practice',{'item_type':'chunk','item_id':1,'ability':'retrieval','grade':2},'POST')[0],201)
            self.assertEqual(json.loads(request('/api/stats')[1])['events'],1)
            self.assertEqual(request('/api/practice',{'grade':999},'POST')[0],404)
            self.assertEqual(request('/api/chunks',{},'POST','http://evil.example')[0],403)
            practice={'item_type':'chunk','item_id':1,'ability':'retrieval','grade':2}
            self.assertEqual(request('/api/practice',practice,'POST','https://127.0.0.1:8000')[0],201)
            self.assertEqual(request('/api/practice',practice,'POST','https://evil.example')[0],403)
            self.assertEqual(request('/api/chunks',{'expression':'rollback me','meaning_zh':'回滚','pattern':'x','source':'test','sense_ids':[999]},'POST')[0],404)
            self.assertEqual(json.loads(request('/api/chunks?q=rollback')[1]),[])
            self.assertEqual(request('/api/chunks',{'expression':'I get it.','meaning_zh':'重复','pattern':'x','source':'test'},'POST')[0],409)

if __name__=='__main__': unittest.main()
