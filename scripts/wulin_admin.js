// ===== API Layer =====
async function apiGet(url){const r=await fetch(url,{headers:{'apikey':SUPABASE_ANON,'Authorization':`Bearer ${SUPABASE_ANON}`}});
if(!r.ok)throw new Error(`GET ${url}: ${r.status}`);return r.json()}
async function apiPost(url,body){const r=await fetch(url,{method:'POST',headers:{'apikey':SUPABASE_ANON,'Authorization':`Bearer ${SUPABASE_ANON}`,'Content-Type':'application/json','Prefer':'return=minimal'},body:JSON.stringify(body)});
if(!r.ok){const t=await r.text();throw new Error(`POST: ${r.status} ${t}`)}return r}
async function apiPatch(url,body){const r=await fetch(url,{method:'PATCH',headers:{'apikey':SUPABASE_ANON,'Authorization':`Bearer ${SUPABASE_ANON}`,'Content-Type':'application/json','Prefer':'return=minimal'},body:JSON.stringify(body)});
if(!r.ok){const t=await r.text();throw new Error(`PATCH: ${r.status} ${t}`)}return r}
async function apiDelete(url){const r=await fetch(url,{method:'DELETE',headers:{'apikey':SUPABASE_ANON,'Authorization':`Bearer ${SUPABASE_ANON}`,'Prefer':'return=minimal'}});
if(!r.ok){const t=await r.text();throw new Error(`DELETE: ${r.status} ${t}`)}return r}

// ===== State =====
let worldData=null, npcs=[], skills=[], npcSkills=[], selectedNpc=null, selectedSkill=null;

// ===== Helpers =====
function toast(msg,ok=true){const t=document.getElementById('toast');t.textContent=msg;t.className='toast show '+(ok?'ok':'err');setTimeout(()=>t.className='toast',2500)}
function esc(s){return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}
function showTab(name){document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));
document.querySelector(`.tab[onclick="showTab('${name}')"]`).classList.add('active');document.getElementById('panel-'+name).classList.add('active')}
function closeModal(e){if(e&&e.target!==document.getElementById('modalOverlay'))return;document.getElementById('modalOverlay').classList.remove('open')}

// ===== Load All =====
async function loadAll(){
  try{const wr=await fetch('data/wulin_world.json');worldData=await wr.json();npcs=worldData.npcs||[]}catch(e){npcs=[]}
  try{skills=await apiGet(`${SUPABASE_URL}/rest/v1/skills?select=*&order=type,power.desc`)}catch(e){skills=[]}
  try{npcSkills=await apiGet(`${SUPABASE_URL}/rest/v1/npc_skills?select=*&order=npc_key`)}catch(e){npcSkills=[]}
  renderWorldInfo();renderNpcList();renderSkillList();renderNsNpcList();
}

function renderWorldInfo(){
  if(!worldData)return;const m=worldData.meta||{};
  document.getElementById('worldInfo').innerHTML=`
    <div class="chip">🗓 <b>${m.world_time||'?'}</b></div>
    <div class="chip">🗺 <b>${Object.keys(m.region_distances||{}).length}</b> 區域</div>
    <div class="chip">👤 <b>${npcs.length}</b> 角色</div>
    <div class="chip">⚔️ <b>${skills.length}</b> 技能</div>
    <div class="chip">🔗 <b>${npcSkills.length}</b> 技能配置</div>`;
}
