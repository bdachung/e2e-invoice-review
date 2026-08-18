import { useEffect, useRef, useState } from 'react'

import { Button } from './ui/Button'
import {
  connectChatStream,
  uploadDocument,
  type ChatAction,
  type ChatEvent,
  type ChatStream,
  type Document,
} from '../lib/api'

const acceptedUploadTypes = ['application/pdf', 'image/jpeg', 'image/png']
const maxUploadBytes = 4 * 1024 * 1024

interface ChatLine {
  id: number
  role: 'user' | 'assistant' | 'system'
  text: string
}

interface ReviewState {
  review_id: string
  status: string
  allowed_actions: ChatAction[]
}

function ChatIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-6 w-6" aria-hidden="true">
      <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" />
    </svg>
  )
}

export function ChatPanel({ currentDocument }: { currentDocument: Document | null }) {
  const [open, setOpen] = useState(false)
  const [lines, setLines] = useState<ChatLine[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [review, setReview] = useState<ReviewState | null>(null)
  const [rejecting, setRejecting] = useState(false)
  const [rejectReason, setRejectReason] = useState('')
  const streamRef = useRef<ChatStream | null>(null)
  const nextIdRef = useRef(1)
  const progressIdRef = useRef<number | null>(null)
  const listRef = useRef<HTMLDivElement | null>(null)
  const uploadRef = useRef<HTMLInputElement | null>(null)

  const addLine = (role: ChatLine['role'], text: string): number => {
    const id = nextIdRef.current++
    setLines((current) => [...current, { id, role, text }])
    return id
  }
  const appendAssistant = (delta: string) => {
    setLines((current) => {
      const last = current[current.length - 1]
      if (last?.role === 'assistant') {
        return [...current.slice(0, -1), { ...last, text: last.text + delta }]
      }
      return [...current, { id: nextIdRef.current++, role: 'assistant', text: delta }]
    })
  }
  const updateProgress = (message: string) => {
    setLines((current) => {
      if (progressIdRef.current !== null) {
        return current.map((line) =>
          line.id === progressIdRef.current ? { ...line, text: message } : line,
        )
      }
      const id = nextIdRef.current++
      progressIdRef.current = id
      return [...current, { id, role: 'system', text: message }]
    })
  }

  useEffect(() => {
    if (!open) {
      streamRef.current?.close()
      streamRef.current = null
      return
    }
    if (streamRef.current) return
    const stream = connectChatStream((event: ChatEvent) => {
      switch (event.type) {
        case 'ready':
          setConnected(true)
          setError(null)
          addLine('system', `Connected. Finance MCP tools: ${event.tools.join(', ')}`)
          break
        case 'user':
          addLine('user', event.text)
          break
        case 'text':
          appendAssistant(event.delta)
          break
        case 'tool':
          progressIdRef.current = null
          addLine('system', `⚙ ${event.name}(${JSON.stringify(event.arguments)})`)
          break
        case 'progress':
          updateProgress(`[${Math.round(event.progress)}/${event.total ?? '?'}] ${event.message ?? ''}`)
          break
        case 'tool_result':
          progressIdRef.current = null
          addLine('system', `↳ ${event.name} finished`)
          break
        case 'review':
          setReview({
            review_id: event.review_id,
            status: event.status,
            allowed_actions: event.allowed_actions,
          })
          break
        case 'action_result':
          addLine('system', `Action ${event.action}: ${JSON.stringify(event.result)}`)
          break
        case 'error':
          setError(event.message)
          addLine('system', `Error: ${event.message}`)
          break
        case 'done':
          setBusy(false)
          break
      }
    })
    streamRef.current = stream
    setBusy(false)
    return () => {
      stream.close()
      streamRef.current = null
      setConnected(false)
    }
  }, [open])

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: 'smooth' })
  }, [lines])

  function sendMessage() {
    const text = input.trim()
    if (!text || busy || !streamRef.current) return
    setInput('')
    setBusy(true)
    setError(null)
    setReview(null)
    const payload: Record<string, unknown> = { type: 'message', text }
    if (currentDocument) payload.document_ref = currentDocument.id
    streamRef.current.send(payload)
  }

  function sendAction(action: ChatAction, reason?: string) {
    if (!review || busy || !streamRef.current) return
    setBusy(true)
    setRejecting(false)
    setRejectReason('')
    const payload: Record<string, unknown> = {
      type: 'action',
      action,
      review_id: review.review_id,
    }
    if (reason) payload.reason = reason
    streamRef.current.send(payload)
  }

  async function uploadFile(file: File | undefined) {
    if (!file || busy || !streamRef.current) return
    if (!acceptedUploadTypes.includes(file.type) || file.size > maxUploadBytes) {
      addLine('system', 'Error: choose a PDF, JPEG, or PNG document up to 4 MB.')
      return
    }
    setBusy(true)
    setError(null)
    setReview(null)
    addLine('user', `📎 ${file.name}`)
    try {
      const record = await uploadDocument(file, { autoProcess: false })
      streamRef.current.send({
        type: 'message',
        text: 'Review the document I just uploaded and summarize the result.',
        document_ref: record.id,
      })
    } catch (reason) {
      setBusy(false)
      const message = reason instanceof Error ? reason.message : 'Could not upload the document.'
      addLine('system', `Error: ${message}`)
      setError(message)
    }
  }

  return (
    <>
      {open && (
        <aside className="fixed bottom-32 right-6 z-50 flex h-[560px] max-h-[calc(100vh-13rem)] w-[380px] max-w-[calc(100vw-3rem)] flex-col overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-2xl">
          <header className="flex items-center justify-between gap-2 border-b border-zinc-200 bg-zinc-50 px-4 py-3">
            <div>
              <p className="text-sm font-semibold text-zinc-900">Finance assistant</p>
              <p className={`text-xs ${connected ? 'text-emerald-600' : 'text-zinc-400'}`}>
                {connected ? 'Connected to MCP server' : 'Connecting…'}
              </p>
            </div>
            <button type="button" onClick={() => setOpen(false)} className="rounded-md p-1 text-zinc-400 hover:bg-zinc-200 hover:text-zinc-700" aria-label="Close chat">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" className="h-5 w-5"><path d="M18 6 6 18M6 6l12 12" /></svg>
            </button>
          </header>

          <div ref={listRef} className="flex-1 space-y-3 overflow-y-auto px-4 py-4 text-sm">
            {lines.length === 0 && (
              <p className="text-center text-xs text-zinc-400">
                Upload an invoice or receipt here, or ask to review the current document.
              </p>
            )}
            {lines.map((line) => (
              <div
                key={line.id}
                className={line.role === 'user' ? 'flex justify-end' : 'flex justify-start'}
              >
                <div
                  className={`max-w-[85%] whitespace-pre-wrap rounded-xl px-3 py-2 ${
                    line.role === 'user'
                      ? 'bg-zinc-900 text-white'
                      : line.role === 'assistant'
                        ? 'border border-zinc-200 bg-white'
                        : 'bg-zinc-100 font-mono text-xs text-zinc-600'
                  }`}
                >
                  {line.text}
                </div>
              </div>
            ))}
            {error && <p className="text-xs text-red-600">{error}</p>}
            {review && review.allowed_actions.length > 0 && (
              <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-3">
                <p className="text-xs text-zinc-500">
                  Review <span className="font-medium text-zinc-800">{review.status}</span> — choose an action:
                </p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {review.allowed_actions.includes('approve') && (
                    <Button variant="success" className="h-8 px-3 text-xs" disabled={busy} onClick={() => sendAction('approve')}>Approve</Button>
                  )}
                  {review.allowed_actions.includes('reject') && (
                    <Button variant="destructive" className="h-8 px-3 text-xs" disabled={busy} onClick={() => { setRejecting((value) => !value); setRejectReason('') }}>Reject</Button>
                  )}
                  {review.allowed_actions.includes('draft_email') && (
                    <Button variant="outline" className="h-8 px-3 text-xs" disabled={busy} onClick={() => sendAction('draft_email')}>Draft email</Button>
                  )}
                </div>
                {rejecting && (
                  <div className="mt-2 flex gap-2">
                    <input
                      value={rejectReason}
                      onChange={(event) => setRejectReason(event.target.value)}
                      placeholder="Rejection reason"
                      className="h-8 min-w-0 flex-1 rounded-lg border border-zinc-200 px-2 text-xs focus:outline-none focus:ring-2 focus:ring-zinc-400"
                    />
                    <Button variant="destructive" className="h-8 px-3 text-xs" disabled={busy} onClick={() => sendAction('reject', rejectReason)}>Confirm</Button>
                  </div>
                )}
              </div>
            )}
          </div>

          <footer className="border-t border-zinc-200 p-3">
            {currentDocument && (
              <p className="mb-2 truncate rounded-lg bg-zinc-100 px-2 py-1 text-xs text-zinc-600">
                Current document: {currentDocument.original_filename}
              </p>
            )}
            <div className="flex items-center gap-2">
              <input
                ref={uploadRef}
                type="file"
                accept="application/pdf,image/jpeg,image/png"
                className="hidden"
                onChange={(event) => void uploadFile(event.target.files?.[0])}
              />
              <button
                type="button"
                onClick={() => uploadRef.current?.click()}
                disabled={busy}
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-zinc-200 bg-white text-zinc-500 transition-colors hover:bg-zinc-50 hover:text-zinc-800 disabled:opacity-50"
                aria-label="Upload a document to review"
                title="Upload a document to review"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="h-5 w-5" aria-hidden="true">
                  <path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48" />
                </svg>
              </button>
              <input
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={(event) => { if (event.key === 'Enter') sendMessage() }}
                placeholder={busy ? 'Working…' : 'Ask the finance assistant…'}
                disabled={busy}
                className="h-10 min-w-0 flex-1 rounded-lg border border-zinc-200 px-3 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-400 disabled:opacity-50"
              />
              <Button onClick={sendMessage} disabled={busy || !input.trim()}>Send</Button>
            </div>
          </footer>
        </aside>
      )}
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="fixed bottom-16 right-6 z-50 flex h-12 w-12 items-center justify-center rounded-full bg-zinc-900 text-white shadow-lg transition-colors hover:bg-zinc-800"
        aria-label={open ? 'Close chat' : 'Open chat'}
        title={open ? 'Close chat' : 'Open chat'}
      >
        <ChatIcon />
      </button>
    </>
  )
}
