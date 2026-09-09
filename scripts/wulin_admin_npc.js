// ===== NPC Management =====
function renderNpcList(filter=''){
  const el=document.getElementById('npcList');
  const f=filter.toLowerCase();
  const filtered=npcs.filter(n=>!f||n.name.includes(f)||n.key.includes(f)||(n.title||'').includes(f));
  if(!filtered.length){el.innerHTML='<div class="empty">冇角色</div>';return}
  el.innerHTML=filtered.map(n=>{
    const active=selectedNpc&&selectedNpc.key===n.key;
    return `<div class="list-item${active?' active':''}" onclick="selectNpc('${n.key}')">
      <div class="name">${esc(n.name)}</div>
      <div class="meta">${esc(n.title||'')} · ${esc(n.region||'')}</div>
    </div>`;
  }).join('');
}
function filterNpcs(){renderNpcList(document.getElementById('npcSearch').value)}

function selectNpc(key){
  selectedNpc=npcs.find(n=>n.key===key)||null;
  renderNpcList(document.getElementById('npcSearch').value);
  if(!selectedNpc){document.getElementById('npcEditor').innerHTML='<div class="empty">← 選擇一個角色</div>';return}
  const n=selectedNpc;
  const aff=n.alignment||500;
  document.getElementById('npcEditor').innerHTML=`
    <h3>${esc(n.name)} <span style="font-size:12px;color:var(--muted)">${esc(n.key)}</span></h3>
    <div class="grid grid-2">
      <div><label>姓名</label><input id="npcName" value="${esc(n.name)}"></div>
      <div><label>稱號</label><input id="npcTitle" value="${esc(n.title||'')}"></div>
      <div><label>區域</label><input id="npcRegion" value="${esc(n.region||'')}"></div>
      <div><label>位置</label><input id="npcLocation" value="${esc(n.location||'')}"></div>
    </div>
    <div style="margin-top:10px"><label>心境</label><input id="npcMood" value="${esc(n.mood||'')}"></div>
    <div style="margin-top:8px"><label>待人態度</label><input id="npcAttitude" value="${esc(n.attitude||'')}"></div>
    <div class="stat-bar" style="margin-top:10px">
      <label>善惡</label>
      <input type="range" min="0" max="1000" value="${aff}" id="npcAlign" oninput="this.nextElementSibling.textContent=this.value">
      <span class="val">${aff}</span>
    </div>
    <div class="stat-bar" style="margin-top:6px">
      <label>道心</label>
      <input type="range" min="0" max="1000" value="${n.daoxin||500}" id="npcDaoxin" oninput="this.nextElementSibling.textContent=this.value">
      <span class="val">${n.daoxin||500}</span>
    </div>
    <div class="grid grid-3" style="margin-top:10px">
      <div class="stat-bar"><label>武功</label><input type="range" min="1" max="100" value="${n.martial||50}" id="npcMartial" oninput="this.nextElementSibling.textContent=this.value"><span class="val">${n.martial||50}</span></div>
      <div class="stat-bar"><label>內功</label><input type="range" min="1" max="100" value="${n.neigong||50}" id="npcNeigong" oninput="this.nextElementSibling.textContent=this.value"><span class="val">${n.neigong||50}</span></div>
      <div class="stat-bar"><label>輕功</label><input type="range" min="1" max="100" value="${n.qinggong||50}" id="npcQinggong" oninput="this.nextElementSibling.textContent=this.value"><span class="val">${n.qinggong||50}</span></div>
    </div>
    <div style="margin-top:10px">
      <label>對白（每行一句）</label>
      <textarea id="npcDialogue" rows="4">${(n.dialogue||[]).join('\n')}</textarea>
    </div>
    <div style="margin-top:10px">
      <label>關係（JSON）</label>
      <textarea id="npcRelations" rows="3">${JSON.stringify(n.relations||{},null,1)}</textarea>
    </div>
    <div class="btn-row">
      <button class="btn btn-primary" onclick="saveNpc()">💾 保存到本地</button>
      <button class="btn btn-danger" onclick="deleteNpcConfirm()">🗑 刪除</button>
    </div>`;
}

async function saveNpc(){
  if(!selectedNpc)return;
  const idx=npcs.findIndex(n=>n.key===selectedNpc.key);
  if(idx<0)return;
  const n=npcs[idx];
  n.name=document.getElementById('npcName').value.trim();
  n.title=document.getElementById('npcTitle').value.trim();
  n.region=document.getElementById('npcRegion').value.trim();
  n.location=document.getElementById('npcLocation').value.trim();
  n.mood=document.getElementById('npcMood').value.trim();
  n.attitude=document.getElementById('npcAttitude').value.trim();
  n.alignment=parseInt(document.getElementById('npcAlign').value)||500;
  n.daoxin=parseInt(document.getElementById('npcDaoxin').value)||500;
  n.martial=parseInt(document.getElementById('npcMartial').value)||50;
  n.neigong=parseInt(document.getElementById('npcNeigong').value)||50;
  n.qinggong=parseInt(document.getElementById('npcQinggong').value)||50;
  n.dialogue=document.getElementById('npcDialogue').value.split('\n').map(s=>s.trim()).filter(Boolean);
  try{n.relations=JSON.parse(document.getElementById('npcRelations').value)}catch(e){}
  worldData.npcs=npcs;
  // Save to local file via download
  const blob=new Blob([JSON.stringify(worldData,null,2)],{type:'application/json'});
  const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='wulin_world.json';a.click();
  toast('✅ 已下載 wulin_world.json（手動上傳至 repo）');
  renderNpcList(document.getElementById('npcSearch').value);
  renderWorldInfo();
}

function deleteNpcConfirm(){
  if(!selectedNpc)return;
  if(!confirm(`確定刪除 ${selectedNpc.name}？`))return;
  npcs=npcs.filter(n=>n.key!==selectedNpc.key);
  worldData.npcs=npcs;
  selectedNpc=null;
  const blob=new Blob([JSON.stringify(worldData,null,2)],{type:'application/json'});
  const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='wulin_world.json';a.click();
  document.getElementById('npcEditor').innerHTML='<div class="empty">← 選擇一個角色</div>';
  renderNpcList(document.getElementById('npcSearch').value);
  renderWorldInfo();
  toast('✅ 已刪除');
}

function showAddNpc(){
  const key=prompt('新角色 key（英文，如 zhangwuji）:');
  if(!key)return;
  if(npcs.find(n=>n.key===key)){toast('key 已存在',false);return}
  const newNpc={key,name:key,title:'',region:'襄陽城',location:'',mood:'',attitude:'',alignment:500,daoxin:500,martial:50,neigong:50,qinggong:50,dialogue:[],chat_options:[],relations:{}};
  npcs.push(newNpc);worldData.npcs=npcs;
  selectNpc(key);
  toast('✅ 新角色已建立，請填寫資料後保存');
}
