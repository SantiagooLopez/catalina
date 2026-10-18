import type { Session, User, Conversation, Message, Page, Answer } from './types';
let session: Session | null = null;
let refreshing: Promise<void> | null = null;
let generation = 0;
export class ApiError extends Error { constructor(message: string, public status: number) { super(message); } }
async function raw<T>(path: string, method = 'GET', body?: unknown, token?: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch('/api/v1' + path, {
      method, headers: { ...(body !== undefined ? {'Content-Type': 'application/json'} : {}), ...(token ? {Authorization: `Bearer ${token}`} : {}) },
      body: body === undefined ? undefined : JSON.stringify(body), signal: AbortSignal.timeout(240000), cache: 'no-store'
    });
  } catch { throw new ApiError('No se pudo completar la conexión. Comprueba Debian y tu red. Si enviaste una pregunta, revisa el historial antes de repetirla.', 0); }
  if (response.status === 204) return undefined as T;
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(data?.error?.message || (typeof data?.detail === 'string' ? data.detail : `No se pudo completar la solicitud (HTTP ${response.status}).`), response.status);
  if (data === null) throw new ApiError('La API devolvió una respuesta que no es JSON.', response.status);
  return data as T;
}
async function request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const current = generation;
  if (!session) throw new ApiError('Inicia sesión para continuar.', 401);
  try { return await raw<T>(path, method, body, session.access_token); }
  catch (error) {
    if (!(error instanceof ApiError) || error.status !== 401 || !session || current !== generation) throw error;
    if (!refreshing) refreshing = (async () => {
      try {
        const next = await raw<Omit<Session, 'user'>>('/auth/refresh', 'POST', {refresh_token: session!.refresh_token});
        if (session && current === generation) session = {...session, ...next};
      } catch (refreshError) {
        if (current === generation) { session = null; generation++; window.dispatchEvent(new Event('catalina:expired')); }
        throw refreshError;
      }
    })().finally(() => {refreshing = null;});
    await refreshing;
    if (!session || current !== generation) throw new ApiError('La sesión terminó. Vuelve a ingresar.', 401);
    return raw<T>(path, method, body, session.access_token);
  }
}
async function all<T>(path: string): Promise<T[]> {
  const result: T[] = [];
  for (let offset = 0; ; offset += 100) {
    const page = await request<Page<T>>(`${path}?limit=100&offset=${offset}`);
    result.push(...page.items);
    if (page.items.length < 100) return result;
  }
}
export const api = {
  async login(email: string, password: string): Promise<User> {
    const data = await raw<Session>('/auth/login', 'POST', {email, password});
    generation++; session = data; return data.user;
  },
  async logout() { if (session) await raw('/auth/logout', 'POST', {refresh_token: session.refresh_token}); generation++; session = null; },
  health: () => raw<{status: string}>('/health'),
  guestAnswer: (query: string) => raw<Pick<Answer, 'query' | 'text' | 'citations'>>('/guest/answers', 'POST', {query}),
  conversations: () => all<Conversation>('/conversations'),
  messages: (id: number) => all<Message>(`/conversations/${id}/messages`),
  create: (titulo: string) => request<Conversation>('/conversations', 'POST', {titulo}),
  rename: (id: number, titulo: string) => request<Conversation>(`/conversations/${id}`, 'PATCH', {titulo}),
  remove: (id: number) => request<void>(`/conversations/${id}`, 'DELETE'),
  answer: (conversation_id: number, query: string) => request<Answer>('/answers', 'POST', {conversation_id, query})
};
