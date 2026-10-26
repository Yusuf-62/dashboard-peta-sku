(() => {
  'use strict';
  const PROVINCES = ['Kalimantan Tengah','Kalimantan Selatan','Kalimantan Timur'];
  const COLORS = {'Kalimantan Tengah':'#43A047','Kalimantan Selatan':'#42A5F5','Kalimantan Timur':'#FBC02D'};
  const PALETTES = {'Kalimantan Tengah':['#E8F5E9','#81C784','#1B5E20'],'Kalimantan Selatan':['#E3F2FD','#64B5F6','#0D47A1'],'Kalimantan Timur':['#FFFDE7','#FFF176','#F9A825']};
  const $ = id => document.getElementById(id);
  let dataset, geojson, map, geoLayer, assetManifest = {};
  const fmt = n => (Number(n)||0).toLocaleString('id-ID',{maximumFractionDigits:0});
  const money = n => 'Rp ' + fmt(n);
  const growth = (a,b) => !b ? (a ? null : 0) : ((a/b)-1)*100;
  const pct = n => n === null || !Number.isFinite(n) ? '—' : `${n>=0?'+':''}${n.toLocaleString('id-ID',{minimumFractionDigits:1,maximumFractionDigits:1})}%`;
  const norm = s => String(s ?? '').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toUpperCase().trim().replace(/^(KABUPATEN|KAB\.|KOTA ADMINISTRASI|KOTA)\s+/,'').replace(/[^A-Z0-9]/g,'');
  const sum = (rows,key) => rows.reduce((a,r)=>a+(Number(r[key])||0),0);
  const unique = xs => [...new Set(xs)];
  function setOptions(el, items, firstLabel, selected='ALL') {
    el.innerHTML='';
    const all=document.createElement('option'); all.value='ALL'; all.textContent=firstLabel; el.appendChild(all);
    items.forEach(item=>{const o=document.createElement('option');o.value=item.value;o.textContent=item.label;el.appendChild(o)});
    el.value=[...el.options].some(o=>o.value===selected)?selected:'ALL';
  }
  function selectedRows() {
    const sku=$('sku-filter').value, depo=$('depo-filter').value, prov=$('prov-filter').value, kab=$('kab-filter').value;
    return dataset.records.filter(r => r.sku===sku && (depo==='ALL'||r.DEPO===depo) && (prov==='ALL'||r.PROVINSI===prov) && (kab==='ALL'||`${r.provinsi_key}||${r.kabupaten_key}`===kab));
  }
  function refreshDepo() {
    const sku=$('sku-filter').value;
    const depots=unique(dataset.records.filter(r=>r.sku===sku).map(r=>r.DEPO)).sort((a,b)=>a.localeCompare(b,'id'));
    setOptions($('depo-filter'),depots.map(x=>({label:x,value:x})),'Semua Depo');
    refreshProvince();
  }
  function refreshProvince() {
    const sku=$('sku-filter').value, depo=$('depo-filter').value;
    const rows=dataset.records.filter(r=>r.sku===sku&&(depo==='ALL'||r.DEPO===depo));
    const available=PROVINCES.filter(p=>rows.some(r=>norm(r.PROVINSI)===norm(p)));
    setOptions($('prov-filter'),available.map(x=>({label:x,value:x})),'Semua Provinsi');
    refreshKabupaten();
  }
  function refreshKabupaten() {
    const sku=$('sku-filter').value, depo=$('depo-filter').value, prov=$('prov-filter').value;
    const rows=dataset.records.filter(r=>r.sku===sku&&(depo==='ALL'||r.DEPO===depo)&&(prov==='ALL'||norm(r.PROVINSI)===norm(prov)));
    const geoKeys=new Set((geojson.features||[]).filter(f=>prov==='ALL'||norm(f.properties.provinsi)===norm(prov)).map(f=>`${f.properties.provinsi_key}||${f.properties.kabupaten_key}`));
    const found=new Map();
    rows.forEach(r=>{const key=`${r.provinsi_key}||${r.kabupaten_key}`; if(geoKeys.has(key)) {const f=(geojson.features||[]).find(x=>`${x.properties.provinsi_key}||${x.properties.kabupaten_key}`===key); found.set(key,`${f?.properties?.kabupaten_geo||r.KABUPATEN} — ${r.PROVINSI}`)}});
    const opts=[...found.entries()].sort((a,b)=>a[1].localeCompare(b[1],'id')).map(([value,label])=>({value,label}));
    setOptions($('kab-filter'),opts,'Semua Kabupaten');
    updateDashboard();
  }
  function filteredBaseRows() {
    const sku=$('sku-filter').value, depo=$('depo-filter').value;
    return dataset.records.filter(r=>r.sku===sku&&(depo==='ALL'||r.DEPO===depo));
  }
  function tableRows(rows) {
    const mapByKey=new Map();
    rows.forEach(r=>{const k=`${r.PROVINSI}||${r.KABUPATEN}`; if(!mapByKey.has(k))mapByKey.set(k,{PROVINSI:r.PROVINSI,KABUPATEN:r.KABUPATEN,'ACT MTD':0,LY:0,'AVG L3M':0,LM:0,'CUST ACT':0,'CUST REG':0}); const o=mapByKey.get(k);['ACT MTD','LY','AVG L3M','LM','CUST ACT','CUST REG'].forEach(c=>o[c]+=Number(r[c])||0)});
    return [...mapByKey.values()].map(r=>({...r,G_LY:growth(r['ACT MTD'],r.LY),G_L3M:growth(r['ACT MTD'],r['AVG L3M']),G_LM:growth(r['ACT MTD'],r.LM),'%CA':r['CUST REG']?100*r['CUST ACT']/r['CUST REG']:0})).sort((a,b)=>a.PROVINSI.localeCompare(b.PROVINSI,'id')||a.KABUPATEN.localeCompare(b.KABUPATEN,'id'));
  }
  function buildTable(rows) {
    const wrap=$('table-wrap'); wrap.innerHTML='';
    if(!rows.length){wrap.textContent='Tidak ada data untuk filter ini.';return;}
    const table=document.createElement('table');table.className='detail-table';
    const headers=['Provinsi','Kabupaten','Sales ACT MTD','vs LY','vs L3M','vs LM','Cust Act / Reg','%CA'];
    const thead=document.createElement('thead'),tr=document.createElement('tr');headers.forEach(h=>{const th=document.createElement('th');th.textContent=h;tr.appendChild(th)});thead.appendChild(tr);table.appendChild(thead);
    const tbody=document.createElement('tbody'); rows.forEach(r=>{const vals=[r.PROVINSI,r.KABUPATEN,fmt(r['ACT MTD']),pct(r.G_LY),pct(r.G_L3M),pct(r.G_LM),`${fmt(r['CUST ACT'])} / ${fmt(r['CUST REG'])}`,`${r['%CA'].toLocaleString('id-ID',{maximumFractionDigits:1,minimumFractionDigits:1})}%`];const tr=document.createElement('tr');vals.forEach((v,i)=>{const td=document.createElement('td');td.textContent=v;if(i>=3&&i<=5)td.className=(String(v).startsWith('+')?'positive':String(v).startsWith('-')?'negative':'');tr.appendChild(td)});tbody.appendChild(tr)});table.appendChild(tbody);wrap.appendChild(table);
  }
  function buildProvinceCards(rows) {
    const target=$('province-cards');target.innerHTML='';
    PROVINCES.forEach(p=>{const sub=rows.filter(r=>norm(r.PROVINSI)===norm(p));if(!sub.length)return;const sales=sum(sub,'ACT MTD'),ly=sum(sub,'LY'),l3=sum(sub,'AVG L3M'),lm=sum(sub,'LM'),ca=sum(sub,'CUST ACT'),reg=sum(sub,'CUST REG');const card=document.createElement('article');card.className='province-card';card.innerHTML=`<div class="province-name" style="background:${COLORS[p]}">${p}</div><div class="province-sales-label">Sales ACT MTD</div><div class="province-sales">${money(sales)}</div><div class="province-growth"><span class="${sales>=ly?'positive':'negative'}">vs LY ${pct(growth(sales,ly))}</span><br><span class="${sales>=l3?'positive':'negative'}">vs L3M ${pct(growth(sales,l3))}</span><br><span class="${sales>=lm?'positive':'negative'}">vs LM ${pct(growth(sales,lm))}</span></div><div class="province-bottom"><div>CA<strong>${fmt(ca)}</strong></div><div>CR<strong>${fmt(reg)}</strong></div><div>%CA<strong>${(reg?100*ca/reg:0).toLocaleString('id-ID',{maximumFractionDigits:1})}%</strong></div></div>`;target.appendChild(card)});
  }
  function colorFor(feature, values) {
    const p=feature.properties.provinsi, palette=PALETTES[p]||['#edf2f7','#9fb5ca','#123f70'];
    const val=Number(values.get(`${feature.properties.provinsi_key}||${feature.properties.kabupaten_key}`)?.['ACT MTD']||0);
    const provinceValues=[...values.entries()].filter(([key])=>key.startsWith(`${norm(p)}||`)).map(([,v])=>Number(v['ACT MTD'])||0);
    const max=Math.max(1,...provinceValues), t=Math.max(0,Math.min(1,val/max));
    const a=hexRgb(palette[0]),b=hexRgb(palette[1]),c=hexRgb(palette[2]);
    return t<.5?mix(a,b,t*2):mix(b,c,(t-.5)*2);
  }
  function hexRgb(h){const x=h.replace('#','');return [parseInt(x.slice(0,2),16),parseInt(x.slice(2,4),16),parseInt(x.slice(4,6),16)]}
  function mix(a,b,t){return '#'+a.map((v,i)=>Math.round(v+(b[i]-v)*t).toString(16).padStart(2,'0')).join('')}
  function updateMap(rows) {
    const base=filteredBaseRows(), mapAgg=new Map();
    base.forEach(r=>{const key=`${r.provinsi_key}||${r.kabupaten_key}`;if(!mapAgg.has(key))mapAgg.set(key,{'ACT MTD':0,'CUST ACT':0,'CUST REG':0});['ACT MTD','CUST ACT','CUST REG'].forEach(k=>mapAgg.get(key)[k]+=Number(r[k])||0)});
    const prov=$('prov-filter').value,kab=$('kab-filter').value;
    const features=(geojson.features||[]).filter(f=>(prov==='ALL'||norm(f.properties.provinsi)===norm(prov))&&(kab==='ALL'||`${f.properties.provinsi_key}||${f.properties.kabupaten_key}`===kab));
    if(geoLayer)map.removeLayer(geoLayer);
    geoLayer=L.geoJSON({type:'FeatureCollection',features},{style:f=>({fillColor:colorFor(f,mapAgg),weight:1,color:'#fff',fillOpacity:.9}),onEachFeature:(f,layer)=>{const p=f.properties,key=`${p.provinsi_key}||${p.kabupaten_key}`,v=mapAgg.get(key)||{'ACT MTD':0,'CUST ACT':0,'CUST REG':0};layer.bindTooltip(`<b>${p.kabupaten_geo}</b><br>${p.provinsi}<br>ACT MTD: ${money(v['ACT MTD'])}<br>Cust Active: ${fmt(v['CUST ACT'])}<br>Cust Registered: ${fmt(v['CUST REG'])}`);layer.on('click',()=>{const optValue=key;if([...$('kab-filter').options].some(o=>o.value===optValue)){$('kab-filter').value=optValue;updateDashboard()}})}}).addTo(map);
    if(features.length){const bounds=geoLayer.getBounds();if(bounds.isValid()){map.fitBounds(bounds,{padding:[18,18],maxZoom:kab!=='ALL'?8:prov!=='ALL'?7:6})}} else map.setView([-1.45,115.05],5.15);
    const legend=$('map-legend');legend.innerHTML='';PROVINCES.forEach(p=>{if(prov!=='ALL'&&prov!==p)return;const item=document.createElement('div');item.className='legend-item';item.innerHTML=`<span class="legend-dot" style="background:${COLORS[p]}"></span><strong>${p}</strong><span>rendah → tinggi</span>`;legend.appendChild(item)});
  }
  function updateDashboard() {
    if(!dataset||!geojson)return;
    const rows=selectedRows(),sales=sum(rows,'ACT MTD'),ly=sum(rows,'LY'),l3=sum(rows,'AVG L3M'),lm=sum(rows,'LM'),ca=sum(rows,'CUST ACT'),cr=sum(rows,'CUST REG'),rate=cr?100*ca/cr:0;
    $('sku-heading').textContent=`${$('sku-filter').value} PERFORMANCE`;
    $('kpi-sales').textContent=money(sales);$('kpi-sales-note').innerHTML=`<span class="${growth(sales,ly)>=0?'positive':'negative'}">vs LY ${pct(growth(sales,ly))}</span> · <span class="${growth(sales,l3)>=0?'positive':'negative'}">vs Avg L3M ${pct(growth(sales,l3))}</span> · <span class="${growth(sales,lm)>=0?'positive':'negative'}">vs LM ${pct(growth(sales,lm))}</span>`;
    $('kpi-ca').textContent=fmt(ca);$('kpi-ca-note').textContent=`${rate.toLocaleString('id-ID',{maximumFractionDigits:1})}% dari ${fmt(cr)} registered`;$('kpi-cr').textContent=fmt(cr);$('kpi-rate').textContent=`${rate.toLocaleString('id-ID',{maximumFractionDigits:1})}%`;$('kpi-rate-note').innerHTML=`<span class="${growth(sales,ly)>=0?'positive':'negative'}">vs LY ${pct(growth(sales,ly))}</span>`;
    buildTable(tableRows(rows));buildProvinceCards(rows);updateMap(rows);
  }
  async function init() {
    try {
      const [d,g,a]=await Promise.all([fetch('data/dashboard.json'),fetch('data/geojson.json'),fetch('data/assets.json')]);
      if(!d.ok)throw new Error('data/dashboard.json tidak ditemukan. Jalankan scripts/export_data.py terlebih dahulu.');
      if(!g.ok)throw new Error('data/geojson.json tidak ditemukan. Jalankan scripts/export_data.py terlebih dahulu.');
      dataset=await d.json();geojson=await g.json();assetManifest=a.ok?await a.json():{};
      const logo=Object.entries(assetManifest).find(([name])=>name.toLowerCase().startsWith('sns_group_logo'));
      if(logo){$('company-logo').src=logo[1];$('company-logo').hidden=false;$('logo-fallback').hidden=true}
      if(!dataset.records?.length)throw new Error('Data dashboard kosong. Periksa folder Data SKU dan kolom Excel.');
      setOptions($('sku-filter'),dataset.skus.map(x=>({label:x,value:x})),'Pilih SKU',dataset.skus[0]);
      map=L.map('map',{scrollWheelZoom:true}).setView([-1.45,115.05],5.15);
      L.tileLayer('https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png?key=cb1_4uob_1_01a61b1009e12411b2c747d4',{attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',maxZoom:19}).addTo(map);
      $('sku-filter').addEventListener('change',refreshDepo);$('depo-filter').addEventListener('change',refreshProvince);$('prov-filter').addEventListener('change',refreshKabupaten);$('kab-filter').addEventListener('change',updateDashboard);
      refreshDepo();
      window.addEventListener('resize', () => { if (map) map.invalidateSize(); });
      requestAnimationFrame(() => { if (map) map.invalidateSize(); });
    } catch(err) { $('status-message').textContent=`Gagal memuat dashboard: ${err.message}`; console.error(err); }
  }
  init();
})();
