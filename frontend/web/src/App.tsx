import {lazy, Suspense, useEffect, useRef, useState, type FormEvent} from 'react';
import {ArrowDown, ArrowRight, ArrowUpRight, BookOpen, Check, ChevronLeft, Compass, FileText, GraduationCap, History, MapPin as MapPinIcon, LogOut, Maximize2, MessageCircle, Moon, Plus, Search, Send, ShieldCheck, Sun, Trash2, X, Pencil, RefreshCw} from 'lucide-react';
import {api} from './api';
import Mascot from './Mascot';
import {LocationCards} from './CampusLinks';
const CampusMap=lazy(()=>import('./CampusMap'));
import type {Conversation, Message, Source, User} from './types';
const prompts = [
  {icon: GraduationCap, title:'Soy estudiante nuevo', text:'¿Qué debo conocer como estudiante nuevo de la universidad?'},
  {icon: BookOpen, title:'Trámites académicos', text:'¿Cómo puedo solicitar un certificado de estudios?'},
  {icon: Compass, title:'Ubícate en la universidad', text:'¿Dónde están las sedes de la universidad?'},
  {icon: FileText, title:'Reglamento y calendario', text:'¿Qué documentos puedo consultar sobre el reglamento y el calendario académico?'}
];
const errorText = (e: unknown) => e instanceof Error ? e.message : 'Ocurrió un error. Inténtalo nuevamente.';
function responseLabel(kind?: string) {
  if (kind === 'campus_location') return 'Directorio del campus · ubicación registrada';
  if (kind === 'document_overview') return 'Vista del índice · extracción documental';
  if (kind === 'document_excerpt') return 'Pasajes textuales · extracción documental';
  if (kind === 'generated' || kind === 'general_chat') return 'Generada por Ollama';
  if (kind === 'cached') return 'Respuesta de Ollama reutilizada';
  if (kind === 'conversational') return 'Respuesta directa · saludo';
  if (kind === 'document_identifier_resolved') return 'Identificador tomado del documento';
  if (kind) return 'Consulta documental · evidencia insuficiente';
  return 'Historial · método de respuesta no disponible';
}
function Avatar({large = false}: {large?: boolean}) {return <span className={'avatar ' + (large ? 'large' : '')}><img src="/brand/catalina-avatar.png" alt=""/></span>;}
function Sources({items, text}: {items: Source[] | undefined; text: string}) {
  if (!items) return /\[S\d+\]/.test(text) ? <small className="source-note">Las citas de este mensaje no están disponibles en el historial de la API.</small> : null;
  if (!items.length) return null;
  return <details className="sources"><summary><FileText size={15}/> Consultar {items.length} fuente{items.length > 1 ? 's' : ''}</summary>{items.map(s => <div className="source" key={s.citation_id}><strong>{s.citation_id} · {s.document_name}</strong><span>Versión {s.version}{s.page_start !== null ? ` · Pág. ${s.page_start}${s.page_end !== null && s.page_end !== s.page_start ? '–' + s.page_end : ''}` : ''}</span>{s.section && <span>{s.section}</span>}</div>)}</details>;
}
export default function App() {
  const [full, setFull] = useState(location.hash === '#/chat');
  const [open, setOpen] = useState(false);
  const [user, setUser] = useState<User | null>(null);
  const [email, setEmail] = useState(''); const [password, setPassword] = useState('');
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [active, setActive] = useState<number | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [guestMessages, setGuestMessages] = useState<Message[]>([]);
  const [mobileMenu, setMobileMenu] = useState(false);
  const [draft, setDraft] = useState(''); const [search, setSearch] = useState('');
  const [elapsed, setElapsed] = useState(0);
  const [busy, setBusy] = useState(false); const [pending, setPending] = useState('');
  const [error, setError] = useState(''); const [health, setHealth] = useState('Comprobando conexión…');
  const [dark, setDark] = useState(() => {try {return localStorage.getItem('catalina-theme') === 'dark';} catch {return false;}});
  const [sidebar, setSidebar] = useState(false);
  const [mapOpen,setMapOpen]=useState(false);
  const [mapCandidates,setMapCandidates]=useState<string[]>([]);
  const [selectedLocation,setSelectedLocation]=useState<string|null>(null);
  const locationIds=useRef(new Map<number,string[]>());
  const bottom = useRef<HTMLDivElement>(null); const launcher = useRef<HTMLButtonElement>(null);
  const chatHeading = useRef<HTMLHeadingElement>(null);
  const responseKinds = useRef(new Map<number, string>());
  const citations = useRef(new Map<number, Source[]>());
  const epoch = useRef(0); const locked = useRef(false);
  useEffect(() => {const update = () => setFull(location.hash === '#/chat'); window.addEventListener('hashchange', update);return () => window.removeEventListener('hashchange', update);}, []);
  useEffect(() => {document.documentElement.dataset.theme = dark ? 'dark' : 'light';try {localStorage.setItem('catalina-theme', dark ? 'dark' : 'light');} catch {}}, [dark]);
  useEffect(() => {void checkHealth();}, []);
  useEffect(() => {bottom.current?.scrollIntoView({behavior:'smooth', block:'end'});}, [messages, guestMessages, pending]);
  useEffect(() => {if (open || full) chatHeading.current?.focus();}, [open, full]);
  useEffect(() => {
    const expired = () => {epoch.current++; setUser(null); setMessages([]); setConversations([]);setActive(null);citations.current.clear();responseKinds.current.clear();locationIds.current.clear();setError('Tu sesión terminó. Inicia sesión nuevamente.');};
    window.addEventListener('catalina:expired', expired);return () => window.removeEventListener('catalina:expired', expired);
  }, []);
  useEffect(() => {
    if (!pending) {setElapsed(0);return;}
    const started = performance.now();
    const timer = window.setInterval(() => setElapsed(Math.floor((performance.now() - started) / 1000)), 1000);
    return () => window.clearInterval(timer);
  }, [pending]);
  async function checkHealth() {setHealth('Comprobando conexión…');try {await api.health();setHealth('API conectada');}catch {setHealth('Sin conexión con la API');}}
  async function action(task: () => Promise<void>) {
    if (locked.current) return;
    locked.current = true;setBusy(true);setError('');
    try {await task();} catch(e) {setError(errorText(e));} finally {locked.current = false;setBusy(false);}
  }
  async function refreshHistory() {const current = epoch.current;const rows = await api.conversations();if(current === epoch.current) setConversations(rows);}
  function goFull() {setOpen(false);location.hash = '/chat';setFull(true);}
  function openCampus(id?:string) {setMapCandidates([]);if(id)setSelectedLocation(id);setMapOpen(true);setSidebar(false);if(!full)goFull();}
  function goPortal() {setMapOpen(false);location.hash = '/';setFull(false);}
  function closeWidget() {setOpen(false);launcher.current?.focus();}
  function newChat() {if (busy) return;setMapOpen(false);setActive(null);setMessages([]);setDraft('');setError('');setSidebar(false);}
  function choosePrompt(text: string) {if (busy) return;setDraft(text);if (!full) setOpen(true);}
  function login(event: FormEvent) {event.preventDefault();void action(async () => {
    const account = await api.login(email.trim(), password);epoch.current++;setUser(account);setPassword('');await refreshHistory();
  });}
  function loadConversation(id: number) {void action(async () => {
    const current = epoch.current;const rows = await api.messages(id);if (current !== epoch.current) return;
    setMessages(rows.map(m => ({...m,citations:citations.current.get(m.id),responseKind:responseKinds.current.get(m.id),locationIds:locationIds.current.get(m.id)})));setActive(id);setDraft('');setSidebar(false);
  });}
  function send(event: FormEvent) {event.preventDefault();const query = draft.trim();if (!query || (full && !user)) return;
    if (!user) {
      void action(async () => {
        setPending(query);
      const started = performance.now();
        try {
          const answer = await api.guestAnswer(query);
          setGuestMessages(rows => [...rows, {id: Date.now(), conversacion_id: 0, pregunta: query, respuesta: answer.text, fecha: new Date().toISOString(), citations: answer.citations, responseKind: answer.reason, locationIds:answer.locations||[], responseSeconds: (performance.now() - started) / 1000}]);
          setDraft('');
        } finally {setPending('');}
      });
      return;
    }
    void action(async () => {
      const current = epoch.current;let id = active;
      if (id === null) {const conversation = await api.create(query.slice(0,160));if(current !== epoch.current) return;id = conversation.id;setActive(id);setConversations(c => [conversation, ...c]);}
      setPending(query);
      const started = performance.now();
      try {
        const answer = await api.answer(id, query);if(current !== epoch.current) return;
        citations.current.set(answer.message_id, answer.citations);responseKinds.current.set(answer.message_id, answer.reason);locationIds.current.set(answer.message_id,answer.locations||[]);
        if(answer.reason==='campus_location'){setSelectedLocation(answer.locations?.length===1?answer.locations[0]:null);setMapCandidates(answer.locations||[]);setMapOpen(true);}
        setMessages(rows => [...rows, {id:answer.message_id,conversacion_id:id!,pregunta:answer.query,respuesta:answer.text,fecha:new Date().toISOString(),citations:answer.citations,responseKind:answer.reason,locationIds:answer.locations||[],responseSeconds:(performance.now()-started)/1000}]);setDraft('');await refreshHistory();
      } finally {setPending('');}
    });
  }
  function rename() {if(active === null || busy) return;const title = window.prompt('Nombre de la conversación',conversations.find(c=>c.id===active)?.titulo);if(!title?.trim()) return;
    void action(async()=>{await api.rename(active,title.trim().slice(0,160));await refreshHistory();});}
  function remove() {if(active === null || busy || !window.confirm('¿Eliminar esta conversación y sus mensajes?')) return;
    void action(async()=>{await api.remove(active);setActive(null);setMessages([]);setDraft('');await refreshHistory();});}
  const title = conversations.find(c=>c.id===active)?.titulo || 'Nueva conversación';
  const visibleMessages = user ? messages : guestMessages;
  const chat = <section className={'chat-shell ' + (full ? 'expanded' : 'compact')} aria-label="Chat con Catalina" onKeyDown={e=>{if(e.key==='Escape' && !full) closeWidget();}}>
    <header className="chat-header"><Avatar/><div><h2 tabIndex={-1} ref={chatHeading}>Catalina</h2><span>Tu asistente universitario</span></div><div className="header-actions"><button className="icon-btn" onClick={()=>setDark(!dark)} aria-label={dark ? 'Activar modo claro' : 'Activar modo oscuro'}>{dark ? <Sun size={19}/> : <Moon size={19}/>}</button>{!full && <><button className="icon-btn" onClick={goFull} aria-label="Ampliar chat"><Maximize2 size={19}/></button><button className="icon-btn" onClick={closeWidget} aria-label="Cerrar chat"><X size={20}/></button></>}</div></header>
    {user && <div className="conversation-bar"><span>{title}</span><button className="icon-btn" disabled={busy} onClick={newChat} aria-label="Nueva conversación"><Plus size={17}/></button>{active !== null && <><button className="icon-btn" disabled={busy} onClick={rename} aria-label="Renombrar conversación"><Pencil size={16}/></button><button className="icon-btn" disabled={busy} onClick={remove} aria-label="Eliminar conversación"><Trash2 size={16}/></button></>}</div>}
    <div className="chat-body">
      {!user && full ? <div className="login-panel"><Mascot pose="standing" className="login-mascot"/><span className="eyebrow">BIENVENIDO A CATALINA</span><h3>Tu espacio.<br/>Tu conversación.</h3><p>Inicia sesión para continuar en el chat ampliado y guardar tus conversaciones. Puedes volver al portal para hacer consultas rápidas sin registro.</p><form onSubmit={login}><label htmlFor="email">Correo electrónico</label><input id="email" type="email" autoComplete="username" required value={email} onChange={e=>setEmail(e.target.value)} disabled={busy}/><label htmlFor="password">Contraseña</label><input id="password" type="password" autoComplete="current-password" required value={password} onChange={e=>setPassword(e.target.value)} disabled={busy}/><button className="primary" disabled={busy}>{busy ? 'Ingresando…' : 'Iniciar sesión'}<ArrowRight size={18}/></button></form><small>Usa una cuenta ya creada en Catalina. El acceso con Microsoft se incorporará más adelante.</small></div> : <>
      {!visibleMessages.length && !pending && <div className="welcome"><Mascot pose="wave" className="welcome-mascot"/><span className="eyebrow">UN ESPACIO PARA TUS PREGUNTAS</span><h3>Hola, {user ? user.nombre.split(' ')[0] : 'qué gusto verte'}.<br/>¿En qué te puedo ayudar?</h3><p>Conversemos, resolvamos tus dudas y consultemos documentos cuando necesites información de tu universidad.</p><div className="prompt-grid">{prompts.map(({icon:Icon,title,text})=><button key={title} disabled={busy} onClick={()=>setDraft(text)}><Icon size={21}/><span>{title}</span><ArrowUpRight size={16}/></button>)}</div></div>}
      <div className="messages" role="log" aria-label="Mensajes de la conversación" aria-live="polite">{visibleMessages.map(m=><article className="exchange" key={m.id}><div className="question">{m.pregunta}</div><div className="answer"><div className="answer-label"><Avatar/> CATALINA</div><div className="response-kind">{responseLabel(m.responseKind)}</div><div className="answer-text">{m.respuesta}</div><small className="response-time">{m.responseSeconds !== undefined ? `Respuesta en ${m.responseSeconds.toFixed(1)} s` : ''}</small><Sources items={m.citations} text={m.respuesta}/>{!!m.locationIds?.length&&<LocationCards ids={m.locationIds} onOpen={openCampus}/>}</div></article>)}{pending && <article className="exchange"><div className="question">{pending}</div><div className="thinking" role="status"><span/>Catalina está preparando tu respuesta… {elapsed > 0 && <small>{elapsed} s</small>}</div></article>}<div ref={bottom}/></div>
      </>}
    </div>
    {error && <div className="error" role="alert">{error}</div>}
    {(user || !full) && <form className="composer" onSubmit={send}><label className="sr-only" htmlFor="question">Tu pregunta para Catalina</label><div className="input-wrap"><textarea id="question" rows={2} maxLength={1000} placeholder="Escribe tu pregunta…" value={draft} disabled={busy} onChange={e=>setDraft(e.target.value)} onKeyDown={e=>{if(e.key==='Enter' && !e.shiftKey && !e.nativeEvent.isComposing){e.preventDefault();e.currentTarget.form?.requestSubmit();}}}/><button disabled={busy || !draft.trim()} aria-label="Enviar pregunta"><Send size={19}/></button></div><small>Revisa las fuentes y confirma los trámites con el área responsable.</small></form>}
    <footer className="chat-footer"><ShieldCheck size={13}/> {!user && !full ? 'Sin registro · Preguntas independientes' : 'Información institucional con fuentes'}{!full && user && <button onClick={goFull}>Ver historial <ArrowRight size={12}/></button>}</footer>
  </section>;
  return <>
    {full ? <div className="workspace"><aside className={'sidebar ' + (sidebar?'visible':'')}><button className="back" onClick={goPortal}><ChevronLeft size={17}/> Volver al portal</button><div className="brand"><Avatar/><div><strong>CATALINA</strong><small>Asistente virtual</small></div></div><button className="new-chat" disabled={busy || !user} onClick={newChat}><Plus size={18}/> Nueva conversación</button><div className="history-title"><History size={15}/> TUS CONVERSACIONES</div><label className="search"><Search size={16}/><input aria-label="Buscar conversaciones" placeholder="Buscar…" value={search} onChange={e=>setSearch(e.target.value)}/></label><nav className="history-list" aria-label="Historial">{conversations.filter(c=>c.titulo.toLocaleLowerCase().includes(search.toLocaleLowerCase())).map(c=><button key={c.id} className={active===c.id?'selected':''} disabled={busy} onClick={()=>loadConversation(c.id)}><MessageCircle size={16}/><span>{c.titulo}</span></button>)}{!conversations.length && <p>{user?'Aquí aparecerán tus conversaciones.':'Inicia sesión para consultar tu historial.'}</p>}</nav>{user && <div className="user-box"><span className="initial">{user.nombre.charAt(0)}</span><div><strong>{user.nombre}</strong><small>{user.email}</small></div><button className="icon-btn" disabled={busy} aria-label="Cerrar sesión" onClick={()=>void action(async()=>{await api.logout();epoch.current++;setUser(null);setMessages([]);setConversations([]);setActive(null);citations.current.clear();responseKinds.current.clear();locationIds.current.clear();})}><LogOut size={18}/></button></div>}<button className="connection" onClick={checkHealth}><span className={health==='API conectada'?'dot online':'dot'}/>{health}<RefreshCw size={12}/></button></aside><main className="main-chat"><button className="mobile-history" onClick={()=>setSidebar(!sidebar)}><History size={17}/>{sidebar?'Ocultar historial':'Ver historial'}</button><nav className="workspace-tabs" aria-label="Vista del asistente"><button className={!mapOpen?'active':''} aria-pressed={!mapOpen} onClick={()=>setMapOpen(false)}><MessageCircle size={16}/> Conversación</button><button className={mapOpen&&user?'active':''} aria-pressed={mapOpen&&!!user} disabled={!user} title={!user?'Inicia sesión para abrir el mapa':undefined} onClick={()=>openCampus()} aria-label="Mostrar mapa del campus"><Compass size={16}/> Mapa del campus</button><span>Universidad Católica de Colombia</span>{mapOpen&&user&&<button className="workspace-theme" onClick={()=>setDark(!dark)} aria-label={dark ? 'Activar modo claro' : 'Activar modo oscuro'}>{dark?<Sun size={18}/>:<Moon size={18}/>}</button>}</nav>{mapOpen&&user?<Suspense fallback={<div className="campus-loading">Abriendo el mapa del campus…</div>}><CampusMap selectedId={selectedLocation} candidateIds={mapCandidates} onSelect={setSelectedLocation} onBack={()=>setMapOpen(false)} onAsk={question=>{setDraft(question);setMapOpen(false);}}/></Suspense>:chat}</main></div> : <div className="portal portal-f">
      <a className="skip-portal" href="#portal-content">Saltar al contenido</a>
      <div className="portal-utility"><span>CATALINA · PROTOTIPO ACADÉMICO</span><div><a href="https://www.ucatolica.edu.co/portal/" target="_blank" rel="noreferrer">Sitio institucional <ArrowUpRight size={12}/></a><span className="utility-separator"/><button onClick={goFull}>Mi espacio <ArrowRight size={12}/></button></div></div>
      <header className="portal-navigation"><a className="portal-product independent-brand" href="#/" aria-label="Catalina, inicio"><Avatar/><span>CATALINA<small>Asistente académico independiente</small></span></a><span className="portal-brand-rule"/><div className="portal-context"><span>INFORMACIÓN UNIVERSITARIA</span><strong>Universidad Católica de Colombia</strong></div><button className="menu-toggle" aria-label="Abrir navegación" aria-expanded={mobileMenu} onClick={()=>setMobileMenu(!mobileMenu)}>{mobileMenu?<X size={22}/>:<Compass size={22}/>}</button><nav className={'portal-main-nav '+(mobileMenu?'visible':'')} aria-label="Navegación principal"><a href="#explora" onClick={()=>setMobileMenu(false)}>Qué puedes consultar</a><a href="#campus" onClick={()=>setMobileMenu(false)}>Nuestro campus</a><a href="#como-funciona" onClick={()=>setMobileMenu(false)}>Cómo funciona</a><button className="portal-theme" onClick={()=>setDark(!dark)} aria-label={dark?'Activar modo claro':'Activar modo oscuro'}>{dark?<Sun size={18}/>:<Moon size={18}/>}</button><button className="portal-nav-cta" onClick={()=>{setOpen(true);setMobileMenu(false);}}>Hablemos <MessageCircle size={17}/></button></nav></header>
      <main id="portal-content"><section className="portal-cover" aria-labelledby="portal-title"><img className="portal-cover-image" src="/brand/campus-editorial.png" alt="" width="1672" height="941" fetchPriority="high"/><div className="portal-cover-shade"/><div className="portal-cover-content"><span className="portal-overline"><span/> TU VIDA UNIVERSITARIA, MÁS CERCA</span><h1 id="portal-title">Tu universidad,<br/>a una <em>conversación.</em></h1><p>Hola, soy Catalina. Te acompaño a encontrar respuestas, explorar el campus y entender la información de tu universidad.</p><div className="portal-cover-actions"><button className="portal-button-primary" onClick={()=>setOpen(true)}>Pregúntale a Catalina <ArrowUpRight size={20}/></button><button className="portal-button-ghost" onClick={goFull}>Mi espacio de conversaciones <ArrowRight size={17}/></button></div><span className="portal-guest-note"><Check size={14}/> Empieza sin registro. Amplía el chat cuando quieras.</span><div className="portal-starters"><span>PUEDES EMPEZAR CON</span><div><button onClick={()=>choosePrompt('¿Qué debo conocer como estudiante nuevo de la universidad?')}>Soy estudiante nuevo <ArrowUpRight size={13}/></button><button onClick={()=>choosePrompt('¿Dónde queda la biblioteca?')}>¿Dónde está la biblioteca? <ArrowUpRight size={13}/></button></div></div></div><div className="portal-cover-guide"><Mascot pose="wave"/><div><span>MUCHO GUSTO, SOY</span><strong>Catalina</strong><p>Tu próxima pregunta<br/>empieza aquí.</p></div></div><small className="portal-image-credit">Ilustración conceptual del campus</small></section>
      <div className="portal-value-bar" aria-label="Lo que puedes hacer con Catalina">{[{icon:MessageCircle,title:'Conversa a tu manera',text:'Empieza con una pregunta.'},{icon:FileText,title:'Encuentra información',text:'Consulta documentos y sus fuentes.'},{icon:Compass,title:'Ubícate en el campus',text:'Explora sedes y dependencias.'}].map(({icon:Icon,title,text})=><div key={title}><span><Icon size={23}/></span><div><strong>{title}</strong><p>{text}</p></div></div>)}</div>
      <section className="portal-explore portal-section" id="explora" aria-labelledby="explore-title"><header className="portal-section-heading"><div><span className="eyebrow">01 / ENCUENTRA TU CAMINO</span><h2 id="explore-title">Una pregunta.<br/>Muchas posibilidades.</h2></div><p>Empieza por lo que necesitas hoy. Catalina te orienta y consulta los documentos institucionales cuando tu pregunta lo requiere.</p></header><div className="portal-topic-grid">{prompts.map(({icon:Icon,title,text},i)=><button key={title} onClick={()=>choosePrompt(text)}><span className="portal-topic-top"><span className="portal-topic-icon"><Icon size={26}/></span><small>0{i+1}</small></span><h3>{title}</h3><p>{text}</p><span className="portal-topic-action">Empezar consulta <ArrowUpRight size={18}/></span></button>)}</div></section>
      <section className="portal-campus-section portal-section" id="campus" aria-labelledby="campus-title"><div className="portal-campus-copy"><span className="eyebrow">02 / CONOCE TU ENTORNO</span><h2 id="campus-title">Tu próximo destino<br/>también está aquí.</h2><p>¿Buscas una biblioteca, una facultad o un servicio? Encuentra su sede y consulta su ubicación en el mapa interactivo del campus.</p><ul><li><Check size={17}/> Sedes y dependencias en un mismo lugar</li><li><Check size={17}/> Preguntas con contexto sobre cada ubicación</li><li><Check size={17}/> Indicaciones para continuar en Google Maps</li></ul><button className="portal-button-primary" onClick={()=>openCampus()}>Explorar el mapa <Compass size={19}/></button><small>Disponible en el chat ampliado al iniciar sesión.</small></div><div className="portal-map-preview"><div className="portal-preview-toolbar"><span><span/> CAMPUS CATALINA</span><Compass size={17}/></div><img src={dark?'/maps/campus-plan-dark.svg':'/maps/campus-plan.svg'} alt="Vista previa del plano con las áreas delimitadas de las sedes universitarias" loading="lazy" width="760" height="550"/><div className="portal-preview-label"><MapPinIcon/><span>Encuentra tu lugar<strong>Explora. Pregunta. Llega.</strong></span><button aria-label="Abrir mapa del campus" onClick={()=>openCampus()}><ArrowUpRight size={20}/></button></div></div></section>
      <section className="portal-how-section portal-section" id="como-funciona" aria-labelledby="how-title"><header className="portal-section-heading"><div><span className="eyebrow">03 / ASÍ DE SENCILLO</span><h2 id="how-title">Menos vueltas.<br/>Más claridad.</h2></div><p>Un espacio pensado para acompañarte en tu día a día universitario, desde una conversación hasta una consulta con fuentes.</p></header><div className="portal-steps">{[{n:'01',title:'Haz tu pregunta',text:'Escribe como hablas. Puedes saludar, conversar o preguntar por tu universidad.'},{n:'02',title:'Explora la respuesta',text:'Consulta las fuentes disponibles o abre la ubicación cuando la respuesta incluya un lugar.'},{n:'03',title:'Continúa a tu ritmo',text:'Inicia sesión en el chat ampliado para guardar y retomar tus conversaciones.'}].map(step=><article key={step.n}><span>{step.n}</span><h3>{step.title}</h3><p>{step.text}</p></article>)}</div></section>
      <section className="portal-final-cta"><div className="portal-final-content"><span className="portal-overline">TU SIGUIENTE PASO EMPIEZA CON UNA PREGUNTA</span><h2>Conversemos de lo que<br/>necesitas hoy.</h2><button className="portal-button-primary" onClick={()=>setOpen(true)}>Hola, Catalina <MessageCircle size={19}/></button><span className="portal-final-note">Tu asistente. Tu universidad. Tu espacio.</span></div><Mascot pose="turn"/></section>
      </main><footer className="institutional-footer"><a className="independent-footer-brand" href="#/" aria-label="Catalina, inicio"><Avatar/><strong>CATALINA</strong></a><p>Catalina · Asistente universitario<br/><span>Proyecto académico independiente. No es el sitio oficial de la universidad.</span></p><a href="https://www.ucatolica.edu.co/portal/" target="_blank" rel="noreferrer">Consultar sitio de la universidad <ArrowUpRight size={16}/></a></footer>{open ? <div className="widget">{chat}</div> : <button className="launcher" ref={launcher} onClick={()=>setOpen(true)} aria-label="Abrir chat de Catalina"><Avatar/><span>Hola, soy Catalina<small>¿Conversamos?</small></span><MessageCircle size={22}/></button>}</div>}
  </>;
}
