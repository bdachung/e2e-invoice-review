import { useEffect, useState } from 'react'

import { ResultStep } from './components/ResultStep'
import { UploadStep } from './components/UploadStep'
import { WelcomePortal } from './components/WelcomePortal'
import { Button } from './components/ui/Button'
import { Card } from './components/ui/Card'
import {
  correctDocument,
  decide,
  deleteDocument,
  draftCorrectionEmail,
  getDocument,
  listAccounts,
  listDocuments,
  selectAccount,
  subscribeDocumentProgress,
  uploadDocument,
  type Account,
  type Document,
  type DocumentCorrection,
  type DocumentProgressEvent,
} from './lib/api'

type View = 'welcome' | 'upload' | 'processing' | 'review' | 'history'

const terminal = new Set(['ready', 'needs_review', 'approved', 'rejected', 'failed'])
const steps = [
  ['classification', 'Classify the document'],
  ['extraction', 'Extract with Document Intelligence'],
  ['normalization', 'Normalize review data'],
  ['independent_review', 'Independently review and reconcile'],
  ['validation', 'Validate VAT and policy'],
  ['general_ledger', 'Suggest a GL account'],
] as const

function AppHeader({ onHome, onNew, onHistory }: { onHome: () => void; onNew: () => void; onHistory: () => void }) {
  return <header className="border-b border-zinc-200 bg-white"><div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-6 py-3"><button type="button" onClick={onHome} className="text-left"><p className="font-semibold text-zinc-950">Document review</p><p className="text-xs text-zinc-500">Northstar Facilities B.V.</p></button><nav className="flex items-center gap-2"><Button onClick={onHistory} variant="ghost">History</Button><Button onClick={onNew}>New review</Button></nav></div></header>
}

