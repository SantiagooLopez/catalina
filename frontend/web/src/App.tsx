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
function Avatar({large = false}: {large?: boolean}) {return <span className={'avatar ' + (large ? 'large' : '')}><Bot aria-hidden="true"/></span>;}
function Sources({items}: {items: Source[] | undefined}) {
  if (!items) return <small className="source-note">Las citas de este mensaje no están disponibles en el historial de la API.</small>;
  if (!items.length) return <small className="source-note">Esta respuesta no incluye fuentes citadas.</small>;
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
  useEffect(() => {bottom.current?.scrollIntoView({behavior:'smooth', block:'end'});}, [messages, pending]);
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
  function send(event: FormEvent) {event.preventDefault();const query = draft.trim();if (!query || !user) return;
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
  const chat = <section className={'chat-shell ' + (full ? 'expanded' : 'compact')} aria-label="Chat con Catalina" onKeyDown={e=>{if(e.key==='Escape' && !full) closeWidget();}}>
    <header className="chat-header"><Avatar/><div><h2 tabIndex={-1} ref={chatHeading}>Catalina</h2><span>Tu asistente universitario</span></div><div className="header-actions"><button className="icon-btn" onClick={()=>setDark(!dark)} aria-label={dark ? 'Activar modo claro' : 'Activar modo oscuro'}>{dark ? <Sun size={19}/> : <Moon size={19}/>}</button>{!full && <><button className="icon-btn" onClick={goFull} aria-label="Ampliar chat"><Maximize2 size={19}/></button><button className="icon-btn" onClick={closeWidget} aria-label="Cerrar chat"><X size={20}/></button></>}</div></header>
    {user && <div className="conversation-bar"><span>{title}</span><button className="icon-btn" disabled={busy} onClick={newChat} aria-label="Nueva conversación"><Plus size={17}/></button>{active !== null && <><button className="icon-btn" disabled={busy} onClick={rename} aria-label="Renombrar conversación"><Pencil size={16}/></button><button className="icon-btn" disabled={busy} onClick={remove} aria-label="Eliminar conversación"><Trash2 size={16}/></button></>}</div>}
    <div className="chat-body">
      {!user ? <div className="login-panel"><Avatar large/><span className="eyebrow">BIENVENIDO A CATALINA</span><h3>Tu universidad,<br/>más cerca de ti.</h3><p>Inicia sesión para preguntar y recuperar tus conversaciones.</p><form onSubmit={login}><label htmlFor="email">Correo electrónico</label><input id="email" type="email" autoComplete="username" required value={email} onChange={e=>setEmail(e.target.value)} disabled={busy}/><label htmlFor="password">Contraseña</label><input id="password" type="password" autoComplete="current-password" required value={password} onChange={e=>setPassword(e.target.value)} disabled={busy}/><button className="primary" disabled={busy}>{busy ? 'Ingresando…' : 'Iniciar sesión'}<ArrowRight size={18}/></button></form><small>Usa una cuenta ya creada en Catalina. El acceso con Microsoft se incorporará más adelante.</small></div> : <>
      {!messages.length && !pending && <div className="welcome"><Avatar large/><span className="eyebrow">UN ESPACIO PARA TUS PREGUNTAS</span><h3>Hola, {user.nombre.split(' ')[0]}.<br/>¿En qué te puedo ayudar?</h3><p>Consulta información de tu universidad con el respaldo de documentos institucionales.</p><div className="prompt-grid">{prompts.map(({icon:Icon,title,text})=><button key={title} disabled={busy} onClick={()=>setDraft(text)}><Icon size={21}/><span>{title}</span><ArrowUpRight size={16}/></button>)}</div></div>}
      <div className="messages" role="log" aria-label="Mensajes de la conversación" aria-live="polite">{messages.map(m=><article className="exchange" key={m.id}><div className="question">{m.pregunta}</div><div className="answer"><div className="answer-label"><Bot size={17}/> CATALINA</div><div className="answer-text">{m.respuesta}</div><Sources items={m.citations}/></div></article>)}{pending && <article className="exchange"><div className="question">{pending}</div><div className="thinking" role="status"><span/>Consultando la información institucional…</div></article>}<div ref={bottom}/></div>
      </>}
    </div>
    {error && <div className="error" role="alert">{error}</div>}
    {user && <form className="composer" onSubmit={send}><label className="sr-only" htmlFor="question">Tu pregunta para Catalina</label><div className="input-wrap"><textarea id="question" rows={2} placeholder="Escribe tu pregunta…" value={draft} disabled={busy} onChange={e=>setDraft(e.target.value)} onKeyDown={e=>{if(e.key==='Enter' && !e.shiftKey && !e.nativeEvent.isComposing){e.preventDefault();e.currentTarget.form?.requestSubmit();}}}/><button disabled={busy || !draft.trim()} aria-label="Enviar pregunta"><Send size={19}/></button></div><small>Revisa las fuentes y confirma los trámites con el área responsable.</small></form>}
    <footer className="chat-footer"><ShieldCheck size={13}/> Información con respaldo institucional{!full && user && <button onClick={goFull}>Ver historial <ArrowRight size={12}/></button>}</footer>
  </section>;
  return <>
    {full ? <div className="workspace"><aside className={'sidebar ' + (sidebar?'visible':'')}><button className="back" onClick={goPortal}><ChevronLeft size={17}/> Volver al portal</button><div className="brand"><Avatar/><div><strong>CATALINA</strong><small>Asistente virtual</small></div></div><button className="new-chat" disabled={busy || !user} onClick={newChat}><Plus size={18}/> Nueva conversación</button><div className="history-title"><History size={15}/> TUS CONVERSACIONES</div><label className="search"><Search size={16}/><input aria-label="Buscar conversaciones" placeholder="Buscar…" value={search} onChange={e=>setSearch(e.target.value)}/></label><nav className="history-list" aria-label="Historial">{conversations.filter(c=>c.titulo.toLocaleLowerCase().includes(search.toLocaleLowerCase())).map(c=><button key={c.id} className={active===c.id?'selected':''} disabled={busy} onClick={()=>loadConversation(c.id)}><MessageCircle size={16}/><span>{c.titulo}</span></button>)}{!conversations.length && <p>{user?'Aquí aparecerán tus conversaciones.':'Inicia sesión para consultar tu historial.'}</p>}</nav>{user && <div className="user-box"><span className="initial">{user.nombre.charAt(0)}</span><div><strong>{user.nombre}</strong><small>{user.email}</small></div><button className="icon-btn" disabled={busy} aria-label="Cerrar sesión" onClick={()=>void action(async()=>{await api.logout();epoch.current++;setUser(null);setMessages([]);setConversations([]);setActive(null);citations.current.clear();})}><LogOut size={18}/></button></div>}<button className="connection" onClick={checkHealth}><span className={health==='API conectada'?'dot online':'dot'}/>{health}<RefreshCw size={12}/></button></aside><main className="main-chat"><button className="mobile-history" onClick={()=>setSidebar(!sidebar)}><History size={17}/>{sidebar?'Ocultar historial':'Ver historial'}</button>{chat}</main></div> : <div className="portal"><div className="utility"><span>UNIVERSIDAD CATÓLICA DE COLOMBIA</span><span>COMUNIDAD UNIVERSITARIA <ArrowUpRight size={13}/></span></div><header className="portal-header"><div className="university-brand"><GraduationCap size={38}/><div>UNIVERSIDAD<br/><strong>CATÓLICA DE COLOMBIA</strong></div></div><nav aria-label="Navegación principal"><a href="#acompanamiento">Vida universitaria</a><a href="#consultas">Información académica</a><button onClick={goFull}>Conoce a Catalina <ArrowUpRight size={16}/></button></nav></header><main><section className="hero"><div className="hero-grid"/><div className="hero-content"><span className="hero-tag"><span/> TU COMPAÑERA EN LA VIDA UNIVERSITARIA</span><h1>Un nuevo camino.<br/><em>Mil preguntas.</em><br/>Aquí empieza Catalina.</h1><p>Encuentra orientación sobre trámites, reglamentos y tu universidad. Un espacio para preguntar, aprender y sentirte acompañado.</p><button className="gold" onClick={goFull}>Conversemos <ArrowUpRight size={19}/></button><a className="hero-link" href="#acompanamiento">Descubre cómo te acompaña <ArrowDown size={16}/></a></div><div className="hero-art" aria-hidden="true"><div className="orbit one"/><div className="orbit two"/><div className="art-bot"><Bot/><span>CATALINA</span></div><div className="floating-card fc-one"><BookOpen size={20}/><span>Información<br/><strong>a tu alcance</strong></span><Check size={16}/></div><div className="floating-card fc-two"><MessageCircle size={20}/><span>Tu próxima pregunta<br/><strong>empieza aquí</strong></span></div><span className="art-caption">CONECTAMOS PREGUNTAS CON CONOCIMIENTO</span></div><div className="hero-bottom"><span>01 / CONOCE A CATALINA</span><span>Tu universidad, más cerca.</span></div></section><section id="acompanamiento" className="intro"><div><span className="eyebrow">CONTIGO, DESDE EL PRIMER DÍA</span><h2>Menos vueltas.<br/>Más respuestas.</h2></div><p>Desde tu primera semana hasta tus próximos pasos: consulta la información institucional en una conversación sencilla.</p></section><section id="consultas" className="portal-cards">{prompts.map(({icon:Icon,title,text},i)=><button key={title} onClick={()=>choosePrompt(text)}><span className="card-number">0{i+1}</span><Icon size={28}/><h3>{title}</h3><span>Pregúntale a Catalina <ArrowUpRight size={17}/></span></button>)}</section><section className="trust"><ShieldCheck/><p><strong>Respuestas que puedes verificar.</strong><br/>Catalina muestra las fuentes cuando la API encuentra respaldo documental para tu consulta.</p><button onClick={goFull}>Abrir asistente <ArrowRight size={18}/></button></section></main><footer className="portal-footer"><strong>CATALINA</strong><span>Prototipo académico · Universidad Católica de Colombia</span></footer>{open ? <div className="widget">{chat}</div> : <button className="launcher" ref={launcher} onClick={()=>setOpen(true)} aria-label="Abrir chat de Catalina"><Avatar/><span>Hola, soy Catalina<small>¿Conversamos?</small></span><MessageCircle size={22}/></button>}</div>}
  </>;
}
