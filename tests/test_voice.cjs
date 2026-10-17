const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm'),fs=require('node:fs');
function setup(supported=true){
 const status={},select={},answer={},listeners={};
 const toolbar={querySelector:s=>s==='select'?select:status};
 const speech={cancel(){},getVoices:()=>[{lang:'en-GB'},{lang:'en-US'}],speak(u){this.last=u;}};
 class Recognition{constructor(){Recognition.last=this;}start(){this.onstart();}stop(){this.onend();}abort(){this.onend();}}
 const window={speechSynthesis:speech,addEventListener(){},...(supported?{SpeechRecognition:Recognition}:{})};
 const document={createElement:()=>toolbar,querySelector:s=>s==='#content'?{before(){}}:answer,addEventListener:(k,v)=>listeners[k]=v};
 vm.runInNewContext(fs.readFileSync('static/voice.js','utf8'),{window,document,SpeechSynthesisUtterance:class{constructor(t){this.text=t;}}});
 const nodes={'button':{},'[role=status]':{},'.transcript':{},'.comparison':{}};
 const host={isConnected:true,querySelector:s=>nodes[s]};
 return {voice:window.voice,host,nodes,speech,select,listeners,answer,Recognition};
}
test('normalization, substitutions, omissions and insertions',()=>{
 const {voice}=setup();
 assert.equal(voice.compare('I get it.','i GET it!').score,100);
 assert.equal(voice.compare('I get it','I got it').score,67);
 assert.match(voice.compare('I get it','I it').differences.join(),/漏读 “get”/);
 assert.match(voice.compare('I get it','I really get it').differences.join(),/多读 “really”/);
 assert.equal(voice.compare('I get it','').score,0);
});
test('unsupported browser gives actionable fallback',()=>{
 const {voice,host,nodes}=setup(false);voice.mount(host,'I get it');
 assert.equal(nodes.button.disabled,true);assert.match(nodes['[role=status]'].textContent,/iOS/);
});
test('speech selects US English and slow speed',()=>{
 const {select,listeners,speech}=setup();select.onchange({target:{value:'0.7'}});
 listeners.click({target:{closest:()=>({dataset:{speak:'Hello'}})}});
 assert.equal(speech.last.lang,'en-US');assert.equal(speech.last.rate,0.7);assert.equal(speech.last.text,'Hello');
});
test('both deployments share speech implementation',()=>assert.equal(fs.readFileSync('static/voice.js','utf8'),fs.readFileSync('docs/voice.js','utf8')));

test('recognition transcribes en-US, compares final result and handles permission denial',()=>{
 const {voice,host,nodes,Recognition,answer}=setup();voice.mount(host,'I get it');nodes.button.onclick();
 const session=Recognition.last;assert.equal(session.lang,'en-US');
 const result=[{transcript:'I got it'}];result.isFinal=true;session.onresult({results:[result]});
 assert.equal(answer.value,'I got it');assert.match(nodes['.comparison'].textContent,/67%/);
 session.onerror({error:'not-allowed'});assert.match(nodes['[role=status]'].textContent,/权限/);
 session.onend();assert.match(nodes.button.textContent,/再次跟读/);
});
