import { useMemo, useState } from 'react'

import { fileUrl } from '../lib/api'
import type {
  Account,
  CorrectionEmailDraft,
  Document,
  DocumentCorrection,
  ReviewData,
} from '../lib/api'
import { Button } from './ui/Button'
import { Card } from './ui/Card'

interface ResultStepProps {
  document: Document
  accounts: Account[]
  onChoose: (code: string) => Promise<void>
  onCorrect: (changes: DocumentCorrection) => Promise<void>
  onDecide: (decision: 'approved' | 'rejected') => Promise<void>
  onDraftCorrectionEmail: () => Promise<CorrectionEmailDraft>
}

const editableFields = [
  'supplier_name', 'supplier_vat_id', 'customer_name', 'customer_vat_id',
  'document_number', 'document_date', 'due_date', 'purchase_order', 'currency',
  'subtotal', 'total_tax', 'total', 'amount_due',
] as const

type EditableField = typeof editableFields[number]
type EditValues = Record<EditableField, string>

const labels: Record<EditableField, string> = {
  supplier_name: 'Supplier name', supplier_vat_id: 'Supplier VAT ID',
  customer_name: 'Customer name', customer_vat_id: 'Customer VAT ID',
  document_number: 'Invoice or receipt number', document_date: 'Document date',
  due_date: 'Due date', purchase_order: 'Purchase order', currency: 'Currency',
  subtotal: 'Subtotal', total_tax: 'VAT total', total: 'Total', amount_due: 'Amount due',
}

function initialValues(data: ReviewData | null): EditValues {
  return Object.fromEntries(editableFields.map((field) => [field, String(data?.[field] ?? '')])) as EditValues
}

function StatusBadge({ status }: { status: Document['status'] }) {
  const style: Record<Document['status'], string> = {
    ready: 'bg-emerald-100 text-emerald-800', needs_review: 'bg-amber-100 text-amber-900',
    approved: 'bg-emerald-100 text-emerald-800', rejected: 'bg-zinc-200 text-zinc-700',
    failed: 'bg-red-100 text-red-800', processing: 'bg-blue-100 text-blue-800',
  }
  return <span className={`rounded-full px-2.5 py-1 text-xs font-medium capitalize ${style[status]}`}>{status.replace('_', ' ')}</span>
}

function Evidence({ value, provenance }: { value: number | null | undefined; provenance: string | undefined }) {
  const text = provenance === 'human' ? 'Human supplied' : provenance === 'llm_fallback' ? 'Independent fallback' : value == null ? 'No confidence' : `${Math.round(value * 100)}% confidence`
  return <span className="text-[11px] font-normal text-zinc-400">{text}</span>
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return <section className="border-t border-zinc-100 pt-6"><h3 className="text-base font-semibold">{title}</h3>{children}</section>
}

