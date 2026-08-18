import { apiBaseUrl } from './env'

export type Status = 'processing' | 'ready' | 'needs_review' | 'approved' | 'rejected' | 'failed'
export type ProgressStatus = 'started' | 'completed' | 'failed'
export type ProcessingStep =
  | 'upload'
  | 'classification'
  | 'extraction'
  | 'normalization'
  | 'independent_review'
  | 'validation'
  | 'general_ledger'

export interface DocumentProgressEvent {
  document_id: string
  step: ProcessingStep | null
  status: ProgressStatus
  message: string | null
}

export interface Issue {
  code: string
  field: string | null
  severity: 'error' | 'warning'
  message: string
}

export interface Account {
  code: string
  name: string
  description: string
}

export interface ReviewLineItem {
  description: string | null
  quantity: string | number | null
  unit_price: string | number | null
  amount: string | number | null
}

export interface ReviewData {
  document_type: 'invoice' | 'receipt'
  expense_category: 'fuel' | 'meals' | 'travel' | 'supplies' | 'other' | null
  supplier_name: string | null
  supplier_vat_id: string | null
  customer_name: string | null
  customer_vat_id: string | null
  document_number: string | null
  document_date: string | null
  due_date: string | null
  purchase_order: string | null
  currency: string | null
  subtotal: string | number | null
  total_tax: string | number | null
  total: string | number | null
  amount_due: string | number | null
  line_items: ReviewLineItem[]
  field_confidence: Record<string, number | null>
  field_provenance: Record<string, 'document_intelligence' | 'llm_fallback' | 'human'>
}

export interface FieldComparison {
  field: string
  label: string
  status: 'match' | 'different' | 'missing_in_document_intelligence' | 'missing_in_llm' | 'missing_in_both'
  document_intelligence_value: string | null
  llm_value: string | null
}

export interface DocumentReview {
  extraction: { summary: string | null } | null
  comparisons: FieldComparison[]
  fallback_fields: FieldComparison[]
  error_message: string | null
}

export interface CorrectionEmailDraft {
  recipient_name: string | null
  subject: string
  body: string
}

export interface Session {
  authenticated: boolean
}

export interface Document {
  id: string
  original_filename: string
  content_type: string
  status: Status
  review_data: ReviewData | null
  document_review: DocumentReview | null
  validation: { issues: Issue[]; status: 'ready' | 'needs_review' } | null
  metadata: { gl_suggestion?: { account_code: string; rationale: string } } | null
  accounting: { selected_account: Account | null } | null
  issues: Issue[]
  supplier_action_required: boolean
  error_message: string | null
  created_at: string
  updated_at: string
}

export type DocumentCorrection = Partial<Pick<
  ReviewData,
  | 'supplier_name'
  | 'supplier_vat_id'
  | 'customer_name'
  | 'customer_vat_id'
  | 'document_number'
  | 'document_date'
  | 'due_date'
  | 'purchase_order'
  | 'currency'
  | 'subtotal'
  | 'total_tax'
  | 'total'
  | 'amount_due'
>>

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, init)
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null
    throw new Error(body?.detail ?? `Request failed (${response.status})`)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export function subscribeDocumentProgress(
  documentId: string,
  onEvent: (event: DocumentProgressEvent) => void,
): () => void {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const baseUrl = apiBaseUrl
    ? apiBaseUrl.replace(/^http/, 'ws')
    : `${protocol}//${window.location.host}`
  const socket = new WebSocket(`${baseUrl}/api/documents/${encodeURIComponent(documentId)}/progress`)
  socket.addEventListener('message', ({ data }) => onEvent(JSON.parse(data) as DocumentProgressEvent))
  return () => socket.close()
}

export type ChatAction = 'approve' | 'reject' | 'draft_email'

export type ChatEvent =
  | { type: 'ready'; tools: string[] }
  | { type: 'user'; text: string }
  | { type: 'text'; delta: string }
  | { type: 'tool'; name: string; arguments: Record<string, unknown> }
  | { type: 'tool_result'; name: string; content: unknown }
  | { type: 'progress'; progress: number; total: number | null; message: string | null }
  | { type: 'review'; review_id: string; status: string; document_ref: string | null; conclusion: string | null; allowed_actions: ChatAction[] }
  | { type: 'action_result'; action: ChatAction; result: Record<string, unknown> }
  | { type: 'error'; message: string }
  | { type: 'done' }

export interface ChatStream {
  send: (payload: Record<string, unknown>) => void
  close: () => void
}

export function connectChatStream(onEvent: (event: ChatEvent) => void): ChatStream {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const baseUrl = apiBaseUrl
    ? apiBaseUrl.replace(/^http/, 'ws')
    : `${protocol}//${window.location.host}`
  const socket = new WebSocket(`${baseUrl}/api/chat/stream`)
  socket.addEventListener('message', ({ data }) => onEvent(JSON.parse(data) as ChatEvent))
  return {
    send: (payload) => socket.send(JSON.stringify(payload)),
    close: () => socket.close(),
  }
}

export function uploadDocument(file: File, options: { autoProcess?: boolean } = {}) {
  const body = new FormData()
  body.append('file', file)
  const query = options.autoProcess === false ? '?auto_process=false' : ''
  return request<Document>(`/api/documents${query}`, { method: 'POST', body })
}

export const getSession = () => request<Session>('/api/auth/session')
export const login = (password: string) => request<void>('/api/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ password }) })
export const logout = () => request<void>('/api/auth/logout', { method: 'POST' })
export const getDocument = (id: string) => request<Document>(`/api/documents/${encodeURIComponent(id)}`)
export const listDocuments = () => request<Document[]>('/api/documents')
export const listAccounts = () => request<Account[]>('/api/accounting/gl-accounts')
export const deleteDocument = (id: string) => request<void>(`/api/documents/${encodeURIComponent(id)}`, { method: 'DELETE' })
export const selectAccount = (id: string, gl_account_code: string) => request<Document>(`/api/documents/${encodeURIComponent(id)}/accounting`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ gl_account_code }) })
export const decide = (id: string, decision: 'approved' | 'rejected') => request<Document>(`/api/documents/${encodeURIComponent(id)}/decision`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ decision }) })
export const correctDocument = (id: string, changes: DocumentCorrection) => request<Document>(`/api/documents/${encodeURIComponent(id)}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(changes) })
export const draftCorrectionEmail = (id: string) => request<CorrectionEmailDraft>(`/api/documents/${encodeURIComponent(id)}/correction-email`, { method: 'POST' })
export const fileUrl = (id: string) => `${apiBaseUrl}/api/documents/${encodeURIComponent(id)}/file`

