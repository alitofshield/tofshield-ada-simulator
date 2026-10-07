(() => {
  const svg=document.querySelector('#instrument-svg'); if(!svg)return;
  const family=document.querySelector('#demo-family'),play=document.querySelector('#demo-play');
  const markers=['a','b','c'].map(s=>document.querySelector('#particle-'+s));
  const masses=[50,150,300],times=[0,.20,.40,.57,.94];
  let t=0, running=false, last=0, selected=-1;
  const explanations=[
    ['Sample introduction','Sample material enters through the inlet. Flow and inlet conditions affect transport; this animation does not calculate sampling efficiency.'],
    ['Ionization',''],
    ['Ion guidance','Ion optics guide the charged particles toward the analyzer while vacuum interfaces reduce the gas load. Neutral molecules do not follow the same ion-optical trajectory.'],
    ['Time-of-flight separation','A pulsed packet begins its flight. In the simplified fixed-energy comparison, time scales with √(m/q): lower m/z arrives first. The ion mirror represents energy-spread compensation.'],
    ['Detection and spectrum','The detector records ion arrivals. A calibrated relationship converts arrival time into m/z; repeated packets build a spectrum. Signals here are illustrative, not this file’s observations.']
  ];
  function stage(n){
    if(n===selected)return;selected=n;
    document.querySelectorAll('[data-demo-stage]').forEach((el,i)=>{el.classList.toggle('active',i===n);el.setAttribute('aria-pressed',i===n?'true':'false');});
    document.querySelector('#demo-stage-title').textContent=(n+1)+' · '+explanations[n][0];
    document.querySelector('#demo-stage-text').textContent=n===1?(family.value==='vocus'?'Vocus: reagent ions react with sample molecules to form product ions. Different reagent/reactor choices change which molecules respond.':'mipTOF: microwave plasma processes sampled material into elemental ions. This is not Vocus reagent-ion chemistry.'):explanations[n][1];
  }
  function flight(p){
    // Original schematic path, not manufacturer geometry.
    if(p<.4)return [634+357*p/.4,156];
    if(p<.65){const a=-Math.PI/2+Math.PI*(p-.4)/.25;return [991+54*Math.cos(a),221+65*Math.sin(a)];}
    return [991-(p-.65)/.35*305,286];
  }
  function draw(){
    const n=t<.16?0:t<.34?1:t<.48?2:t<.88?3:4;stage(n);
    markers.forEach((circle,i)=>{
      const arrival=.50+.46*Math.sqrt(masses[i]/300);
      let point;
      if(t<.50){const x=45+(t/.50)*560;point=[x,172+(i-1)*10];}
      else point=flight(Math.min(1,Math.max(0,(t-.50)/(arrival-.50))));
      circle.setAttribute('cx',point[0]);circle.setAttribute('cy',point[1]);circle.setAttribute('opacity',t>arrival?.25:1);
      document.querySelector('#arrival-'+['a','b','c'][i]).textContent='m/z '+masses[i]+': '+(t>=arrival?'arrived':t>=.5?'in flight':'waiting for pulse');
    });
    document.querySelector('#detector').setAttribute('fill',t>.68?'#5ce2c1':'#cdba84');
  }
  function pause(){running=false;play.textContent='Play';}
  play.addEventListener('click',()=>{running=!running;play.textContent=running?'Pause':'Play';last=0;});
  document.querySelector('#demo-step').addEventListener('click',()=>{pause();t=times[(selected+1)%times.length];draw();});
  document.querySelector('#demo-reset').addEventListener('click',()=>{pause();t=0;draw();});
  document.querySelectorAll('[data-demo-stage]').forEach(el=>el.addEventListener('click',()=>{pause();t=times[Number(el.dataset.demoStage)];draw();}));
  family.addEventListener('change',()=>{
    pause();t=0;selected=-1;const mip=family.value==='miptof';
    document.querySelector('#ionization-label').textContent=mip?'Microwave plasma':'Reaction chamber';
    document.querySelector('#ionization-caption').textContent=mip?'Particles → elemental ions':'Molecules + reagent ions → product ions';
    document.querySelector('#plasma').setAttribute('visibility',mip?'visible':'hidden');document.querySelector('#reagent-source').setAttribute('visibility',mip?'hidden':'visible');draw();
  });
  document.addEventListener('visibilitychange',()=>{if(document.hidden)pause();});
  function frame(now){if(running){if(last)t=(t+(now-last)/12000*Number(document.querySelector('#demo-speed').value))%1;draw();}last=now;requestAnimationFrame(frame);}
  draw();requestAnimationFrame(frame);
})();
