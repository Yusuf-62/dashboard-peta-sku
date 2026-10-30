(() => {
  'use strict';
  const PROVINCES = ['Kalimantan Tengah','Kalimantan Selatan','Kalimantan Timur'];
  const COLORS = {'Kalimantan Tengah':'#43A047','Kalimantan Selatan':'#42A5F5','Kalimantan Timur':'#FBC02D'};
  const PALETTES = {'Kalimantan Tengah':['#E8F5E9','#81C784','#1B5E20'],'Kalimantan Selatan':['#E3F2FD','#64B5F6','#0D47A1'],'Kalimantan Timur':['#FFFDE7','#FFF176','#F9A825']};
  const $ = id => document.getElementById(id);
  const on = (id, event, handler, options) => { const el = $(id); if (el) el.addEventListener(event, handler, options); else console.warn(`Elemen #${id} tidak ditemukan; event ${event} dilewati.`); return el; };
  let dataset, geojson, kecGeojson={type:'FeatureCollection',features:[]}, map, geoLayer, assetManifest={};
  const fmt = n => (Number(n)||0).toLocaleString('id-ID',{maximumFractionDigits:0});
  const money = n => 'Rp ' + fmt(n);
  const growth = (a,b) => !b ? (a ? null : 0) : ((a/b)-1)*100;
  const pct = n => n === null || !Number.isFinite(n) ? '—' : `${n>=0?'+':''}${n.toLocaleString('id-ID',{minimumFractionDigits:1,maximumFractionDigits:1})}%`;
  const norm = s => String(s ?? '').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toUpperCase().trim().replace(/^(KABUPATEN|KAB\.|KOTA ADMINISTRASI|KOTA)\s+/,'').replace(/[^A-Z0-9]/g,'');
  const sum = (rows,key) => rows.reduce((a,r)=>a+(Number(r[key])||0),0);
  const unique = xs => [...new Set(xs)];

  function setOptions(el, items, firstLabel, selected='ALL') {
    el.innerHTML=''; const all=document.createElement('option'); all.value='ALL'; all.textContent=firstLabel; el.appendChild(all);
    items.forEach(item=>{const o=document.createElement('option');o.value=item.value;o.textContent=item.label;el.appendChild(o)});
    el.value=[...el.options].some(o=>o.value===selected)?selected:'ALL';
  }
  function selectedRegion() {
    const value=$('region-filter').value;
    if(value==='ALL') return {type:'ALL'};
    if(value.startsWith('PROV|')) return {type:'PROV',provKey:value.slice(5)};
    if(value.startsWith('KAB|')) return {type:'KAB',key:value.slice(4)};
    return {type:'ALL'};
  }
  function skuMatches(recordSku, selectedSku) {
    return recordSku===selectedSku || recordSku.startsWith(selectedSku + '/');
  }
  function selectedRows() {
    const sku=$('sku-filter').value.trim(), depo=$('depo-filter').value, kec=$('kecamatan-filter').value, region=selectedRegion();
    return dataset.records.filter(r => skuMatches(r.sku,sku) && (depo==='ALL'||r.DEPO===depo) &&
      (region.type==='ALL'||(region.type==='PROV'&&r.provinsi_key===region.provKey)||(region.type==='KAB'&&`${r.provinsi_key}||${r.kabupaten_key}`===region.key)) &&
      (kec==='ALL'||`${r.provinsi_key}||${r.kabupaten_key}||${norm(r.KECAMATAN||r.Kecamatan||r.kecamatan)}`===kec));
  }
  function filteredBaseRows() {
    const sku=$('sku-filter').value.trim(), depo=$('depo-filter').value;
    return dataset.records.filter(r=>skuMatches(r.sku,sku)&&(depo==='ALL'||r.DEPO===depo));
  }

  // Nested menu helpers. Click selects; hover reveals the next level to the right.
  // Klik memilih item; hover hanya membuka submenu. Event dipasang saat node dibuat,
  // tetapi parent diperiksa saat event terjadi (node sudah berada di DOM).
  function menuItem(label, children=[], onSelect=null) {
    const item=document.createElement('div');
    item.className='menu-item'; item.tabIndex=0; item.setAttribute('role','menuitem');
    const text=document.createElement('span'); text.textContent=label; item.appendChild(text);
    if(children.length){
      const arrow=document.createElement('span'); arrow.className='menu-arrow'; arrow.textContent='›'; item.appendChild(arrow);
      const sub=document.createElement('div'); sub.className='menu-submenu';
      const list=document.createElement('div'); list.className='menu-list';
      children.forEach(c=>list.appendChild(menuItem(c.label,c.children||[],c.onSelect||null)));
      sub.appendChild(list); item.appendChild(sub);
      item.addEventListener('mouseenter',()=>{
        const parent=item.parentElement;
        if(parent) parent.querySelectorAll(':scope > .menu-item > .menu-submenu').forEach(el=>{if(el!==sub)el.style.display='none'});
        const rect=item.getBoundingClientRect();
        sub.style.position='fixed'; sub.style.display='block';
        const h=sub.offsetHeight||220, w=sub.offsetWidth||220;
        sub.style.top=Math.max(6,Math.min(rect.top,window.innerHeight-h-6))+'px';
        const right=rect.right+4;
        sub.style.left=(right+w>window.innerWidth?Math.max(6,rect.left-w-4):right)+'px';
      });
      item.addEventListener('mouseleave',e=>{
        if(!item.contains(e.relatedTarget)) sub.style.display='none';
      });
      item.addEventListener('focus',()=>{sub.style.display='block'});
    }
    if(onSelect){
      item.addEventListener('click',e=>{e.stopPropagation();onSelect()});
      item.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();onSelect()}});
    }
    return item;
  }
  function bindMenu(triggerId,menuId){
    const trigger=$(triggerId), menu=$(menuId);
    if(!trigger || !menu){ console.error(`[EMACO2 FIX3] Elemen menu tidak ditemukan: #${triggerId} atau #${menuId}. Pastikan index.html dan Assets/js/dashboard.js berasal dari ZIP yang sama.`); return; }
    const wrapper=trigger.closest('.compact-filter');
    trigger.addEventListener('click',()=>{menu.hidden=!menu.hidden;trigger.setAttribute('aria-expanded',String(!menu.hidden))});
    if(wrapper) wrapper.addEventListener('mouseleave',e=>{if(!wrapper.contains(e.relatedTarget)){menu.hidden=true;trigger.setAttribute('aria-expanded','false');menu.querySelectorAll('.menu-submenu').forEach(el=>el.style.display='')}});
    document.addEventListener('keydown',e=>{if(e.key==='Escape'){menu.hidden=true;trigger.setAttribute('aria-expanded','false')}});
  }
  function closeMenu(id){const menu=$(id);if(menu)menu.hidden=true;}
  function updateRegionButton(label){$('region-menu-trigger').textContent=label+' ▾';}
  function updateKecamatanButton(label){$('kecamatan-menu-trigger').textContent=label+' ▾';}
  function updateSkuButton(label){$('sku-menu-trigger').textContent=label+' ▾';}

  function renderSkuMenu(){
    if(!dataset)return;
    const root=$('sku-menu');root.replaceChildren();
    const list=document.createElement('div');list.className='menu-list';
    const tree=new Map();
    dataset.skus.forEach(value=>{
      const parts=String(value).split('/').filter(Boolean);let level=tree;
      parts.forEach((part,index)=>{
        if(!level.has(part))level.set(part,{children:new Map(),value:null,path:parts.slice(0,index+1).join('/')});
        const node=level.get(part);if(index===parts.length-1)node.value=String(value);level=node.children;
      });
    });
    function selectSku(value,label){
      $('sku-filter').value=value;updateSkuButton(label);closeMenu('sku-menu');
      $('depo-filter').value='ALL';$('region-filter').value='ALL';$('kecamatan-filter').value='ALL';
      updateRegionButton('Semua wilayah');updateKecamatanButton('Semua kecamatan');refreshDepo();
    }
    function buildItems(nodes){
      return [...nodes.entries()].sort((a,b)=>a[0].localeCompare(b[0],'id',{numeric:true})).map(([label,node])=>{
        const value=node.value || node.path;
        const onSelect=()=>selectSku(value,label);
        return {label,children:buildItems(node.children),onSelect};
      });
    }
    buildItems(tree).forEach(item=>list.appendChild(menuItem(item.label,item.children,item.onSelect)));
    root.appendChild(list);
  }

  function renderRegionMenu(){
    if(!dataset)return;
    const root=$('region-menu');root.replaceChildren();
    const list=document.createElement('div');list.className='menu-list';
    const selectProvince=(province,pk)=>{
      $('region-filter').value=`PROV|${pk}`;$('kecamatan-filter').value='ALL';
      updateRegionButton(province);updateKecamatanButton('Semua kecamatan');
      closeMenu('region-menu');refreshKecamatan();
    };
    const selectKab=(province,name,key)=>{
      $('region-filter').value=`KAB|${key}`;$('kecamatan-filter').value='ALL';
      updateRegionButton(`${province} / ${name}`);updateKecamatanButton('Semua kecamatan');
      closeMenu('region-menu');refreshKecamatan();
    };
    list.appendChild(menuItem('Semua wilayah',[],()=>{
      $('region-filter').value='ALL';$('kecamatan-filter').value='ALL';
      updateRegionButton('Semua wilayah');updateKecamatanButton('Semua kecamatan');
      closeMenu('region-menu');refreshKecamatan();
    }));
    const base=filteredBaseRows();
    PROVINCES.forEach(province=>{
      const pk=norm(province),provinceRows=base.filter(r=>r.provinsi_key===pk||norm(r.PROVINSI)===pk);
      if(!provinceRows.length)return;
      const counties=new Map();
      provinceRows.forEach(r=>{const key=`${r.provinsi_key}||${r.kabupaten_key}`;if(!counties.has(key))counties.set(key,r.KABUPATEN)});
      const countyItems=[...counties.entries()].sort((a,b)=>String(a[1]).localeCompare(String(b[1]),'id')).map(([key,name])=>{
        const rows=provinceRows.filter(r=>`${r.provinsi_key}||${r.kabupaten_key}`===key),kecMap=new Map();
        rows.forEach(r=>{const n=String(r.KECAMATAN||r.Kecamatan||r.kecamatan||'').trim();if(n)kecMap.set(`${key}||${norm(n)}`,n)});
        const kecItems=[{label:'Semua kecamatan',onSelect:()=>selectKab(province,name,key)},
          ...[...kecMap.entries()].sort((a,b)=>a[1].localeCompare(b[1],'id')).map(([value,n])=>({label:n,onSelect:()=>{
            $('region-filter').value=`KAB|${key}`;refreshKecamatan();$('kecamatan-filter').value=value;
            updateRegionButton(`${province} / ${name}`);updateKecamatanButton(n);closeMenu('region-menu');updateDashboard();
          }}))];
        return {label:name,children:kecItems,onSelect:()=>selectKab(province,name,key)};
      });
      list.appendChild(menuItem(province,[{label:'Semua kabupaten/kota',onSelect:()=>selectProvince(province,pk)},...countyItems],()=>selectProvince(province,pk)));
    });
    root.appendChild(list);
  }
  function renderKecamatanMenu(){
    if(!dataset)return;const root=$('kecamatan-menu');root.replaceChildren();const list=document.createElement('div');list.className='menu-list';
    list.appendChild(menuItem('Semua kecamatan',[],()=>{$('kecamatan-filter').value='ALL';updateKecamatanButton('Semua kecamatan');closeMenu('kecamatan-menu');updateDashboard()}));
    const base=filteredBaseRows(), groups=new Map();
    base.forEach(r=>{const n=String(r.KECAMATAN||r.Kecamatan||r.kecamatan||'').trim();if(!n)return;const kabKey=`${r.provinsi_key}||${r.kabupaten_key}`;if(!groups.has(kabKey))groups.set(kabKey,{prov:r.PROVINSI,kab:r.KABUPATEN,kecs:new Map()});groups.get(kabKey).kecs.set(`${kabKey}||${norm(n)}`,n)});
    [...groups.entries()].sort((a,b)=>`${a[1].prov} ${a[1].kab}`.localeCompare(`${b[1].prov} ${b[1].kab}`,'id')).forEach(([kabKey,g])=>{
      const kecs=[...g.kecs.entries()].sort((a,b)=>a[1].localeCompare(b[1],'id')).map(([value,n])=>({label:n,onSelect:()=>{$('region-filter').value=`KAB|${kabKey}`;refreshKecamatan();$('kecamatan-filter').value=value;updateRegionButton(`${g.prov} / ${g.kab}`);updateKecamatanButton(n);closeMenu('kecamatan-menu');updateDashboard()}}));
      list.appendChild(menuItem(`${g.prov} / ${g.kab}`,kecs));
    });root.appendChild(list);
  }

  function refreshDepo(){
    const sku=$('sku-filter').value.trim(),depots=unique(dataset.records.filter(r=>skuMatches(r.sku,sku)).map(r=>r.DEPO)).sort((a,b)=>a.localeCompare(b,'id')),current=$('depo-filter').value;
    setOptions($('depo-filter'),depots.map(x=>({label:x,value:x})),'Semua Depo',current);refreshRegion();renderSkuMenu();
  }
  function refreshRegion(){
    const sku=$('sku-filter').value.trim(),depo=$('depo-filter').value,rows=dataset.records.filter(r=>skuMatches(r.sku,sku)&&(depo==='ALL'||r.DEPO===depo)),options=[];
    PROVINCES.filter(p=>rows.some(r=>norm(r.PROVINSI)===norm(p))).forEach(p=>{const pk=norm(p);options.push({label:`Provinsi: ${p}`,value:`PROV|${pk}`});const counties=new Map();rows.filter(r=>norm(r.PROVINSI)===pk).forEach(r=>{const key=`${r.provinsi_key}||${r.kabupaten_key}`;if(!counties.has(key))counties.set(key,r.KABUPATEN)});[...counties.entries()].sort((a,b)=>a[1].localeCompare(b[1],'id')).forEach(([key,name])=>options.push({label:`Kabupaten: ${name}`,value:`KAB|${key}`}))});
    const current=$('region-filter').value;setOptions($('region-filter'),options,'Semua wilayah',current);refreshKecamatan();renderRegionMenu();
  }
  function refreshKecamatan(){
    const sku=$('sku-filter').value.trim(),depo=$('depo-filter').value,region=selectedRegion();let rows=dataset.records.filter(r=>skuMatches(r.sku,sku)&&(depo==='ALL'||r.DEPO===depo));
    if(region.type==='PROV')rows=rows.filter(r=>r.provinsi_key===region.provKey);if(region.type==='KAB')rows=rows.filter(r=>`${r.provinsi_key}||${r.kabupaten_key}`===region.key);
    const names=new Map();rows.forEach(r=>{const name=String(r.KECAMATAN||r.Kecamatan||r.kecamatan||'').trim();if(name){const key=`${r.provinsi_key}||${r.kabupaten_key}||${norm(name)}`;if(!names.has(key))names.set(key,{name,kabupaten:r.KABUPATEN})}});
    const current=$('kecamatan-filter').value,options=[...names.entries()].sort((a,b)=>a[1].name.localeCompare(b[1].name,'id')).map(([value,item])=>({label:`${item.name} — ${item.kabupaten}`,value}));setOptions($('kecamatan-filter'),options,'Semua kecamatan',current);
    $('kecamatan-filter').disabled=names.size===0;$('kecamatan-filter').title=names.size?'Pilih kecamatan':'Data Excel tidak memiliki kolom KECAMATAN atau tidak ada data kecamatan untuk filter ini';renderKecamatanMenu();updateDashboard();
  }
  function tableRows(rows){const m=new Map();rows.forEach(r=>{const k=`${r.PROVINSI}||${r.KABUPATEN}`;if(!m.has(k))m.set(k,{PROVINSI:r.PROVINSI,KABUPATEN:r.KABUPATEN,'ACT MTD':0,LY:0,'AVG L3M':0,LM:0,'CUST ACT':0,'CUST REG':0});const o=m.get(k);['ACT MTD','LY','AVG L3M','LM','CUST ACT','CUST REG'].forEach(c=>o[c]+=Number(r[c])||0)});return [...m.values()].map(r=>({...r,G_LY:growth(r['ACT MTD'],r.LY),G_L3M:growth(r['ACT MTD'],r['AVG L3M']),G_LM:growth(r['ACT MTD'],r.LM),'%CA':r['CUST REG']?100*r['CUST ACT']/r['CUST REG']:0})).sort((a,b)=>a.PROVINSI.localeCompare(b.PROVINSI,'id')||a.KABUPATEN.localeCompare(b.KABUPATEN,'id'))}
  function buildTable(rows){const wrap=$('table-wrap');wrap.innerHTML='';if(!rows.length){wrap.textContent='Tidak ada data untuk filter ini.';return}const table=document.createElement('table');table.className='detail-table';const headers=['Provinsi','Kabupaten','Sales ACT MTD','vs LY','vs L3M','vs LM','Cust Act / Reg','%CA'];const thead=document.createElement('thead'),tr=document.createElement('tr');headers.forEach(h=>{const th=document.createElement('th');th.textContent=h;tr.appendChild(th)});thead.appendChild(tr);table.appendChild(thead);const tbody=document.createElement('tbody');rows.forEach(r=>{const vals=[r.PROVINSI,r.KABUPATEN,fmt(r['ACT MTD']),pct(r.G_LY),pct(r.G_L3M),pct(r.G_LM),`${fmt(r['CUST ACT'])} / ${fmt(r['CUST REG'])}`,`${r['%CA'].toLocaleString('id-ID',{maximumFractionDigits:0,minimumFractionDigits:0})}%`];const tr=document.createElement('tr');vals.forEach((v,i)=>{const td=document.createElement('td');td.textContent=v;if(i>=3&&i<=5)td.className=String(v).startsWith('+')?'positive':String(v).startsWith('-')?'negative':'';tr.appendChild(td)});tbody.appendChild(tr)});table.appendChild(tbody);wrap.appendChild(table)}
  function buildProvinceCards(rows){const target=$('province-cards');target.innerHTML='';PROVINCES.forEach(p=>{const sub=rows.filter(r=>norm(r.PROVINSI)===norm(p));if(!sub.length)return;const sales=sum(sub,'ACT MTD'),ly=sum(sub,'LY'),l3=sum(sub,'AVG L3M'),lm=sum(sub,'LM'),ca=sum(sub,'CUST ACT'),reg=sum(sub,'CUST REG');const card=document.createElement('article');card.className='province-card';
      const growthTile=(label,value)=>{const up=value===null?false:value>=0;const color=value===null?'neutral':(up?'positive':'negative');const direction=value===null?'Data tidak tersedia':(up?'Naik':'Turun');return `<div class="growth-tile ${color}" title="${label}: ${pct(value)}"><span class="growth-label">${label}</span><div class="growth-value"><i class="growth-triangle" aria-hidden="true"></i><strong aria-label="${direction} ${pct(value)}">${pct(value)}</strong></div></div>`};
      card.innerHTML=`<div class="province-name" style="background:${COLORS[p]}">${p}</div><div class="province-sales-label">Sales ACT MTD</div><div class="province-sales"><span class="currency-prefix">Rp</span><span class="sales-amount">${fmt(sales)}</span></div><div class="province-growth">${growthTile('vs LY',growth(sales,ly))}${growthTile('vs L3M',growth(sales,l3))}${growthTile('vs LM',growth(sales,lm))}</div><div class="province-bottom"><div><span>CA</span><strong>${fmt(ca)}</strong></div><div><span>CR</span><strong>${fmt(reg)}</strong></div><div><span>%CA</span><strong>${(reg?100*ca/reg:0).toLocaleString('id-ID',{maximumFractionDigits:0})}%</strong></div></div>`;target.appendChild(card)})}
  function hexRgb(h){const x=h.replace('#','');return [parseInt(x.slice(0,2),16),parseInt(x.slice(2,4),16),parseInt(x.slice(4,6),16)]}
  function mix(a,b,t){return '#'+a.map((v,i)=>Math.round(v+(b[i]-v)*t).toString(16).padStart(2,'0')).join('')}
  function colorFor(feature,values){const p=feature.properties.provinsi,palette=PALETTES[p]||['#edf2f7','#9fb5ca','#123f70'];const key=feature.properties.kecamatan_key?`${feature.properties.provinsi_key}||${feature.properties.kabupaten_key}||${feature.properties.kecamatan_key}`:`${feature.properties.provinsi_key}||${feature.properties.kabupaten_key}`;const val=Number(values.get(key)?.['ACT MTD']||0),provinceValues=[...values.entries()].filter(([k])=>k.startsWith(`${norm(p)}||`)).map(([,v])=>Number(v['ACT MTD'])||0),max=Math.max(1,...provinceValues),t=Math.max(0,Math.min(1,val/max)),a=hexRgb(palette[0]),b=hexRgb(palette[1]),c=hexRgb(palette[2]);return t<.5?mix(a,b,t*2):mix(b,c,(t-.5)*2)}
  function updateMap(){
    const base=filteredBaseRows(),mapAgg=new Map(),kecAgg=new Map();base.forEach(r=>{const key=`${r.provinsi_key}||${r.kabupaten_key}`;if(!mapAgg.has(key))mapAgg.set(key,{'ACT MTD':0,'CUST ACT':0,'CUST REG':0});['ACT MTD','CUST ACT','CUST REG'].forEach(k=>mapAgg.get(key)[k]+=Number(r[k])||0);const kn=String(r.KECAMATAN||r.Kecamatan||r.kecamatan||'').trim();if(kn){const kk=`${r.provinsi_key}||${r.kabupaten_key}||${norm(kn)}`;if(!kecAgg.has(kk))kecAgg.set(kk,{'ACT MTD':0,'CUST ACT':0,'CUST REG':0});['ACT MTD','CUST ACT','CUST REG'].forEach(k=>kecAgg.get(kk)[k]+=Number(r[k])||0)}});
    const region=selectedRegion(),kec=$('kecamatan-filter').value,useKec=region.type==='KAB'&&(kecGeojson.features||[]).length>0,source=useKec?kecGeojson:geojson;let features=(source.features||[]).filter(f=>(region.type==='ALL')||(region.type==='PROV'&&f.properties.provinsi_key===region.provKey)||(region.type==='KAB'&&`${f.properties.provinsi_key}||${f.properties.kabupaten_key}`===region.key));if(useKec){features=features.filter(f=>`${f.properties.provinsi_key}||${f.properties.kabupaten_key}`===region.key);if(kec!=='ALL'){const parts=kec.split('||');features=features.filter(f=>f.properties.kecamatan_key===parts[2])}}
    if(geoLayer)map.removeLayer(geoLayer);const values=useKec?kecAgg:mapAgg,keyFor=f=>useKec?`${f.properties.provinsi_key}||${f.properties.kabupaten_key}||${f.properties.kecamatan_key}`:`${f.properties.provinsi_key}||${f.properties.kabupaten_key}`,valueFor=f=>values.get(keyFor(f))||{'ACT MTD':0,'CUST ACT':0,'CUST REG':0};
    geoLayer=L.geoJSON({type:'FeatureCollection',features},{style:f=>({fillColor:colorFor(f,values),weight:1,color:'#fff',fillOpacity:.9}),onEachFeature:(f,layer)=>{const p=f.properties,v=valueFor(f),title=useKec?p.kecamatan_geo:p.kabupaten_geo;layer.bindTooltip(`<b>${title}</b><br>${p.kabupaten_geo||''}<br>${p.provinsi}<br>ACT MTD: ${money(v['ACT MTD'])}<br>Cust Active: ${fmt(v['CUST ACT'])}<br>Cust Registered: ${fmt(v['CUST REG'])}`);layer.on('click',()=>{if(useKec)return;const key=`${p.provinsi_key}||${p.kabupaten_key}`,value=`KAB|${key}`;if([...$('region-filter').options].some(o=>o.value===value)){$('region-filter').value=value;updateRegionButton(p.kabupaten_geo||p.kabupaten||'Kabupaten');refreshKecamatan()}})}}).addTo(map);
    if(features.length){const bounds=geoLayer.getBounds();if(bounds.isValid())map.fitBounds(bounds,{padding:[18,18],maxZoom:useKec?10:region.type==='KAB'?8:region.type==='PROV'?7:6})}else map.setView([-1.45,115.05],5.15);
    const legend=$('map-legend');legend.innerHTML='';PROVINCES.forEach(p=>{if(region.type==='PROV'&&region.provKey!==norm(p))return;if(region.type==='KAB'&&!region.key.startsWith(`${norm(p)}||`))return;const item=document.createElement('div');item.className='legend-item';item.innerHTML=`<span class="legend-dot" style="background:${COLORS[p]}"></span><strong>${p}</strong><span>rendah → tinggi</span>`;legend.appendChild(item)});
  }
  function updateDashboard(){if(!dataset||!geojson)return;const rows=selectedRows(),sales=sum(rows,'ACT MTD'),ly=sum(rows,'LY'),l3=sum(rows,'AVG L3M'),lm=sum(rows,'LM'),ca=sum(rows,'CUST ACT'),cr=sum(rows,'CUST REG'),rate=cr?100*ca/cr:0;$('sku-heading').textContent=`${String($('sku-filter').value).split('/').pop()} PERFORMANCE`;$('kpi-sales').textContent=money(sales);$('kpi-sales-note').innerHTML=`<span class="${growth(sales,ly)>=0?'positive':'negative'}">vs LY ${pct(growth(sales,ly))}</span> · <span class="${growth(sales,l3)>=0?'positive':'negative'}">vs Avg L3M ${pct(growth(sales,l3))}</span> · <span class="${growth(sales,lm)>=0?'positive':'negative'}">vs LM ${pct(growth(sales,lm))}</span>`;$('kpi-ca').textContent=fmt(ca);$('kpi-ca-note').textContent=`${rate.toLocaleString('id-ID',{maximumFractionDigits:1})}% dari ${fmt(cr)} registered`;$('kpi-cr').textContent=fmt(cr);$('kpi-rate').textContent=`${rate.toLocaleString('id-ID',{maximumFractionDigits:1})}%`;$('kpi-rate-note').innerHTML=`<span class="${growth(sales,ly)>=0?'positive':'negative'}">vs LY ${pct(growth(sales,ly))}</span>`;buildTable(tableRows(rows));buildProvinceCards(rows);updateMap()}

  async function init(){
    try{
      const [d,g,a,k]=await Promise.all([fetch('data/dashboard.json'),fetch('data/geojson.json'),fetch('data/assets.json'),fetch('data/kecamatan_geojson.json')]);
      if(!d.ok)throw new Error('data/dashboard.json tidak ditemukan. Jalankan scripts/export_data.py terlebih dahulu.');if(!g.ok)throw new Error('data/geojson.json tidak ditemukan. Jalankan scripts/export_data.py terlebih dahulu.');
      dataset=await d.json();geojson=await g.json();kecGeojson=k.ok?await k.json():{type:'FeatureCollection',features:[]};assetManifest=a.ok?await a.json():{};
      const entries=Object.entries(assetManifest),findAsset=aliases=>entries.find(([name])=>{const stem=name.split('/').pop().replace(/\.[^.]+$/,'').toLowerCase().replace(/[\s-]+/g,'_');return aliases.some(alias=>stem===alias||stem.startsWith(alias+'_'))});
      const logo=findAsset(['sns_group_logo']), logoEl=$('company-logo'), logoFallback=$('logo-fallback');if(logoEl){if(logo){logoEl.src=logo[1];logoEl.hidden=false;if(logoFallback)logoFallback.hidden=true}else{logoEl.addEventListener('error',()=>{logoEl.hidden=true;if(logoFallback)logoFallback.hidden=false},{once:true});logoEl.src='Assets/images/SNS_Group_Logo.png';logoEl.hidden=false;if(logoFallback)logoFallback.hidden=true}}
      const iconAliases={sales:['actual_sales','act_sales','sales_act'],ca:['customer_active','customer_act','ca'],cr:['customer_register','customer_registered','customer_registe','customer_registerd','customer_reg','cr'],rate:['pie_chart_percentage','piechart_percentage','pie_chart_percent','pie_chart_percent_age','percentage','percent']};
      document.querySelectorAll('.kpi-card').forEach((card,index)=>{const key=['sales','ca','cr','rate'][index],icon=card.querySelector('.kpi-icon'),asset=findAsset(iconAliases[key]||[]);if(icon&&asset){const img=document.createElement('img');img.src=asset[1];img.alt='';img.loading='eager';icon.replaceChildren(img);icon.setAttribute('aria-hidden','true')}});
      if(!dataset.records?.length)throw new Error('Data dashboard kosong. Periksa folder Data SKU dan kolom Excel.');
      $('sku-options').replaceChildren(...dataset.skus.map(x=>{const o=document.createElement('option');o.value=x;return o}));$('sku-filter').value=dataset.skus[0];updateSkuButton(String(dataset.skus[0]).split('/').pop());
      bindMenu('sku-menu-trigger','sku-menu');bindMenu('region-menu-trigger','region-menu');bindMenu('kecamatan-menu-trigger','kecamatan-menu');

      map=L.map('map',{scrollWheelZoom:true}).setView([-1.45,115.05],5.15);L.tileLayer('https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png?key=cb1_4uob_1_01a61b1009e12411b2c747d4',{attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',maxZoom:19}).addTo(map);
      on('sku-filter','change',()=>{if(!dataset.skus.includes($('sku-filter').value.trim()))return;updateSkuButton($('sku-filter').value.trim());refreshDepo()});on('sku-filter','keydown',e=>{if(e.key==='Enter'){e.preventDefault();const q=$('sku-filter').value.trim().toLowerCase(),match=dataset.skus.find(x=>x.toLowerCase()===q)||dataset.skus.find(x=>x.toLowerCase().includes(q));if(match){$('sku-filter').value=match;updateSkuButton(match);refreshDepo()}}});
      on('depo-filter','change',refreshRegion);on('region-filter','change',()=>{updateRegionButton($('region-filter').selectedOptions[0]?.textContent||'Semua wilayah');refreshKecamatan()});on('kecamatan-filter','change',()=>{updateKecamatanButton($('kecamatan-filter').selectedOptions[0]?.textContent||'Semua kecamatan');updateDashboard()});
      refreshDepo();renderSkuMenu();window.addEventListener('resize',()=>{if(map)map.invalidateSize()});requestAnimationFrame(()=>{if(map)map.invalidateSize()});
    }catch(err){$('status-message').textContent=`Gagal memuat dashboard: ${err.message}`;console.error(err)}
    finally{const loader=$('loading-screen');if(loader){loader.classList.add('loading-hidden');window.setTimeout(()=>loader.remove(),350)}}
  }
  console.info('[EMACO2 FIX5] dashboard.js versi 2026-10-30-fix5 dimuat');
  init();
})();