export function ResultStep({ document, accounts, onChoose, onCorrect, onDecide, onDraftCorrectionEmail }: ResultStepProps) {
  const locked = document.status === 'approved' || document.status === 'rejected'
  const hasErrors = document.issues.some((issue) => issue.severity === 'error')
  const hasAccount = Boolean(document.accounting?.selected_account)
  const canApprove = !locked && document.status !== 'failed' && !hasErrors && hasAccount
  const [values, setValues] = useState<EditValues>(() => initialValues(document.review_data))
  const [saving, setSaving] = useState(false)
  const [draft, setDraft] = useState<CorrectionEmailDraft | null>(null)
  const [draftError, setDraftError] = useState<string | null>(null)
  const data = document.review_data
  const comparisons = useMemo(() => document.document_review?.comparisons.filter((item) => item.status !== 'missing_in_both') ?? [], [document.document_review])
  const approvalMessage = hasErrors ? 'Resolve all error-level validation findings before approval.' : !hasAccount ? 'Select a valid general ledger account before approval.' : 'All approval prerequisites are complete.'

  async function saveCorrections() {
    setSaving(true)
    try {
      const changes: DocumentCorrection = {}
      for (const field of editableFields) changes[field] = values[field].trim() || null
      await onCorrect(changes)
    } finally { setSaving(false) }
  }

  async function createDraft() {
    setDraftError(null)
    try { setDraft(await onDraftCorrectionEmail()) } catch (error) { setDraftError(error instanceof Error ? error.message : 'Could not create the correction draft.') }
  }

  async function copyDraft() {
    if (!draft) return
    try { await navigator.clipboard.writeText(`Subject: ${draft.subject}\n\n${draft.body}`) } catch { setDraftError('Copy was not available in this browser. Select the draft text to copy it.') }
  }

  return <main className="mx-auto max-w-7xl px-6 py-8"><div className="mb-6"><p className="text-sm text-zinc-500">Prepared review</p><h1 className="mt-1 text-2xl font-semibold tracking-tight">Review evidence and decide</h1><p className="mt-1 text-sm text-zinc-600">Document Intelligence is primary. Independent values only fill gaps and remain visible beside it.</p></div><div className="grid gap-6 xl:grid-cols-[.8fr_1.2fr]"><Card className="h-fit overflow-hidden"><div className="border-b border-zinc-100 p-5"><p className="break-all text-sm font-medium">{document.original_filename}</p><p className="mt-1 text-xs text-zinc-500">Original uploaded document</p></div><iframe title="Original document" src={fileUrl(document.id)} className="min-h-[680px] w-full border-0 bg-zinc-100" /></Card><Card className="overflow-hidden"><div className="flex flex-wrap items-start justify-between gap-4 border-b border-zinc-100 p-6"><div><p className="text-sm font-medium text-zinc-500">Northstar policy review</p><h2 className="mt-1 text-lg font-semibold">{data?.document_type === 'receipt' ? 'Receipt' : 'Invoice'} preparation</h2></div><StatusBadge status={document.status} /></div><div className="space-y-8 p-6">{document.status === 'failed' ? <section className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800"><p className="font-semibold">Processing could not complete</p><p className="mt-1">{document.error_message ?? 'No additional error details were returned.'}</p></section> : <><section><div className="flex items-center justify-between"><div><h3 className="text-base font-semibold">Automatic checks</h3><p className="mt-1 text-sm text-zinc-500">Errors block approval; warnings remain reviewable.</p></div><span className="rounded-full bg-zinc-100 px-2.5 py-1 text-xs">{document.issues.length} issues</span></div>{document.issues.length ? <ul className="mt-4 space-y-2">{document.issues.map((issue) => <li key={`${issue.code}-${issue.field}`} className={`rounded-lg border p-3 text-sm ${issue.severity === 'error' ? 'border-red-200 bg-red-50 text-red-800' : 'border-amber-200 bg-amber-50 text-amber-900'}`}><b className="capitalize">{issue.severity}:</b> {issue.message}</li>)}</ul> : <p className="mt-4 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">No policy issues were found.</p>}</section><Section title="Prepared fields"><p className="mt-1 text-sm text-zinc-500">Save an edit to re-run the same deterministic policy. Changed values become human-supplied.</p><div className="mt-4 grid gap-3 md:grid-cols-2">{editableFields.map((field) => <label key={field}><span className="flex items-center justify-between text-xs font-medium text-zinc-600">{labels[field]}<Evidence value={data?.field_confidence[field]} provenance={data?.field_provenance[field]} /></span><input type={field.includes('date') ? 'date' : 'text'} value={values[field]} disabled={locked} onChange={(event) => setValues((current) => ({ ...current, [field]: event.target.value }))} className="mt-1 h-10 w-full rounded-lg border border-zinc-200 bg-white px-3 text-sm disabled:bg-zinc-100" /></label>)}</div>{!locked && <div className="mt-4 flex justify-end"><Button variant="outline" disabled={saving} onClick={() => void saveCorrections()}>{saving ? 'Revalidating…' : 'Save and revalidate'}</Button></div>}</Section>{data?.line_items.length ? <Section title="Line items"><div className="mt-4 overflow-x-auto rounded-xl border border-zinc-200"><table className="min-w-full text-left text-sm"><thead className="bg-zinc-50 text-xs text-zinc-500"><tr><th className="px-3 py-2">Description</th><th className="px-3 py-2">Qty</th><th className="px-3 py-2">Unit price</th><th className="px-3 py-2">Amount</th></tr></thead><tbody>{data.line_items.map((item, index) => <tr key={`${item.description}-${index}`} className="border-t border-zinc-100"><td className="px-3 py-2">{item.description ?? '—'}</td><td className="px-3 py-2">{item.quantity ?? '—'}</td><td className="px-3 py-2">{item.unit_price ?? '—'}</td><td className="px-3 py-2">{item.amount ?? '—'}</td></tr>)}</tbody></table></div></Section> : null}<Section title="Independent source review">{document.document_review?.error_message ? <p className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">{document.document_review.error_message}</p> : <><p className="mt-1 text-sm text-zinc-500">{document.document_review?.extraction?.summary ?? 'No independent summary was returned.'}</p>{comparisons.length ? <div className="mt-4 space-y-2">{comparisons.map((comparison) => <div key={comparison.field} className={`rounded-lg border p-3 text-sm ${comparison.status === 'different' ? 'border-amber-200 bg-amber-50 text-amber-900' : comparison.status === 'match' ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : 'border-zinc-200 bg-zinc-50 text-zinc-700'}`}><div className="flex justify-between gap-4"><p className="font-medium">{comparison.label}</p><p className="text-xs capitalize">{comparison.status.replaceAll('_', ' ')}</p></div><div className="mt-2 grid gap-2 text-xs sm:grid-cols-2"><p><b>Document Intelligence: </b>{comparison.document_intelligence_value ?? 'Not found'}</p><p><b>Independent review: </b>{comparison.llm_value ?? 'Not found'}</p></div></div>)}</div> : null}</>}</Section><Section title="General ledger account">{document.metadata?.gl_suggestion && <div className="mt-3 rounded-lg border border-zinc-200 bg-zinc-50 p-4 text-sm"><p className="font-medium">Suggested: {document.metadata.gl_suggestion.account_code}</p><p className="mt-1 text-zinc-600">{document.metadata.gl_suggestion.rationale}</p></div>}<select className="mt-4 h-10 w-full rounded-lg border border-zinc-200 bg-white px-3 text-sm" value={document.accounting?.selected_account?.code ?? ''} disabled={locked} onChange={(event) => { if (event.target.value) void onChoose(event.target.value) }}><option value="">Select an account</option>{accounts.map((account) => <option key={account.code} value={account.code}>{account.code} — {account.name}</option>)}</select>{!locked && !hasAccount && <p className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">Select a valid general ledger account to enable approval.</p>}</Section><Section title="Supplier correction email">{document.supplier_action_required ? <p className="mt-1 text-sm text-zinc-500">Draft a correction request from supplier-fixable findings. The app will never send it.</p> : <p className="mt-1 text-sm text-zinc-500">No supplier-fixable finding is present, so a correction request is not needed for this review.</p>}<div className="mt-3"><Button variant="outline" disabled={!document.supplier_action_required || locked} title={document.supplier_action_required ? 'Create an unsent correction draft' : 'No supplier correction is needed'} onClick={() => void createDraft()}>Draft correction email</Button></div>{draftError && <p className="mt-3 text-sm text-red-700">{draftError}</p>}{draft && <div className="mt-4 rounded-lg border border-zinc-200 bg-zinc-50 p-4"><p className="text-xs font-medium uppercase tracking-wide text-zinc-500">Draft only — never sent</p><p className="mt-3 text-sm font-medium">Subject: {draft.subject}</p><p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-zinc-700">{draft.body}</p><div className="mt-4 flex gap-3"><Button variant="outline" onClick={() => void copyDraft()}>Copy draft</Button><Button variant="ghost" onClick={() => setDraft(null)}>Close</Button></div></div>}</Section></>} {!locked && <div className="border-t border-zinc-100 pt-6"><div className="flex flex-wrap items-center justify-between gap-3"><p id="approval-prerequisite" className={`text-sm ${canApprove ? 'text-emerald-800' : 'text-amber-800'}`}>{approvalMessage}</p><div className="flex gap-3"><Button variant="destructive" onClick={() => void onDecide('rejected')}>Reject</Button>{document.status !== 'failed' && <Button variant="success" disabled={!canApprove} aria-describedby="approval-prerequisite" onClick={() => void onDecide('approved')}>Approve</Button>}</div></div></div>}</div></Card></div></main>
}
