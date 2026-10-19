export interface User {id: number; email: string; nombre: string; rol: string; activo: boolean}
export interface Session {access_token: string; refresh_token: string; refresh_expires_at: string; user: User}
export interface Conversation {id: number; titulo: string; fecha_inicio: string; fecha_actualizacion: string}
export interface Source {citation_id: string; document_name: string; version: string; page_start: number | null; page_end: number | null; section: string | null; document_id: number; document_version_id: number; point_id: string; index_run_id: string}
export interface Message {id: number; conversacion_id: number; pregunta: string; respuesta: string; fecha: string; citations?: Source[]; responseSeconds?: number; responseKind?: string}
export interface Answer {conversation_id: number; message_id: number; query: string; text: string; citations: Source[]; generated: boolean; reason: string}
export interface Page<T> {items: T[]; limit: number; offset: number}
