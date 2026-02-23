import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Loader2, Send, ExternalLink, User, Building2, Mail, Download, Sparkles, X } from 'lucide-react'
import { leadsApi, authApi } from '../api/client'

const STATES = [
  { value: '', label: 'All States' },
  { value: 'COLLECTED', label: 'Collected' },
  { value: 'ENRICHED', label: 'Enriched' },
  { value: 'EMAILED_1', label: 'First Email Sent' },
  { value: 'INTERESTED', label: 'Interested' },
  { value: 'NOT_INTERESTED', label: 'Not Interested' },
  { value: 'EMAILED_2', label: 'Follow-up Sent' },
  { value: 'CLOSED', label: 'Closed' },
]

interface GeneratedMessage {
  leadId: number
  subject: string
  body: string
}

export default function LeadsPage() {
  const [stateFilter, setStateFilter] = useState('')
  const [page, setPage] = useState(1)
  const [sendingLeadId, setSendingLeadId] = useState<number | null>(null)
  const [generatingLeadId, setGeneratingLeadId] = useState<number | null>(null)
  const [preview, setPreview] = useState<GeneratedMessage | null>(null)
  const queryClient = useQueryClient()

  const { data: gmailStatus } = useQuery({
    queryKey: ['gmail-status'],
    queryFn: () => authApi.getGmailStatus().then(r => r.data),
  })

  const gmailConnected = gmailStatus?.authenticated ?? false

  const { data, isLoading } = useQuery({
    queryKey: ['leads', stateFilter, page],
    queryFn: () =>
      leadsApi.getLeads({
        page,
        per_page: 20,
        state: stateFilter || undefined,
      }).then(r => r.data),
  })

  const sendEmailMutation = useMutation({
    mutationFn: (leadId: number) => {
      setSendingLeadId(leadId)
      return leadsApi.sendEmail(leadId)
    },
    onSuccess: () => {
      setSendingLeadId(null)
      queryClient.invalidateQueries({ queryKey: ['leads'] })
    },
    onError: () => {
      setSendingLeadId(null)
    },
  })

  const generateMutation = useMutation({
    mutationFn: (leadId: number) => {
      setGeneratingLeadId(leadId)
      return leadsApi.generateFirstMessage(leadId).then(r => ({ leadId, ...r.data }))
    },
    onSuccess: (result) => {
      setGeneratingLeadId(null)
      setPreview({ leadId: result.leadId, subject: result.subject, body: result.body })
    },
    onError: () => {
      setGeneratingLeadId(null)
    },
  })

  const downloadCsvMutation = useMutation({
    mutationFn: () =>
      leadsApi.downloadExportCsv({ state: stateFilter || undefined }).then((r) => r.data as Blob),
    onSuccess: (blob) => {
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'leads_enriched.csv'
      a.click()
      URL.revokeObjectURL(url)
    },
  })

  const generateAllMutation = useMutation({
    mutationFn: () => leadsApi.generateAllFirstMessages().then(r => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['leads'] })
    },
  })

  const getStateBadge = (state: string) => {
    const styles: Record<string, string> = {
      COLLECTED: 'bg-gray-100 text-gray-700',
      ENRICHED: 'bg-blue-100 text-blue-700',
      EMAILED_1: 'bg-purple-100 text-purple-700',
      INTERESTED: 'bg-green-100 text-green-700',
      NOT_INTERESTED: 'bg-red-100 text-red-700',
      EMAILED_2: 'bg-orange-100 text-orange-700',
      CLOSED: 'bg-gray-100 text-gray-500',
    }
    return (
      <span className={`inline-flex px-2 py-1 rounded-full text-xs font-medium ${styles[state] || styles.COLLECTED}`}>
        {state.replace(/_/g, ' ')}
      </span>
    )
  }

  const canSendEmail = (lead: { state: string; emails_sent_count: number }) => {
    return (
      (lead.state === 'ENRICHED' || lead.state === 'EMAILED_1') &&
      lead.emails_sent_count < 2
    )
  }

  return (
    <div className="space-y-6">
      {/* Generated message preview modal */}
      {preview && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-2xl mx-4 flex flex-col max-h-[80vh]">
            <div className="flex items-center justify-between p-5 border-b border-gray-200">
              <div className="flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-purple-600" />
                <h2 className="text-lg font-semibold text-gray-900">Generated First Message</h2>
              </div>
              <button
                onClick={() => setPreview(null)}
                className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-5 overflow-y-auto flex-1 space-y-4">
              <div>
                <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">Subject</p>
                <p className="text-gray-900 font-medium bg-gray-50 rounded-lg px-4 py-2 border border-gray-200">
                  {preview.subject}
                </p>
              </div>
              <div>
                <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">Body</p>
                <pre className="whitespace-pre-wrap text-gray-800 text-sm bg-gray-50 rounded-lg px-4 py-3 border border-gray-200 font-sans leading-relaxed">
                  {preview.body}
                </pre>
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 p-5 border-t border-gray-200">
              <p className="text-xs text-gray-400 flex-1">
                Saved as draft — visible in CSV export under first_message_subject / first_message_body
              </p>
              <button
                onClick={() => generateMutation.mutate(preview.leadId)}
                disabled={generateMutation.isPending}
                className="inline-flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-50"
              >
                {generateMutation.isPending ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Sparkles className="w-4 h-4" />
                )}
                Regenerate
              </button>
              <button
                onClick={() => setPreview(null)}
                className="px-4 py-2 bg-gray-900 text-white text-sm rounded-lg hover:bg-gray-700"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Leads</h1>

        <div className="flex items-center gap-3">
          {!gmailConnected && (
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => generateAllMutation.mutate()}
                disabled={generateAllMutation.isPending}
                className="inline-flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {generateAllMutation.isPending ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Sparkles className="w-4 h-4" />
                )}
                {generateAllMutation.isPending ? 'Generating...' : 'Generate All Messages'}
              </button>
              {generateAllMutation.isSuccess && (
                <span className="text-sm text-green-600 font-medium">
                  Done: {generateAllMutation.data?.generated} generated, {generateAllMutation.data?.skipped} skipped
                </span>
              )}
            </div>
          )}
          <button
            type="button"
            onClick={() => downloadCsvMutation.mutate()}
            disabled={downloadCsvMutation.isPending}
            className="inline-flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed text-gray-700"
          >
            {downloadCsvMutation.isPending ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Download className="w-4 h-4" />
            )}
            Download
          </button>
          <select
            value={stateFilter}
            onChange={(e) => {
              setStateFilter(e.target.value)
              setPage(1)
            }}
            className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          >
            {STATES.map(({ value, label }) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200">
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-gray-400" />
          </div>
        ) : !data?.leads?.length ? (
          <div className="text-center py-12">
            <User className="w-12 h-12 mx-auto text-gray-300 mb-4" />
            <p className="text-gray-500">No leads found</p>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-gray-200 bg-gray-50">
                    <th className="text-left py-3 px-4 text-sm font-medium text-gray-500">Lead</th>
                    <th className="text-left py-3 px-4 text-sm font-medium text-gray-500">Company</th>
                    <th className="text-left py-3 px-4 text-sm font-medium text-gray-500">State</th>
                    <th className="text-center py-3 px-4 text-sm font-medium text-gray-500">Emails</th>
                    <th className="text-left py-3 px-4 text-sm font-medium text-gray-500">Links</th>
                    <th className="text-right py-3 px-4 text-sm font-medium text-gray-500">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {data.leads.map((lead) => (
                    <tr key={lead.id} className="border-b border-gray-100 hover:bg-gray-50">
                      <td className="py-4 px-4">
                        <div>
                          <div className="font-medium text-gray-900">
                            {lead.first_name} {lead.last_name}
                          </div>
                          <div className="text-sm text-gray-500">{lead.job_title || 'No title'}</div>
                        </div>
                      </td>
                      <td className="py-4 px-4">
                        <div className="flex items-center gap-2 text-gray-600">
                          <Building2 className="w-4 h-4 text-gray-400" />
                          {lead.company_name || 'Unknown'}
                        </div>
                        <div className="text-sm text-gray-400">{lead.industry}</div>
                      </td>
                      <td className="py-4 px-4">{getStateBadge(lead.state)}</td>
                      <td className="py-4 px-4 text-center">
                        <span className="text-gray-600">{lead.emails_sent_count}/2</span>
                      </td>
                      <td className="py-4 px-4">
                        <div className="flex items-center gap-2">
                          <a
                            href={`mailto:${lead.email}`}
                            className="text-gray-400 hover:text-blue-600"
                            title={lead.email}
                          >
                            <Mail className="w-4 h-4" />
                          </a>
                          <a
                            href={lead.linkedin_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-gray-400 hover:text-blue-600"
                          >
                            <ExternalLink className="w-4 h-4" />
                          </a>
                        </div>
                      </td>
                      <td className="py-4 px-4 text-right">
                        {gmailConnected ? (
                          canSendEmail(lead) && (
                            <button
                              onClick={() => sendEmailMutation.mutate(lead.id)}
                              disabled={sendEmailMutation.isPending && sendingLeadId === lead.id}
                              className="inline-flex items-center gap-1 px-3 py-1.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50"
                            >
                              {sendEmailMutation.isPending && sendingLeadId === lead.id ? (
                                <Loader2 className="w-4 h-4 animate-spin" />
                              ) : (
                                <Send className="w-4 h-4" />
                              )}
                              Send Email
                            </button>
                          )
                        ) : (
                          lead.state === 'ENRICHED' && lead.emails_sent_count === 0 && (
                            <button
                              onClick={() => generateMutation.mutate(lead.id)}
                              disabled={generateMutation.isPending && generatingLeadId === lead.id}
                              className="inline-flex items-center gap-1 px-3 py-1.5 bg-purple-600 text-white text-sm rounded-lg hover:bg-purple-700 disabled:opacity-50"
                            >
                              {generateMutation.isPending && generatingLeadId === lead.id ? (
                                <Loader2 className="w-4 h-4 animate-spin" />
                              ) : (
                                <Sparkles className="w-4 h-4" />
                              )}
                              Generate Message
                            </button>
                          )
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            <div className="flex items-center justify-between px-4 py-3 border-t border-gray-200">
              <div className="text-sm text-gray-500">
                Showing {((page - 1) * 20) + 1} to {Math.min(page * 20, data.total)} of {data.total} leads
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="px-3 py-1 border border-gray-300 rounded-lg disabled:opacity-50"
                >
                  Previous
                </button>
                <button
                  onClick={() => setPage(p => p + 1)}
                  disabled={page * 20 >= data.total}
                  className="px-3 py-1 border border-gray-300 rounded-lg disabled:opacity-50"
                >
                  Next
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
