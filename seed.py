"""原创教学示例；序号仅为教学顺序，不代表真实词频。"""
DATA = [
('get','v','understand','理解','I get it.','我明白了。','I get {thing}.','确认理解','日常','I get what you mean.'),
('make','v','cause something to happen','使得','That makes sense.','这有道理。','{thing} makes sense.','表示同意','工作','Your plan makes sense.'),
('sense','n','a reasonable meaning','道理','It makes sense to me.','我觉得有道理。','It makes sense to {person}.','表示同意','日常','It makes sense to me now.'),
('take','v','use an amount of time','花费','Take your time.','慢慢来。','Take your time.','提出建议','日常','Take your time. We can wait.'),
('give','v','provide something','给予','Give me a minute.','给我一分钟。','Give {person} {time}.','请求帮助','工作','Give me a minute to check.'),
('go','v','move to a place','去','Let’s go.','我们走吧。','Let’s go {place}.','提出建议','出行','Let’s go home.'),
('come','v','move toward someone','来','Come with me.','跟我来。','Come with {person}.','提出建议','出行','Come with me to the station.'),
('know','v','have information','知道','I don’t know yet.','我还不知道。','I don’t know {detail} yet.','表达不确定','工作','I don’t know the answer yet.'),
('think','v','have an opinion','认为','I think so.','我想是的。','I think {clause}.','表达观点','日常','I think we should leave.'),
('want','v','wish for something','想要','I want to try.','我想试试。','I want to {verb}.','表达意愿','日常','I want to try again.'),
('need','v','require something','需要','I need some help.','我需要一些帮助。','I need {thing}.','请求帮助','工作','I need some help with this task.'),
('work','v','spend effort on a task','处理；工作','I’m working on it.','我正在处理。','I’m working on {task}.','描述进展','工作','I’m working on the report.'),
('help','v','make something easier','帮助','Could you help me?','你能帮我吗？','Could you help me with {thing}?','请求帮助','日常','Could you help me with this bag?'),
('time','n','a period available','时间','Do you have time?','你有时间吗？','Do you have time to {verb}?','询问信息','工作','Do you have time to talk?'),
('good','adj','of high quality','好的','That sounds good.','听起来不错。','{idea} sounds good.','表示同意','日常','Dinner at six sounds good.'),
('sure','adj','certain','确定的','I’m not sure.','我不确定。','I’m not sure if {clause}.','表达不确定','工作','I’m not sure if it will work.'),
('mean','v','intend to express','意思是','What do you mean?','你是什么意思？','What do you mean by {thing}?','确认理解','日常','What do you mean by that?'),
('say','v','express in words','说','What I’m trying to say is…','我想说的是……','What I’m trying to say is {clause}.','补充说明','工作','What I’m trying to say is we need more time.'),
('look','v','direct attention','看','Let me look.','让我看看。','Let me look at {thing}.','提出建议','日常','Let me look at the map.'),
('feel','v','experience an emotion or state','感觉','I feel better.','我感觉好些了。','I feel {adjective}.','描述状态','日常','I feel better today.'),
]

def seed(db, now):
    if db.execute('SELECT count(*) FROM words').fetchone()[0]:
        return
    for i, (lemma,pos,en,zh,expr,meaning,pattern,intent,scene,example) in enumerate(DATA,1):
        db.execute('INSERT INTO words(id,lemma,priority) VALUES(?,?,?)',(i,lemma,1))
        db.execute('INSERT INTO word_senses(id,word_id,pos,definition_en,definition_zh,source) VALUES(?,?,?,?,?,?)',(i,i,pos,en,zh,'原创示例，待审核'))
        db.execute('INSERT INTO chunks(id,expression,meaning_zh,pattern,slots,usage_notes,updated_at,source) VALUES(?,?,?,?,?,?,?,?)',(i,expr,meaning,pattern,__import__('json').dumps(__import__('re').findall(r'\{(.*?)\}',pattern)),'按例句理解语境；替换时注意语法。',now,'原创示例，待审核'))
        db.execute('INSERT INTO chunk_senses VALUES(?,?,?)',(i,i,'core'))
        db.execute('INSERT OR IGNORE INTO intents(name) VALUES(?)',(intent,))
        db.execute('INSERT OR IGNORE INTO scenarios(name) VALUES(?)',(scene,))
        db.execute('INSERT INTO chunk_contexts(chunk_id,intent_id,scenario_id,example) VALUES(?,(SELECT id FROM intents WHERE name=?),(SELECT id FROM scenarios WHERE name=?),?)',(i,intent,scene,example))
    # 一词多义以及一个语块关联多个义项。
    for en,zh,expr,meaning in [('receive','获得','get a message','收到消息'),('become','变得','get better','变好'),('arrive','到达','get there','到达那里')]:
        sid=db.execute('INSERT INTO word_senses(word_id,pos,definition_en,definition_zh,sense_rank,source) VALUES(1,?,?,?,?,?)',('v',en,zh,2,'原创示例，待审核')).lastrowid
        cid=db.execute('INSERT INTO chunks(expression,meaning_zh,pattern,updated_at,source) VALUES(?,?,?,?,?)',(expr,meaning,expr,now,'原创示例，待审核')).lastrowid
        db.execute('INSERT INTO chunk_senses VALUES(?,?,?)',(cid,sid,'core'))
        db.execute('INSERT INTO chunk_contexts(chunk_id,intent_id,scenario_id,example) VALUES(?,1,1,?)',(cid,'I '+expr+'.'))
    db.execute("UPDATE chunk_contexts SET example='I got a message.' WHERE chunk_id=21")
    db.execute("UPDATE chunk_contexts SET example='I hope you get better soon.' WHERE chunk_id=22")
    db.execute("UPDATE chunk_contexts SET example='How do I get there?' WHERE chunk_id=23")
    db.execute("INSERT INTO chunk_senses VALUES(2,3,'support')")
    db.execute("INSERT INTO chunk_senses VALUES(3,2,'support')")
