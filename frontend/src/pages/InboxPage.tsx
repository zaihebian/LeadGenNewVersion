import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Loader2, MessageSquare, Send, AlertCircle, ChevronRight, X } from 'lucide-react'
import { inboxApi } from '../api/client'

export default function InboxPage() {
  const [filter, setFilter] = useState<'all' | 'needs_attention' | 'has_reply'>('all')
  const [selectedThread, setSelectedThread] = useState<number | null>(null)
  const [replyContent, setReplyContent] = useState('')
  const queryClient = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ['inbox-threads', filter],
    queryFn: () =>
      inboxApi.getThreads(
        filter === 'needs_attention'
          ? { requires_human: true }
          : filter === 'has_reply'
          ? { has_reply: true }
          : undefined
      ).then(r => r.data),
  })

  const { data: threadDetail, isLoading: threadLoading } = useQuery({
    queryKey: ['inbox-thread', selectedThread],
    queryFn: () => inboxApi.getThread(selectedThread!).then(r => r.data),
    enabled: !!selectedThread,
  })

  const replyMutation = useMutation({
    mutationFn: ({ threadId, content }: { threadId: number; content: string }) =>
      inboxApi.sendReply(threadId, content),
    onSuccess: () => {
      setReplyContent('')
      queryClient.invalidateQueries({ queryKey: ['inbox-thread', selectedThread] })
      queryClient.invalidateQueries({ queryKey: ['inbox-threads'] })
    },
  })

  const handleReply = () => {
    if (selectedThread && replyContent.trim()) {
      replyMutation.mutate({ threadId: selectedThread, content: replyContent.trim() })
    }
  }

  const getSentimentBadge = (sentiment: string | undefined) => {
    if (!sentiment) return null
    const styles: Record<string, string> = {
      POSITIVE: 'bg-green-100 text-green-700',
      NEGATIVE: 'bg-red-100 text-red-700',
      NEUTRAL: 'bg-gray-100 text-gray-700',
    }
    return (
      <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${styles[sentiment] || styles.NEUTRAL}`}>
        {sentiment}
      </span>
    )
  }

  return (
    <div className="flex gap-6 h-[calc(100vh-12rem)]">
      {/* Thread List */}
      <div className="w-1/3 flex flex-col">
        <div className="flex items-center gap-2 mb-4">
          <h1 className="text-2xl font-bold text-gray-900">Inbox</h1>
          <span className="text-sm text-gray-500">({data?.total || 0} threads)</span>
        </div>

        {/* Filter Tabs */}
        <div className="flex gap-1 mb-4">
          {[
            { key: 'all', label: 'All' },
            { key: 'needs_attention', label: 'Needs Attention' },
            { key: 'has_reply', label: 'Has Reply' },
          ].map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setFilter(key as typeof filter)}
              className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
                filter === key
                  ? 'bg-blue-100 text-blue-700'
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Thread List */}
        <div className="flex-1 overflow-y-auto bg-white rounded-xl shadow-sm border border-gray-200">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 animate-spin text-gray-400" />
            </div>
          ) : !data?.threads?.length ? (
            <div className="text-center py-12">
              <MessageSquare className="w-12 h-12 mx-auto text-gray-300 mb-4" />
              <p className="text-gray-500">No email threads yet</p>
            </div>
          ) : (
            <div className="divide-y divide-gray-100">
              {data.threads.map((thread) => (
                <button
                  key={thread.id}
                  onClick={() => setSelectedThread(thread.id)}
                  className={`w-full p-4 text-left hover:bg-gray-50 transition-colors ${
                    selectedThread === thread.id ? 'bg-blue-50' : ''
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-medium text-gray-900 truncate">
                          {thread.lead_name}
                        </span>
                        {thread.requires_human && (
                          <AlertCircle className="w-4 h-4 text-orange-500 flex-shrink-0" />
                        )}
                      </div>
                      <div className="text-sm text-gray-600 truncate">{thread.subject}</div>
                      <div className="flex items-center gap-2 mt-1">
                        <span className="text-xs text-gray-400">{thread.lead_company}</span>
                        {getSentimentBadge(thread.reply_sentiment)}
                      </div>
                    </div>
                    <ChevronRight className="w-5 h-5 text-gray-400 flex-shrink-0" />
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Thread Detail */}
      <div className="flex-1 flex flex-col bg-white rounded-xl shadow-sm border border-gray-200">
        {!selectedThread ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <MessageSquare className="w-16 h-16 mx-auto text-gray-200 mb-4" />
              <p className="text-gray-500">Select a thread to view</p>
            </div>
          </div>
        ) : threadLoading ? (
          <div className="flex-1 flex items-center justify-center">
            <Loader2 className="w-8 h-8 animate-spin text-gray-400" />
          </div>
        ) : threadDetail ? (
          <>
            {/* Header */}
            <div className="p-4 border-b border-gray-200">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="font-semibold text-gray-900">{threadDetail.lead_name}</h2>
                  <p className="text-sm text-gray-500">
                    {threadDetail.lead_email} · {threadDetail.lead_company}
                  </p>
                </div>
                <button
                  onClick={() => setSelectedThread(null)}
                  className="p-2 hover:bg-gray-100 rounded-lg"
                >
                  <X className="w-5 h-5 text-gray-400" />
                </button>
              </div>
              <p className="mt-2 text-gray-700">{threadDetail.subject}</p>
              {threadDetail.requires_human && (
                <div className="mt-2 px-3 py-2 bg-orange-50 border border-orange-200 rounded-lg">
                  <p className="text-sm text-orange-700">This lead requires human attention</p>
                </div>
              )}
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {threadDetail.messages?.map((msg: { role: string; content: string; timestamp: string }, idx: number) => (
                <div
                  key={idx}
                  className={`max-w-[80%] ${
                    msg.role === 'sent' ? 'ml-auto' : 'mr-auto'
                  }`}
                >
                  <div
                    className={`p-4 rounded-lg ${
                      msg.role === 'sent'
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-100 text-gray-900'
                    }`}
                  >
                    <p className="whitespace-pre-wrap">{msg.content}</p>
                  </div>
                  <p className={`text-xs mt-1 ${msg.role === 'sent' ? 'text-right' : ''} text-gray-400`}>
                    {new Date(msg.timestamp).toLocaleString()}
                  </p>
                </div>
              ))}
            </div>

            {/* Reply Box */}
            <div className="p-4 border-t border-gray-200">
              <div className="flex gap-2">
                <textarea
                  value={replyContent}
                  onChange={(e) => setReplyContent(e.target.value)}
                  placeholder="Type your reply..."
                  className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 resize-none"
                  rows={3}
                />
                <button
                  onClick={handleReply}
                  disabled={!replyContent.trim() || replyMutation.isPending}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 self-end"
                >
                  {replyMutation.isPending ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    <Send className="w-5 h-5" />
                  )}
                </button>
              </div>
            </div>
          </>
        ) : null}
      </div>
    </div>
  )
}
