import {useEffect, useRef, useState, type FormEvent} from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import {ArrowLeft, ArrowUpRight, Building2, ChevronRight, Compass, ExternalLink, MapPin, MessageCircle, Navigation, Search, Send, ShieldCheck} from 'lucide-react';
import {api} from './api';
import {googleDirections, googleSearch, normalizeCampus, type CampusCatalog, type CampusPlace, type CampusReply} from './campusTypes';
import './campus.css';

export default function CampusMap({selectedId,candidateIds=[],onSelect,onBack,onAsk}:{selectedId:string|null;candidateIds?:string[];onSelect:(id:string)=>void;onBack:()=>void;onAsk:(question:string)=>void}) {
  const [catalog,setCatalog]=useState<CampusCatalog|null>(null);
  const [error,setError]=useState('');const [retry,setRetry]=useState(0);
  const [search,setSearch]=useState('');const [category,setCategory]=useState('all');
  const [showMatches,setShowMatches]=useState(candidateIds.length>1);
  const [question,setQuestion]=useState('');const [busy,setBusy]=useState(false);
  const [answers,setAnswers]=useState<CampusReply[]>([]);
  const container=useRef<HTMLDivElement>(null);const map=useRef<L.Map|null>(null);
  const markers=useRef(new Map<string,L.Marker>());const currentSelect=useRef(onSelect);
  const areas=useRef(new Map<string,L.Polygon[]>());
  const selectedRef=useRef(selectedId);const locked=useRef(false);const live=useRef(true);
  currentSelect.current=onSelect;selectedRef.current=selectedId;
  useEffect(()=>{live.current=true;return()=>{live.current=false;};},[]);
  useEffect(()=>{let active=true;setError('');void api.campusLocations().then(data=>{if(active)setCatalog(data);}).catch(e=>{if(active)setError(e instanceof Error?e.message:'No se pudo cargar el directorio.');});return()=>{active=false;};},[retry]);
  const selected=catalog?.locations.find(p=>p.id===selectedId)||null;
  useEffect(()=>{
    if(!catalog||!container.current)return;
    const bounds=L.latLngBounds([[0,0],[catalog.reference_height,catalog.reference_width]]);
    const instance=L.map(container.current,{crs:L.CRS.Simple,minZoom:-3,maxZoom:2,zoomSnap:.25,zoomControl:false,dragging:false,boxZoom:false,keyboard:false,scrollWheelZoom:'center',doubleClickZoom:'center',maxBounds:bounds,maxBoundsViscosity:1});
    map.current=instance;
    L.control.zoom({position:'bottomleft'}).addTo(instance);
    instance.attributionControl.setPrefix(false);
    instance.attributionControl.addAttribution('Plano Catalina · posiciones de referencia');
    L.imageOverlay(catalog.reference_image,bounds,{alt:'Mapa de referencia del entorno de la Universidad Católica de Colombia'}).addTo(instance);
    instance.fitBounds(bounds,{padding:[18,18]});
    instance.setMinZoom(instance.getZoom());
    catalog.locations.forEach(place=>{
      const shapes=(place.reference_areas||[]).map(area=>{
        const shape=L.polygon(area.map(p=>[catalog.reference_height*(1-p.y),catalog.reference_width*p.x] as [number,number]),{color:place.map_color||'#087faa',weight:0,fillOpacity:0}).addTo(instance);
        const label=document.createElement('span');label.textContent=place.name;
        shape.bindTooltip(label,{className:'campus-place-label',sticky:true});
        shape.on('click',()=>currentSelect.current(place.id));return shape;
      });
      areas.current.set(place.id,shapes);
    });
    const points=catalog.locations.filter(p=>p.reference_point&&p.map_label);
    points.forEach(place=>{
      const point=place.reference_point!;
      const icon=L.divIcon({className:'campus-marker '+(place.parent_id?'campus-submarker':'campus-site-marker'),html:`<span>${place.map_label}</span>`,iconSize:[36,32],iconAnchor:[18,16]});
      const marker=L.marker([catalog.reference_height*(1-point.y),catalog.reference_width*point.x],{icon,title:place.name,alt:place.name}).addTo(instance);
      const tooltip=document.createElement('span');tooltip.textContent=place.name;
      marker.bindTooltip(tooltip,{direction:'top',offset:[0,-18],className:'campus-place-label'});
      marker.on('click',()=>currentSelect.current(place.id));
      marker.getElement()?.setAttribute('aria-label','Seleccionar '+place.name);
      markers.current.set(place.id,marker);
    });
    const updateDetail=()=>container.current?.classList.toggle('map-overview-small',instance.getZoom()<-.5);
    instance.on('zoomend',updateDetail);updateDetail();
    const observer=new ResizeObserver(()=>{instance.invalidateSize();instance.setMinZoom(-3);instance.fitBounds(bounds,{padding:[18,18]});instance.setMinZoom(instance.getZoom());});observer.observe(container.current);
    return()=>{observer.disconnect();markers.current.clear();areas.current.clear();instance.remove();map.current=null;};
  },[catalog]);
  useEffect(()=>{
    if(!catalog||!map.current)return;
    const place=catalog.locations.find(p=>p.id===selectedId);
    for(const [id,marker] of markers.current){const active=id===place?.anchor_id;marker.getElement()?.classList.toggle('active',active);if(active)marker.openTooltip();else marker.closeTooltip();}
    for(const [id,shapes] of areas.current){const active=id===place?.id;const parent=id===place?.parent_id;for(const shape of shapes)shape.setStyle({color:active?'#fff':parent?'#fff':catalog.locations.find(p=>p.id===id)?.map_color,weight:active?4:parent?3:0,fillColor:'#fff',fillOpacity:active ? .18 : parent ? .08 : 0});}
  },[catalog,selectedId]);
  function overview(){if(catalog&&map.current)map.current.fitBounds([[0,0],[catalog.reference_height,catalog.reference_width]],{padding:[18,18]});}
  function ask(event:FormEvent){event.preventDefault();const query=question.trim();if(!query||locked.current)return;locked.current=true;setBusy(true);setError('');const context=selectedId;void api.campusQuestion(query,context).then(answer=>{if(!live.current)return;setAnswers(rows=>[...rows,answer]);setQuestion('');if(answer.locations.length===1&&selectedRef.current===context)onSelect(answer.locations[0]);}).catch(e=>{if(live.current)setError(e instanceof Error?e.message:'No se pudo consultar el mapa.');}).finally(()=>{locked.current=false;if(live.current)setBusy(false);});}
  const shown=catalog?.locations.filter(place=>{
    const matches=normalizeCampus([place.name,...place.aliases,place.parent_name||''].join(' ')).includes(normalizeCampus(search));
    return matches&&(!showMatches||!!search||candidateIds.includes(place.id))&&(category==='all'||(category==='pending'?!place.anchor_id:place.category===category));
  })||[];
  return <section className="campus-panel" aria-label="Mapa interactivo del campus">
    <header className="campus-header"><div className="campus-heading-icon"><MapPin size={23}/></div><div><span className="eyebrow">EXPLORA TU UNIVERSIDAD</span><h2>Mapa del campus</h2><p>Selecciona una dependencia o pregúntale al mapa.</p></div><button className="campus-return" onClick={onBack}><ArrowLeft size={16}/> Volver al chat</button></header>
    {!catalog ? <div className="campus-loading" role="status">{error||'Cargando el directorio del campus…'}{error&&<button onClick={()=>setRetry(n=>n+1)}>Reintentar</button>}</div> : <div className="map-workbench">
      <div className="map-visual"><div ref={container} className="campus-canvas" aria-label="Referencia visual con marcadores seleccionables"/><div className="map-caption"><span className="map-caption-dot"/> PLANO DEL CAMPUS <span>{catalog.locations.filter(p=>p.reference_point).length} marcadores orientativos</span></div><button className="map-reset" onClick={overview}><Compass size={17}/> Ver todo</button><div className="map-reference-note">Caracas en rojo · Carrera Séptima en azul · zoom disponible · plano fijo.</div></div>
      <aside className="map-directory"><div className="directory-top"><div><strong>Encuentra tu lugar</strong><span>{catalog.locations.length} ubicaciones y dependencias</span></div><MapPin size={21}/></div><label className="map-search"><Search size={17}/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Buscar sede o dependencia…" aria-label="Buscar en el mapa"/></label><select className="map-filter" value={category} onChange={e=>setCategory(e.target.value)} aria-label="Filtrar ubicaciones"><option value="all">Todas las ubicaciones</option><option value="sede">Sedes</option><option value="facultad">Facultades</option><option value="servicio">Servicios</option><option value="pending">Sin marcador confirmado</option></select>
      <div className="map-match-hint">{showMatches&&<>Coinciden {candidateIds.length} ubicaciones. <button onClick={()=>setShowMatches(false)}>Ver todo el directorio</button></>}</div><nav className="map-place-list" aria-label="Dependencias del campus">{shown.map(place=><button key={place.id} onClick={()=>onSelect(place.id)} aria-pressed={selectedId===place.id} className={selectedId===place.id?'selected':''}>{place.reference_point?<MapPin size={17}/>:<Building2 size={17}/>}<span><strong>{place.name}</strong><small>{place.parent_name||(place.anchor_id?'Referencia en el mapa':'Marcador por confirmar')}</small></span><ChevronRight size={14}/></button>)}{!shown.length&&<p>No encontramos ese nombre. Prueba otra dependencia.</p>}</nav>
      {selected ? <section className="map-place-detail" aria-label="Ubicación seleccionada"><span className={'place-status '+(selected.anchor_id?'located':'pending')}>{selected.reference_point?'Marcador orientativo':selected.anchor_id?'Referencia de su sede':'Punto pendiente de confirmar'}</span><h3>{selected.name}</h3>{selected.parent_name&&<p className="place-parent">{selected.parent_name}</p>}<p className="place-address"><MapPin size={16}/>{selected.resolved_address||'Dirección exacta por confirmar'}</p><p className="place-note">{selected.note}</p>{selected.source.url?<a className="place-source" href={selected.source.url} target="_blank" rel="noreferrer"><ShieldCheck size={13}/>{selected.source.label}<ExternalLink size={12}/></a>:<span className="place-source">{selected.source.label}</span>}<div className="place-directions"><a href={selected.resolved_address?googleDirections(selected):googleSearch(selected)} target="_blank" rel="noreferrer"><Navigation size={15}/>{selected.resolved_address?'Cómo llegar':'Buscar en Google Maps'}<ArrowUpRight size={15}/></a><button onClick={()=>onAsk('¿Dónde queda '+selected.name+'?')} aria-label="Preguntar por esta ubicación en el chat"><MessageCircle size={16}/></button></div></section> : <div className="map-place-empty"><Compass size={30}/><strong>¿A dónde quieres ir?</strong><p>Elige un marcador o busca una dependencia en el directorio.</p><a href={catalog.google_maps_url} target="_blank" rel="noreferrer">Abrir referencia en Google Maps <ArrowUpRight size={14}/></a></div>}
      <div className="map-chat"><div className="map-chat-title"><img src="/brand/catalina.svg" alt=""/><div><strong>Pregúntale a este mapa</strong><span>Directorio consultable · sin ubicaciones inventadas</span></div></div>{answers.length>0&&<div className="map-chat-log" role="log" aria-live="polite">{answers.map((answer,i)=><article key={i}><strong>{answer.query}</strong><p>{answer.text}</p>{answer.locations.map(id=><button key={id} onClick={()=>onSelect(id)}><MapPin size={12}/>{catalog.locations.find(p=>p.id===id)?.name||id}</button>)}</article>)}</div>}<div className="map-question-suggestions"><button disabled={busy||!selected} onClick={()=>setQuestion('¿Cuál es la dirección?')}>Dirección</button><button disabled={busy||!selected} onClick={()=>setQuestion('¿Qué dependencias hay aquí?')}>Dependencias de esta sede</button></div><form onSubmit={ask}><label className="sr-only" htmlFor="map-question">Pregunta sobre el mapa</label><textarea id="map-question" rows={2} maxLength={1000} value={question} onChange={e=>setQuestion(e.target.value)} placeholder="Ej. ¿Dónde queda Bienestar?" disabled={busy}/><button disabled={busy||!question.trim()} aria-label="Enviar pregunta al mapa"><Send size={17}/></button></form>{busy&&<small role="status">Consultando el directorio…</small>}</div>
      <p className="directory-review">Directorio revisado: {catalog.reviewed_at}. Las ubicaciones pendientes se completan con confirmación.</p>
      </aside>
    </div>}{error&&catalog&&<div className="error" role="alert">{error}</div>}
  </section>;
}
