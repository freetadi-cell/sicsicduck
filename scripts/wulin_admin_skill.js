// ===== Skill Management =====
const RARITY_LABEL={common:'凡',uncommon:'中',rare:'高',legendary:'絕'};
const TYPE_LABEL={martial:'⚔️武功',neigong:'🧘內功',qinggong:'💨輕功'};
const TYPE_CSS={martial:'tag-martial',neigong:'tag-neigong',qinggong:'tag-qinggong'};

function renderSkillList(filter=''){
  const el=document.getElementById('skillList');
  const f=filter.toLowerCase();
  const filtered=skills.filter(s=>!f||s.name.includes(f)||s.key.includes(f)||s.type.includes(f));
  if(!filtered.length){el.innerHTML='<div class="empty">冇技能</div>';return}
  el.innerHTML=filtered.map(s=>{
    const active=selectedSkill&&selectedSkill.key===s.key;
    return `<div class="list-item${active?' active':''}" onclick="selectSkill('${esc(s.key)}')">
      <span class="tag ${TYPE_CSS[s.type]||''} ${s.rarity}">${TYPE_LABEL[s.type]||s.type}</span>
      <div class="name">${esc(s.name)}</div>
      <div class="meta">⚡${s.power} ${RARITY_LABEL[s.rarity]||s.rarity}</div>
    </div>`;
  }).join('');
}
function filterSkills(){renderSkillList(document.getElementById('skillSearch').value)}

function selectSkill(key){
  selectedSkill=skills.find(s=>s.key===key)||null;
  renderSkillList(document.getElementById('skillSearch').value);
  if(!selectedSkill){document.getElementById('skillEditor').innerHTML='<div class="empty">← 選擇一個技能</div>';return}
  const s=selectedSkill;
  document.getElementById('skillEditor').innerHTML=`
    <h3>${esc(s.name)}</h3>
    <div class="grid grid-2">
      <div><label>Key</label><input id="skKey" value="${esc(s.key)}"></div>
      <div><label>名稱</label><input id="skName" value="${esc(s.name)}"></div>
      <div><label>類型</label><select id="skType">
        <option value="martial"${s.type==='martial'?' selected':''}>⚔️ 武功</option>
        <option value="neigong"${s.type==='neigong'?' selected':''}>🧘 內功</option>
        <option value="qinggong"${s.type==='qinggong'?' selected':''}>💨 輕功</option>
      </select></div>
      <div><label>稀有度</label><select id="skRarity">
        <option value="common"${s.rarity==='common'?' selected':''}>凡</option>
        <option value="uncommon"${s.rarity==='uncommon'?' selected':''}>中</option>
        <option value="rare"${s.rarity==='rare'?' selected':''}>高</option>
        <option value="legendary"${s.rarity==='legendary'?' selected':''}>絕</option>
      </select></div>
    </div>
    <div class="stat-bar" style="margin-top:10px">
      <label>威力</label>
      <input type="range" min="1" max="100" value="${s.power}" id="skPower" oninput="this.nextElementSibling.textContent=this.value">
      <span class="val">${s.power}</span>
    </div>
    <div style="margin-top:10px"><label>描述</label><textarea id="skDesc" rows="3">${esc(s.description||'')}</textarea></div>
    <div class="btn-row">
      <button class="btn btn-primary" onclick="saveSkill()">💾 保存</button>
      <button class="btn btn-danger" onclick="deleteSkillConfirm()">🗑 刪除</button>
    </div>`;
}

