export interface CampusPoint {x:number; y:number}
export interface CampusPlace {
  id:string; name:string; category:string; aliases:string[]; address:string|null;
  parent_id:string|null; parent_name:string|null; reference_point:CampusPoint|null;
  resolved_address:string|null; anchor_id:string|null; note:string;
  map_label?:string|null; reference_areas?:CampusPoint[][]; map_color?:string;
  source:{label:string; url:string|null};
}
export interface CampusCatalog {
  reviewed_at:string; reference_image:string; reference_width:number; reference_height:number;
  google_maps_url:string; locations:CampusPlace[];
}
export interface CampusReply {query:string; text:string; locations:string[]; reason:string}
export const normalizeCampus = (value:string) => value.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase();
export const googleSearch = (place:CampusPlace) => 'https://www.google.com/maps/search/?api=1&query='+encodeURIComponent(place.resolved_address || place.name+' Universidad Católica de Colombia Bogotá');
export const googleDirections = (place:CampusPlace) => 'https://www.google.com/maps/dir/?api=1&destination='+encodeURIComponent(place.resolved_address || place.name+' Universidad Católica de Colombia Bogotá')+'&travelmode=walking';