function App() {
  const [view, setView] = useState<View>('welcome')
  const [file, setFile] = useState<File | null>(null)
  const [selected, setSelected] = useState<Document | null>(null)
  const [documents, setDocuments] = useState<Document[]>([])
  const [accounts, setAccounts] = useState<Account[]>([])
  const [events, setEvents] = useState<DocumentProgressEvent[]>([])
  const [error, setError] = useState<string | null>(null)
  const selectedId = selected?.id
  const selectedStatus = selected?.status

  useEffect(() => { void listAccounts().then(setAccounts).catch(() => setError('Could not load the GL catalog.')) }, [])

  useEffect(() => {
    if (view !== 'processing' || !selectedId || (selectedStatus && terminal.has(selectedStatus))) return
    const refresh = () => void getDocument(selectedId).then((next) => {
      setSelected(next)
      if (terminal.has(next.status)) setView('review')
    }).catch((reason: unknown) => {
      setError(reason instanceof Error ? reason.message : 'Could not check processing status.')
      setView('review')
    })
    const unsubscribe = subscribeDocumentProgress(selectedId, (event) => {
      setEvents((current) => [...current, event])
      if (!event.step && (event.status === 'completed' || event.status === 'failed')) window.setTimeout(refresh, 100)
    })
    const timer = window.setInterval(refresh, 1500)
    return () => { unsubscribe(); window.clearInterval(timer) }
  }, [selectedId, selectedStatus, view])

  function start() { setFile(null); setSelected(null); setEvents([]); setError(null); setView('upload') }
  async function history() { setView('history'); try { setDocuments(await listDocuments()) } catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not load history.') } }
  async function process() { if (!file) return; setError(null); setEvents([]); try { const record = await uploadDocument(file); setSelected(record); setView(record.status === 'processing' ? 'processing' : 'review') } catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not process the document.') } }
  async function chooseAccount(code: string) { if (!selected) return; try { setSelected(await selectAccount(selected.id, code)) } catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not save account.') } }
  async function updateReview(changes: DocumentCorrection) { if (!selected) return; try { setSelected(await correctDocument(selected.id, changes)) } catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not revalidate the edited review.') } }
  async function makeDecision(decision: 'approved' | 'rejected') { if (!selected) return; try { setSelected(await decide(selected.id, decision)) } catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not save decision.') } }
  async function createCorrectionEmail() { if (!selected) throw new Error('No document is selected.'); return draftCorrectionEmail(selected.id) }

  return <div className="min-h-screen bg-zinc-50 text-zinc-950">{view !== 'welcome' && <AppHeader onHome={() => setView('welcome')} onNew={start} onHistory={() => void history()} />}{error && <div role="alert" className="mx-auto mt-6 max-w-6xl rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">{error}</div>}{view === 'welcome' && <WelcomePortal onStart={start} onHistory={() => void history()} />}{view === 'upload' && <UploadStep file={file} error={error} onChoose={(next) => { setFile(next); setError(null) }} onProcess={() => void process()} onBack={() => setView('welcome')} />}{view === 'processing' && selected && <Processing filename={selected.original_filename} events={events} />}{view === 'review' && selected && <ResultStep key={`${selected.id}-${selected.updated_at}`} document={selected} accounts={accounts} onChoose={chooseAccount} onCorrect={updateReview} onDecide={makeDecision} onDraftCorrectionEmail={createCorrectionEmail} />}{view === 'history' && <History documents={documents} onOpen={(item) => { setSelected(item); setView('review') }} onDelete={async (id) => { await deleteDocument(id); setDocuments((items) => items.filter((item) => item.id !== id)) }} />}</div>
}

function Processing({ filename, events }: { filename: string; events: DocumentProgressEvent[] }) {
  const latest = (step: string) => [...events].reverse().find((event) => event.step === step)
  const active = steps.findIndex(([step]) => latest(step)?.status === 'started')
  const failed = events.find((event) => event.status === 'failed')
  return <main className="mx-auto flex min-h-[70vh] max-w-2xl items-center justify-center px-6 py-12 text-center"><Card className="w-full"><div className="p-8 sm:p-10"><div className="flex justify-center"><div className="h-9 w-9 animate-spin rounded-full border-2 border-zinc-200 border-t-zinc-800" /></div><p className="mt-6 text-sm text-zinc-500">Live processing progress</p><h1 className="mt-1 text-2xl font-semibold tracking-tight">Processing document</h1><p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-zinc-600">Working through the review pipeline for <span className="font-medium text-zinc-800">{filename}</span>.</p>{failed?.message && <p className="mt-3 text-sm text-red-700">{failed.message}</p>}<ol className="mx-auto mt-8 max-w-lg space-y-2 text-left">{steps.map(([step, label], index) => { const event = latest(step); const complete = event?.status === 'completed'; const isFailed = event?.status === 'failed'; const running = !complete && !isFailed && index === active; return <li key={step} className={`flex gap-4 rounded-lg border p-4 ${isFailed ? 'border-red-200 bg-red-50' : running ? 'border-zinc-300 bg-zinc-50' : 'border-zinc-200 bg-white'}`}><span className={`flex h-7 w-7 items-center justify-center rounded-full text-xs ${complete ? 'bg-emerald-100 text-emerald-800' : isFailed ? 'bg-red-100 text-red-800' : 'bg-zinc-100'}`}>{complete ? '✓' : isFailed ? '!' : index + 1}</span><div><p className="text-sm font-medium text-zinc-700">{label}</p><p className="mt-1 text-xs text-zinc-500">{complete ? 'Completed' : isFailed ? 'Failed' : running ? 'In progress' : 'Waiting'}</p></div></li> })}</ol></div></Card></main>
}

function History({ documents, onOpen, onDelete }: { documents: Document[]; onOpen: (document: Document) => void; onDelete: (id: string) => Promise<void> }) { return <main className="mx-auto max-w-4xl px-6 py-10"><div><p className="text-sm text-zinc-500">Saved locally</p><h1 className="mt-1 text-2xl font-semibold tracking-tight">Review history</h1></div><Card className="mt-6 overflow-hidden">{documents.length ? documents.map((item) => <div key={item.id} className="flex items-center justify-between gap-4 border-b border-zinc-100 p-4 last:border-0"><button onClick={() => onOpen(item)} className="text-left"><p className="text-sm font-medium">{item.original_filename}</p><p className="mt-1 text-xs capitalize text-zinc-500">{item.status.replace('_', ' ')}</p></button><Button variant="destructive" onClick={() => void onDelete(item.id)}>Delete</Button></div>) : <p className="p-10 text-center text-sm text-zinc-500">No reviews have been saved yet.</p>}</Card></main> }

export default App