async function saveSkill(){
  if(!selectedSkill)return;
  const body={
    key:document.getElementById('skKey').value.trim(),
    name:document.getElementById('skName').value.trim(),
    type:document.getElementById('skType').value,
    rarity:document.getElementById('skRarity').value,
    power:parseInt(document.getElementById('skPower').value)||50,
    description:document.getElementById('skDesc').value.trim()
  };
  if(!body.key||!body.name){toast('Key 和名稱不能為空',false);return}
  try{
    if(body.key===selectedSkill.key){
      // Update existing
      await apiPatch(`${SUPABASE_URL}/rest/v1/skills?key=eq.${encodeURIComponent(body.key)}`,body);
    }else{
      // Key changed — delete old, insert new
      await apiDelete(`${SUPABASE_URL}/rest/v1/skills?key=eq.${encodeURIComponent(selectedSkill.key)}`);
      await apiPost(`${SUPABASE_URL}/rest/v1/skills`,body);
    }
    skills=await apiGet(`${SUPABASE_URL}/rest/v1/skills?select=*&order=type,power.desc`);
    renderSkillList(document.getElementById('skillSearch').value);
    selectSkill(body.key);
    renderWorldInfo();
    toast('✅ 技能已保存');
  }catch(e){toast('❌ '+e.message,false)}
}

async function deleteSkillConfirm(){
  if(!selectedSkill)return;
  if(!confirm(`確定刪除「${selectedSkill.name}」？`))return;
  try{
    await apiDelete(`${SUPABASE_URL}/rest/v1/skills?key=eq.${encodeURIComponent(selectedSkill.key)}`);
    // Also remove from npc_skills
    await apiDelete(`${SUPABASE_URL}/rest/v1/npc_skills?skill_key=eq.${encodeURIComponent(selectedSkill.key)}`);
    skills=await apiGet(`${SUPABASE_URL}/rest/v1/skills?select=*&order=type,power.desc`);
    npcSkills=await apiGet(`${SUPABASE_URL}/rest/v1/npc_skills?select=*&order=npc_key`);
    selectedSkill=null;
    document.getElementById('skillEditor').innerHTML='<div class="empty">← 選擇一個技能</div>';
    renderSkillList(document.getElementById('skillSearch').value);
    renderNsNpcList();renderWorldInfo();
    toast('✅ 已刪除');
  }catch(e){toast('❌ '+e.message,false)}
}

function showAddSkill(){
  const m=document.getElementById('modalContent');
  m.innerHTML=`<button class="close" onclick="closeModal(event)">✕</button>
    <h3>新增技能</h3>
    <div class="grid grid-2">
      <div><label>Key</label><input id="newSkKey" placeholder="如: taijiquan"></div>
      <div><label>名稱</label><input id="newSkName" placeholder="太極拳"></div>
      <div><label>類型</label><select id="newSkType">
        <option value="martial">⚔️ 武功</option><option value="neigong">🧘 內功</option><option value="qinggong">💨 輕功</option>
      </select></div>
      <div><label>稀有度</label><select id="newSkRarity">
        <option value="common">凡</option><option value="uncommon">中</option><option value="rare">高</option><option value="legendary">絕</option>
      </select></div>
    </div>
    <div class="stat-bar" style="margin-top:10px"><label>威力</label><input type="range" min="1" max="100" value="50" id="newSkPower" oninput="this.nextElementSibling.textContent=this.value"><span class="val">50</span></div>
    <div style="margin-top:10px"><label>描述</label><textarea id="newSkDesc" rows="2"></textarea></div>
    <div class="btn-row"><button class="btn btn-primary" onclick="addSkill()">確認新增</button></div>`;
  document.getElementById('modalOverlay').classList.add('open');
}

async function addSkill(){
  const body={
    key:document.getElementById('newSkKey').value.trim(),
    name:document.getElementById('newSkName').value.trim(),
    type:document.getElementById('newSkType').value,
    rarity:document.getElementById('newSkRarity').value,
    power:parseInt(document.getElementById('newSkPower').value)||50,
    description:document.getElementById('newSkDesc').value.trim()
  };
  if(!body.key||!body.name){toast('Key 和名稱不能為空',false);return}
  try{
    await apiPost(`${SUPABASE_URL}/rest/v1/skills`,body);
    skills=await apiGet(`${SUPABASE_URL}/rest/v1/skills?select=*&order=type,power.desc`);
    renderSkillList(document.getElementById('skillSearch').value);
    document.getElementById('modalOverlay').classList.remove('open');
    renderWorldInfo();
    toast('✅ 技能已新增');
  }catch(e){toast('❌ '+e.message,false)}
}
