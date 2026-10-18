import {useEffect, useRef, useState, type FormEvent} from 'react';
import {ArrowDown, ArrowRight, ArrowUpRight, BookOpen, Bot, Check, ChevronLeft, Compass, FileText, GraduationCap, History, LogOut, Maximize2, MessageCircle, Moon, Plus, Search, Send, ShieldCheck, Sun, Trash2, X, Pencil, RefreshCw} from 'lucide-react';
import {api} from './api';
import type {Conversation, Message, Source, User} from './types';
const prompts = [
  {icon: GraduationCap, title:'Soy estudiante nuevo', text:'¿Qué debo conocer como estudiante nuevo de la universidad?'},
  {icon: BookOpen, title:'Trámites académicos', text:'¿Cómo puedo solicitar un certificado de estudios?'},
  {icon: Compass, title:'Ubícate en la universidad', text:'¿Dónde están las sedes de la universidad?'},
  {icon: FileText, title:'Reglamento y calendario', text:'¿Qué documentos puedo consultar sobre el reglamento y el calendario académico?'}
];
const errorText = (e: unknown) => e instanceof Error ? e.message : 'Ocurrió un error. Inténtalo nuevamente.';
function Avatar({large = false}: {large?: boolean}) {return <span className={'avatar ' + (large ? 'large' : '')}><img src="/brand/catalina.svg" alt=""/></span>;}
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
  const [slide, setSlide] = useState(0);
  const [mobileMenu, setMobileMenu] = useState(false);
  const [draft, setDraft] = useState(''); const [search, setSearch] = useState('');
  const [busy, setBusy] = useState(false); const [pending, setPending] = useState('');
  const [error, setError] = useState(''); const [health, setHealth] = useState('Comprobando conexión…');
  const [dark, setDark] = useState(() => {try {return localStorage.getItem('catalina-theme') === 'dark';} catch {return false;}});
  const [sidebar, setSidebar] = useState(false);
  const bottom = useRef<HTMLDivElement>(null); const launcher = useRef<HTMLButtonElement>(null);
  const chatHeading = useRef<HTMLHeadingElement>(null);
  const citations = useRef(new Map<number, Source[]>());
  const epoch = useRef(0); const locked = useRef(false);
  useEffect(() => {const update = () => setFull(location.hash === '#/chat'); window.addEventListener('hashchange', update);return () => window.removeEventListener('hashchange', update);}, []);
  useEffect(() => {document.documentElement.dataset.theme = dark ? 'dark' : 'light';try {localStorage.setItem('catalina-theme', dark ? 'dark' : 'light');} catch {}}, [dark]);
  useEffect(() => {void checkHealth();}, []);
  useEffect(() => {bottom.current?.scrollIntoView({behavior:'smooth', block:'end'});}, [messages, guestMessages, pending]);
  useEffect(() => {if (open || full) chatHeading.current?.focus();}, [open, full]);
  useEffect(() => {
    const expired = () => {epoch.current++; setUser(null); setMessages([]); setConversations([]);setActive(null);citations.current.clear();setError('Tu sesión terminó. Inicia sesión nuevamente.');};
    window.addEventListener('catalina:expired', expired);return () => window.removeEventListener('catalina:expired', expired);
  }, []);
  async function checkHealth() {setHealth('Comprobando conexión…');try {await api.health();setHealth('API conectada');}catch {setHealth('Sin conexión con la API');}}
  async function action(task: () => Promise<void>) {
    if (locked.current) return;
    locked.current = true;setBusy(true);setError('');
    try {await task();} catch(e) {setError(errorText(e));} finally {locked.current = false;setBusy(false);}
  }
  async function refreshHistory() {const current = epoch.current;const rows = await api.conversations();if(current === epoch.current) setConversations(rows);}
  function goFull() {setOpen(false);location.hash = '/chat';setFull(true);}
  function goPortal() {location.hash = '/';setFull(false);}
  function closeWidget() {setOpen(false);launcher.current?.focus();}
  function newChat() {if (busy) return;setActive(null);setMessages([]);setDraft('');setError('');setSidebar(false);}
  function choosePrompt(text: string) {if (busy) return;setDraft(text);if (!full) setOpen(true);}
  function login(event: FormEvent) {event.preventDefault();void action(async () => {
    const account = await api.login(email.trim(), password);epoch.current++;setUser(account);setPassword('');await refreshHistory();
  });}
  function loadConversation(id: number) {void action(async () => {
    const current = epoch.current;const rows = await api.messages(id);if (current !== epoch.current) return;
    setMessages(rows.map(m => ({...m,citations:citations.current.get(m.id)})));setActive(id);setDraft('');setSidebar(false);
  });}
  function send(event: FormEvent) {event.preventDefault();const query = draft.trim();if (!query || (full && !user)) return;
    if (!user) {
      void action(async () => {
        setPending(query);
        try {
          const answer = await api.guestAnswer(query);
          setGuestMessages(rows => [...rows, {id: Date.now(), conversacion_id: 0, pregunta: query, respuesta: answer.text, fecha: new Date().toISOString(), citations: answer.citations}]);
          setDraft('');
        } finally {setPending('');}
      });
      return;
    }
    void action(async () => {
      const current = epoch.current;let id = active;
      if (id === null) {const conversation = await api.create(query.slice(0,160));if(current !== epoch.current) return;id = conversation.id;setActive(id);setConversations(c => [conversation, ...c]);}
      setPending(query);
      try {
        const answer = await api.answer(id, query);if(current !== epoch.current) return;
        citations.current.set(answer.message_id, answer.citations);
        setMessages(rows => [...rows, {id:answer.message_id,conversacion_id:id!,pregunta:answer.query,respuesta:answer.text,fecha:new Date().toISOString(),citations:answer.citations}]);setDraft('');await refreshHistory();
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
      {!user && full ? <div className="login-panel"><Avatar large/><span className="eyebrow">BIENVENIDO A CATALINA</span><h3>Tu espacio.<br/>Tu conversación.</h3><p>Inicia sesión para continuar en el chat ampliado y guardar tus conversaciones. Puedes volver al portal para hacer consultas rápidas sin registro.</p><form onSubmit={login}><label htmlFor="email">Correo electrónico</label><input id="email" type="email" autoComplete="username" required value={email} onChange={e=>setEmail(e.target.value)} disabled={busy}/><label htmlFor="password">Contraseña</label><input id="password" type="password" autoComplete="current-password" required value={password} onChange={e=>setPassword(e.target.value)} disabled={busy}/><button className="primary" disabled={busy}>{busy ? 'Ingresando…' : 'Iniciar sesión'}<ArrowRight size={18}/></button></form><small>Usa una cuenta ya creada en Catalina. El acceso con Microsoft se incorporará más adelante.</small></div> : <>
      {!visibleMessages.length && !pending && <div className="welcome"><Avatar large/><span className="eyebrow">UN ESPACIO PARA TUS PREGUNTAS</span><h3>Hola, {user ? user.nombre.split(' ')[0] : 'qué gusto verte'}.<br/>¿En qué te puedo ayudar?</h3><p>Conversemos, resolvamos tus dudas y consultemos documentos cuando necesites información de tu universidad.</p><div className="prompt-grid">{prompts.map(({icon:Icon,title,text})=><button key={title} disabled={busy} onClick={()=>setDraft(text)}><Icon size={21}/><span>{title}</span><ArrowUpRight size={16}/></button>)}</div></div>}
      <div className="messages" role="log" aria-label="Mensajes de la conversación" aria-live="polite">{visibleMessages.map(m=><article className="exchange" key={m.id}><div className="question">{m.pregunta}</div><div className="answer"><div className="answer-label"><Bot size={17}/> CATALINA</div><div className="answer-text">{m.respuesta}</div><Sources items={m.citations} text={m.respuesta}/></div></article>)}{pending && <article className="exchange"><div className="question">{pending}</div><div className="thinking" role="status"><span/>Catalina está preparando tu respuesta…</div></article>}<div ref={bottom}/></div>
      </>}
    </div>
    {error && <div className="error" role="alert">{error}</div>}
    {(user || !full) && <form className="composer" onSubmit={send}><label className="sr-only" htmlFor="question">Tu pregunta para Catalina</label><div className="input-wrap"><textarea id="question" rows={2} maxLength={1000} placeholder="Escribe tu pregunta…" value={draft} disabled={busy} onChange={e=>setDraft(e.target.value)} onKeyDown={e=>{if(e.key==='Enter' && !e.shiftKey && !e.nativeEvent.isComposing){e.preventDefault();e.currentTarget.form?.requestSubmit();}}}/><button disabled={busy || !draft.trim()} aria-label="Enviar pregunta"><Send size={19}/></button></div><small>Revisa las fuentes y confirma los trámites con el área responsable.</small></form>}
    <footer className="chat-footer"><ShieldCheck size={13}/> {!user && !full ? 'Sin registro · Preguntas independientes' : 'Información institucional con fuentes'}{!full && user && <button onClick={goFull}>Ver historial <ArrowRight size={12}/></button>}</footer>
  </section>;
  return <>
    {full ? <div className="workspace"><aside className={'sidebar ' + (sidebar?'visible':'')}><button className="back" onClick={goPortal}><ChevronLeft size={17}/> Volver al portal</button><div className="brand"><Avatar/><div><strong>CATALINA</strong><small>Asistente virtual</small></div></div><button className="new-chat" disabled={busy || !user} onClick={newChat}><Plus size={18}/> Nueva conversación</button><div className="history-title"><History size={15}/> TUS CONVERSACIONES</div><label className="search"><Search size={16}/><input aria-label="Buscar conversaciones" placeholder="Buscar…" value={search} onChange={e=>setSearch(e.target.value)}/></label><nav className="history-list" aria-label="Historial">{conversations.filter(c=>c.titulo.toLocaleLowerCase().includes(search.toLocaleLowerCase())).map(c=><button key={c.id} className={active===c.id?'selected':''} disabled={busy} onClick={()=>loadConversation(c.id)}><MessageCircle size={16}/><span>{c.titulo}</span></button>)}{!conversations.length && <p>{user?'Aquí aparecerán tus conversaciones.':'Inicia sesión para consultar tu historial.'}</p>}</nav>{user && <div className="user-box"><span className="initial">{user.nombre.charAt(0)}</span><div><strong>{user.nombre}</strong><small>{user.email}</small></div><button className="icon-btn" disabled={busy} aria-label="Cerrar sesión" onClick={()=>void action(async()=>{await api.logout();epoch.current++;setUser(null);setMessages([]);setConversations([]);setActive(null);citations.current.clear();})}><LogOut size={18}/></button></div>}<button className="connection" onClick={checkHealth}><span className={health==='API conectada'?'dot online':'dot'}/>{health}<RefreshCw size={12}/></button></aside><main className="main-chat"><button className="mobile-history" onClick={()=>setSidebar(!sidebar)}><History size={17}/>{sidebar?'Ocultar historial':'Ver historial'}</button>{chat}</main></div> : <div className="portal">
      <div className="institutional-bar"><div className="service-links"><a href="https://www.ucatolica.edu.co/portal/" target="_blank" rel="noreferrer">SERVICIOS<br/>INSTITUCIONALES</a><a className="paw" href="https://www.ucatolica.edu.co/portal/" target="_blank" rel="noreferrer">PAW 3.0</a><a href="https://www.ucatolica.edu.co/portal/" target="_blank" rel="noreferrer">CAMPUS VIRTUAL</a><a className="financial" href="https://www.ucatolica.edu.co/portal/" target="_blank" rel="noreferrer">APOYO FINANCIERO</a></div><div className="institutional-links"><a href="#informacion">TRANSPARENCIA Y ACCESO A LA INFORMACIÓN</a><a href="#consultas">ATENCIÓN Y SERVICIOS</a><a href="https://www.ucatolica.edu.co/portal/" target="_blank" rel="noreferrer">BIBLIOTECA <BookOpen size={12}/></a></div></div>
      <header className="institutional-header"><a className="official-logo" href="#/" aria-label="Universidad Católica de Colombia, inicio"><img src="/brand/universidad-catolica.png" alt="Universidad Católica de Colombia · Vigilada Mineducación"/></a><div className="header-divider"/><div className="identity-caption"><ShieldCheck size={30}/><span>Educación que<br/><strong>transforma vidas</strong></span></div><button className="menu-toggle" aria-label="Abrir navegación" aria-expanded={mobileMenu} onClick={()=>setMobileMenu(!mobileMenu)}><Compass size={23}/></button><nav className={mobileMenu ? 'institutional-nav visible' : 'institutional-nav'} aria-label="Navegación principal">{['Nuestra universidad','Oferta académica','Admisiones','Facultades','Investigaciones','Vida universitaria'].map(label=><a key={label} href="https://www.ucatolica.edu.co/portal/" target="_blank" rel="noreferrer">{label}</a>)}<button onClick={()=>{setOpen(true);setMobileMenu(false);}}>CATALINA <img src="/brand/catalina.svg" alt=""/></button></nav></header>
      <main><section className={'campus-hero slide-'+slide} aria-label="Actualidad universitaria">
        {slide===0 ? <><div className="reference-banner"><img src="/brand/portal-reference.png" alt="CyberTrust Summit 2026 · AI, Cybersecurity & Digital Defense · 27 y 28 de octubre de 2026"/></div><a className="banner-link" href="https://www.cybertrustsummit.com/" target="_blank" rel="noreferrer" aria-label="Conocer CyberTrust Summit 2026"/></> : <div className="catalina-banner"><div className="banner-orbits"/><div className="catalina-banner-copy"><span className="hero-tag">UNIVERSIDAD CATÓLICA DE COLOMBIA</span><h1>Tu universidad.<br/>Tus preguntas.<br/><em>Una conversación.</em></h1><p>Conoce a Catalina, tu asistente para explorar la información de la universidad.</p><button className="gold" onClick={()=>setOpen(true)}>Pregúntale a Catalina <ArrowUpRight size={20}/></button><span className="banner-note">Empieza aquí, sin iniciar sesión.</span></div><div className="catalina-emblem"><img src="/brand/catalina.svg" alt="Logo de Catalina"/><span>CATALINA</span><small>Tu asistente universitario</small></div></div>}
        <button className="slide-control previous" onClick={()=>setSlide(slide===0?1:0)} aria-label="Banner anterior"><ChevronLeft size={35}/></button><button className="slide-control next" onClick={()=>setSlide(slide===0?1:0)} aria-label="Banner siguiente"><ChevronLeft size={35}/></button><div className="slide-dots">{[0,1].map(i=><button key={i} className={slide===i?'active':''} onClick={()=>setSlide(i)} aria-label={i===0?'Ver CyberTrust Summit':'Ver Catalina'} aria-pressed={slide===i}/>)}</div>
      </section>
      <section className="campus-shortcuts" aria-label="Accesos destacados"><a className="enroll" href="https://www.ucatolica.edu.co/portal/" target="_blank" rel="noreferrer"><GraduationCap size={27}/><span>Inscripciones<strong>Infórmate aquí</strong></span><ArrowUpRight size={20}/></a>{[{title:'PREGRADOS',icon:BookOpen},{title:'POSGRADOS',icon:GraduationCap},{title:'EDUCACIÓN CONTINUADA',icon:Compass}].map(({title,icon:Icon})=><a key={title} href="https://www.ucatolica.edu.co/portal/" target="_blank" rel="noreferrer"><Icon size={27}/><span>{title}</span><ArrowUpRight size={17}/></a>)}<button onClick={()=>setOpen(true)}><img src="/brand/catalina.svg" alt=""/><span>CONOCE A<strong>CATALINA</strong></span><ArrowUpRight size={17}/></button></section>
      <section className="assistant-intro" id="consultas"><div className="intro-heading"><span className="eyebrow">CONECTADOS CON LO QUE NECESITAS</span><h2>Una pregunta puede<br/>abrir muchos caminos<span>.</span></h2><p>Encuentra orientación sobre tu vida universitaria con Catalina. Empieza una consulta rápida o inicia sesión para tener tu espacio de conversaciones.</p><button className="text-action" onClick={()=>setOpen(true)}>Hablemos de tu próxima pregunta <ArrowRight size={18}/></button></div><div className="question-cards">{prompts.map(({icon:Icon,title,text},i)=><button key={title} onClick={()=>choosePrompt(text)}><span className="question-icon"><Icon size={24}/></span><div><small>0{i+1} / EXPLORA</small><h3>{title}</h3><p>{text}</p></div><ArrowUpRight size={20}/></button>)}</div></section>
      <section className="catalina-callout" id="informacion"><div className="callout-brand"><Avatar large/><div><span>CONOCE A TU ASISTENTE</span><h2>Hola, soy Catalina.</h2><p>Tu próxima pregunta empieza aquí.</p></div></div><button className="gold" onClick={()=>setOpen(true)}>Iniciar una conversación <MessageCircle size={19}/></button><button className="callout-full" onClick={goFull}>Mi espacio de conversaciones <ArrowUpRight size={17}/></button></section>
      </main><footer className="institutional-footer"><img src="/brand/universidad-catolica.png" alt="Universidad Católica de Colombia"/><p>Catalina · Asistente universitario<br/><span>Prototipo académico · Respuestas institucionales con fuentes verificables.</span></p><a href="https://www.ucatolica.edu.co/portal/" target="_blank" rel="noreferrer">Visitar sitio institucional <ArrowUpRight size={16}/></a></footer>{open ? <div className="widget">{chat}</div> : <button className="launcher" ref={launcher} onClick={()=>setOpen(true)} aria-label="Abrir chat de Catalina"><Avatar/><span>Hola, soy Catalina<small>¿Conversamos?</small></span><MessageCircle size={22}/></button>}</div>}
  </>;
}
