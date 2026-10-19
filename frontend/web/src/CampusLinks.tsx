import {useEffect,useState} from 'react';
import {ArrowUpRight,MapPin} from 'lucide-react';
import {api} from './api';
import type {CampusCatalog} from './campusTypes';
import './campus-links.css';

export function LocationCards({ids,onOpen}:{ids:string[];onOpen:(id:string)=>void}) {
  const [catalog,setCatalog]=useState<CampusCatalog|null>(null);
  useEffect(()=>{let live=true;void api.campusLocations().then(data=>{if(live)setCatalog(data);}).catch(()=>{});return()=>{live=false;};},[]);
  return <div className="location-cards">{ids.map(id=>{const place=catalog?.locations.find(p=>p.id===id);return <button key={id} onClick={()=>onOpen(id)}><MapPin size={18}/><span><strong>{place?.name||'Ubicación del campus'}</strong><small>{place?.resolved_address||'Consultar la referencia y su estado'}</small></span><span className="location-card-action">Ver mapa <ArrowUpRight size={14}/></span></button>;})}</div>;
}
