// ===== NPC Skill Assignment =====
function renderNsNpcList(filter=''){
  const el=document.getElementById('nsNpcList');
  const f=filter.toLowerCase();
  const filtered=npcs.filter(n=>!f||n.name.includes(f)||n.key.includes(f));
  if(!filtered.length){el.innerHTML='<div class="empty">冇角色</div>';return}
  el.innerHTML=filtered.map(n=>{
    const count=npcSkills.filter(ns=>ns.npc_key===n.key).length;
    return `<div class="list-item" onclick="selectNsNpc('${n.key}')">
      <div class="name">${esc(n.name)}</div>
      <div class="meta">${count} 技能</div>
    </div>`;
  }).join('');
}
function filterNpcSkills(){renderNsNpcList(document.getElementById('nsSearch').value)}

function selectNsNpc(key){
  const npc=npcs.find(n=>n.key===key);
  if(!npc)return;
  const assigned=npcSkills.filter(ns=>ns.npc_key===key);
  const assignedKeys=new Set(assigned.map(a=>a.skill_key));
  const unassigned=skills.filter(s=>!assignedKeys.has(s.key));

  let html=`<h3>${esc(npc.name)} 的技能</h3>`;

  // Assigned skills
  html+=`<div style="margin-top:12px"><b style="color:var(--gold);font-size:13px">已配置 (${assigned.length})</b></div>`;
  if(assigned.length){
    html+=assigned.map(a=>{
      const sk=skills.find(s=>s.key===a.skill_key);
      const name=sk?sk.name:a.skill_key;
      const type=sk?sk.type:'';
      return `<div class="skill-row">
        <span class="tag ${TYPE_CSS[type]||''}">${TYPE_LABEL[type]||type}</span>
        <span class="sk-name">${esc(name)}</span>
        <span class="sk-meta">熟練度 ${a.proficiency||0}</span>
        <button class="btn btn-sm btn-danger" onclick="removeNpcSkill('${key}','${a.skill_key}')">✕</button>
      </div>`;
    }).join('');
  }else{html+=`<div class="empty" style="padding:10px">無</div>`}

  // Add skill
  html+=`<div style="margin-top:16px"><b style="color:var(--gold);font-size:13px">添加技能</b></div>`;
  if(unassigned.length){
    html+='<div style="margin-top:8px"><select id="nsSkillSelect" style="width:100%">';
    html+='<option value="">— 選擇技能 —</option>';
    for(const s of unassigned){
      html+='<option value="'+esc(s.key)+'">'+esc(s.name)+' ('+(TYPE_LABEL[s.type]||s.type)+', ⚡'+s.power+')</option>';
    }
    html+='</select></div>';
    html+=`<div class="stat-bar" style="margin-top:8px"><label>熟練度</label><input type="range" min="0" max="100" value="50" id="nsProf" oninput="this.nextElementSibling.textContent=this.value"><span class="val">50</span></div>`;
    html+=`<div class="btn-row"><button class="btn btn-primary" onclick="addNpcSkill('${key}')">➕ 添加</button></div>`;
  }else{html+=`<div class="empty" style="padding:10px">所有技能已配置</div>`}

  document.getElementById('nsEditor').innerHTML=html;
}

async function addNpcSkill(npcKey){
  const sel=document.getElementById('nsSkillSelect');
  const skillKey=sel.value;
  if(!skillKey){toast('請選擇技能',false);return}
  const prof=parseInt(document.getElementById('nsProf').value)||50;
  try{
    // Check duplicate
    const exists=npcSkills.find(n=>n.npc_key===npcKey&&n.skill_key===skillKey);
    if(exists){
      await apiPatch(`${SUPABASE_URL}/rest/v1/npc_skills?npc_key=eq.${npcKey}&skill_key=eq.${skillKey}`,{proficiency:prof});
    }else{
      await apiPost(`${SUPABASE_URL}/rest/v1/npc_skills`,{npc_key:npcKey,skill_key:skillKey,proficiency:prof});
    }
    npcSkills=await apiGet(`${SUPABASE_URL}/rest/v1/npc_skills?select=*&order=npc_key`);
    selectNsNpc(npcKey);renderNsNpcList(document.getElementById('nsSearch').value);renderWorldInfo();
    toast('✅ 已添加');
  }catch(e){toast('❌ '+e.message,false)}
}

async function removeNpcSkill(npcKey,skillKey){
  if(!confirm('確定移除？'))return;
  try{
    await apiDelete(`${SUPABASE_URL}/rest/v1/npc_skills?npc_key=eq.${npcKey}&skill_key=eq.${skillKey}`);
    npcSkills=await apiGet(`${SUPABASE_URL}/rest/v1/npc_skills?select=*&order=npc_key`);
    selectNsNpc(npcKey);renderNsNpcList(document.getElementById('nsSearch').value);renderWorldInfo();
    toast('✅ 已移除');
  }catch(e){toast('❌ '+e.message,false)}
}

// ===== Init =====
loadAll();
