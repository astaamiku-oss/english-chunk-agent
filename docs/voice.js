/* Native browser speech only: no API keys or paid services. */
(() => {
  const synth = window.speechSynthesis;
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  let rate = 1, recognition = null;
  const toolbar = document.createElement('div');
  toolbar.className = 'voice-toolbar';
  toolbar.innerHTML = '<label>朗读语速 <select aria-label="朗读语速"><option value="1">正常</option><option value="0.7">慢速</option></select></label><span class="voice-status" role="status"></span>';
  document.querySelector('#content').before(toolbar);
  const status = toolbar.querySelector('[role=status]');
  toolbar.querySelector('select').onchange = e => { rate = Number(e.target.value); };
  if (!synth) status.textContent = '当前浏览器不支持朗读，请尝试 Safari、Chrome 或 Edge。';
  document.addEventListener('click', e => {
    const b = e.target.closest('[data-speak]');
    if (!b) return;
    if (!synth) return;
    stop();
    const utterance = new SpeechSynthesisUtterance(b.dataset.speak);
    const voices = synth.getVoices();
    utterance.voice = voices.find(v => /^en-US$/i.test(v.lang)) || voices.find(v => /^en-GB$/i.test(v.lang)) || voices.find(v => /^en\b/i.test(v.lang)) || null;
    utterance.lang = utterance.voice?.lang || 'en-US';
    utterance.rate = rate;
    utterance.onstart = () => { status.textContent = '正在朗读…'; };
    utterance.onend = () => { status.textContent = ''; };
    utterance.onerror = e => { if (!['canceled','interrupted'].includes(e.error)) status.textContent = '暂时无法朗读，请检查设备声音或稍后重试。'; };
    synth.speak(utterance);
  });
  function stop() {
    if (recognition) { recognition.abort(); recognition = null; }
    synth?.cancel();
    status.textContent = '';
  }
  function tokens(text) { return (text.toLowerCase().replace(/[’‘]/g,"'").match(/[a-z0-9]+(?:'[a-z]+)*/g) || []); }
  function compare(answer, transcript) {
    const a = tokens(answer), b = tokens(transcript);
    const dp = Array.from({length:a.length+1},()=>Array(b.length+1).fill(0));
    for(let i=0;i<=a.length;i++) dp[i][0]=i;
    for(let j=0;j<=b.length;j++) dp[0][j]=j;
    for(let i=1;i<=a.length;i++) for(let j=1;j<=b.length;j++) dp[i][j]=Math.min(dp[i-1][j]+1,dp[i][j-1]+1,dp[i-1][j-1]+(a[i-1]===b[j-1]?0:1));
    let i=a.length,j=b.length, differences=[];
    while(i||j) {
      if(i&&j&&a[i-1]===b[j-1]) {i--;j--;}
      else if(i&&j&&dp[i][j]===dp[i-1][j-1]+1) {differences.unshift(`“${b[--j]}” → “${a[--i]}”`);}
      else if(i&&dp[i][j]===dp[i-1][j]+1) differences.unshift(`漏读 “${a[--i]}”`);
      else differences.unshift(`多读 “${b[--j]}”`);
    }
    return {score:Math.round((1-dp[a.length][b.length]/Math.max(a.length,b.length,1))*100),differences};
  }
  function mount(host, answer) {
    host.className='voice-practice';
    host.innerHTML='<button type="button" class="mic-button">🎙 开始跟读</button><p class="recognition-status" role="status"></p><p class="transcript"></p><p class="comparison"></p><small>英文文本相似度仅供参考，不代表发音评分。语音识别可能使用浏览器厂商的在线服务。</small>';
    const button=host.querySelector('button'), message=host.querySelector('[role=status]');
    if (!Recognition) { button.disabled=true; message.textContent='当前浏览器不支持语音识别（部分 iOS 浏览器会受限），请尝试 Chrome / Edge，或在上方手动输入。'; return; }
    button.onclick=()=>{
      if(recognition) {recognition.stop();return;}
      synth?.cancel();
      const session=new Recognition(); recognition=session;
      session.lang='en-US'; session.interimResults=true; session.continuous=false;
      let heard=false;
      message.textContent='正在准备麦克风，请允许访问…';
      session.onstart=()=>{button.textContent='■ 停止跟读';message.textContent='正在聆听，请说英语…';};
      session.onresult=e=>{
        if(!host.isConnected)return;
        const transcript=Array.from(e.results,r=>r[0].transcript).join(' '); heard=true;
        host.querySelector('.transcript').textContent='识别文字：'+transcript;
        document.querySelector('#answer').value=transcript;
        if(Array.from(e.results).every(r=>r.isFinal)) {
          const result=compare(answer,transcript);
          host.querySelector('.comparison').textContent=`文本相似度：${result.score}% · `+(result.differences.join('；')||'与标准答案一致');
          message.textContent='识别完成';
        }
      };
      session.onerror=e=>{message.textContent=({'not-allowed':'麦克风权限未开启，请在浏览器设置中允许麦克风后重试。','audio-capture':'未找到可用麦克风，请检查设备。','no-speech':'没有听到语音，请再试一次。','network':'语音识别网络连接失败，请检查网络后重试。',aborted:'跟读已停止。'})[e.error]||'暂时无法识别，请换用支持的浏览器或手动输入。';};
      session.onend=()=>{if(recognition===session)recognition=null;button.textContent='🎙 再次跟读';if(!heard&&message.textContent.startsWith('正在'))message.textContent='没有识别到文字，请重试。';};
      try {session.start();} catch {recognition=null;message.textContent='无法启动麦克风，请稍后重试或手动输入。';}
    };
  }
  window.voice={mount,stop,compare};
  window.addEventListener('pagehide',stop);
})();
