/* Static seed data + browser-local progress. Same scheduling rules as app.py. */
(() => {
  'use strict';
  const KEY = 'english-chunk-agent:v1';
  const abilities = ['recognition', 'listening', 'construction', 'retrieval'];
  const seed = fetch('./data.json').then(r => {
    if (!r.ok) throw Error('词库加载失败，请刷新重试');
    return r.json();
  });
  function load() {
    try {
      const raw = localStorage.getItem(KEY);
      if (!raw) return {progress: [], events: []};
      const state = JSON.parse(raw);
      if (!Array.isArray(state.progress) || !Array.isArray(state.events)) throw Error();
      return state;
    } catch (_) { throw Error('无法读取本浏览器学习记录，请检查浏览器存储设置'); }
  }
  const average = values => values.length ? values.reduce((a,b) => a+b,0)/values.length : null;
  async function api(path, input) {
    const data = await seed;
    const state = load();
    const url = new URL(path, 'https://local.invalid/');
    const route = url.pathname, q = url.searchParams;
    const senses = data.words.flatMap(w => w.senses);
    const item = (kind, id) => ({word:data.words,sense:senses,chunk:data.chunks}[kind] || []).find(x => x.id === id);
    const due = () => state.progress.filter(p => Date.parse(p.next_review) <= Date.now()).sort((a,b) => Date.parse(a.next_review)-Date.parse(b.next_review)).map(p => {
      const value = item(p.item_type,p.item_id);
      return {...p, prompt:value.meaning_zh || value.definition_zh || value.lemma};
    });
    if (route === '/practice') {
      const {item_type:kind,item_id:id,ability,grade} = input;
      if (!item(kind,id) || !abilities.includes(ability) || !Number.isInteger(grade) || grade<0 || grade>3) throw Error('练习参数无效');
      for (const key of ['answer','error']) if (typeof input[key] !== 'string' || input[key].length > 4000) throw Error('回答或备注过长');
      const ts = new Date().toISOString();
      let p = state.progress.find(p => p.item_type===kind && p.item_id===id);
      if (!p) {p = {user_id:'local',item_type:kind,item_id:id,repetitions:0,interval_days:0,...Object.fromEntries(abilities.map(a=>[a,null]))};state.progress.push(p);}
      const previous = p.interval_days;
      const interval = grade===0 ? 10/1440 : previous<1 ? 1 : previous*({1:1.2,2:2,3:2.5}[grade]);
      Object.assign(p,{[ability]:grade,repetitions:p.repetitions+1,interval_days:interval,next_review:new Date(Date.now()+interval*86400000).toISOString(),updated_at:ts});
      state.events.push({...input,id:(state.events.at(-1)?.id || 0)+1,user_id:'local',created_at:ts});
      try { localStorage.setItem(KEY,JSON.stringify(state)); }
      catch (_) { throw Error('学习记录未保存：浏览器存储不可用或空间不足，请检查设置后重试'); }
      return {...p};
    }
    if (route === '/words') return data.words.filter(w=>w.lemma.toLowerCase().includes((q.get('q')||'').toLowerCase()));
    if (route.startsWith('/words/')) return item('word',Number(route.split('/').pop()));
    if (route === '/chunks') return data.chunks.filter(c => {
      const term=(q.get('q')||'').toLowerCase();
      return (c.expression.toLowerCase().includes(term)||c.meaning_zh.includes(term)) &&
        ['intent_id','scenario_id'].every(key=>!q.get(key)||c.contexts.some(x=>x[key]===Number(q.get(key)))) &&
        (!q.get('word_id')||c.senses.some(s=>s.word_id===Number(q.get('word_id'))));
    });
    if (route.startsWith('/chunks/')) return item('chunk',Number(route.split('/').pop()));
    if (route === '/meta') return data.meta;
    if (route === '/progress') return state.progress.sort((a,b)=>b.updated_at.localeCompare(a.updated_at));
    if (route === '/events') return state.events.slice().reverse().slice(0,100);
    if (route === '/review') return due();
    if (route === '/stats') {
      const learned = new Set(state.progress.filter(p=>p.item_type!=='chunk').map(p=>p.item_type==='word'?p.item_id:item('sense',p.item_id)?.word_id));
      const success = (kind,ability) => average(state.events.filter(e=>e.item_type===kind&&e.ability===ability).map(e=>Number(e.grade>=2)));
      return {target_words:1000,words:data.words.length,reviewed_words:data.words.filter(w=>w.reviewed===1).length,learned_words:learned.size,senses:senses.length,chunks:data.chunks.length,practiced_chunks:state.progress.filter(p=>p.item_type==='chunk').length,events:state.events.length,due:due().length,abilities:Object.fromEntries(abilities.map(a=>[a,average(state.progress.map(p=>p[a]).filter(v=>v!==null&&v!==undefined))])),sense_recognition:success('sense','recognition'),chunk_retrieval:success('chunk','retrieval')};
    }
    throw Error('未知操作');
  }
  window.chunkStore = {api};
})();
