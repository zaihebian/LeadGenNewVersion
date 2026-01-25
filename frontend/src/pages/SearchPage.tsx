import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Search, Loader2, CheckCircle, AlertCircle, Clock } from 'lucide-react'
import { searchApi, authApi } from '../api/client'

export default function SearchPage() {
  const [keywords, setKeywords] = useState('')
  const queryClient = useQueryClient()

  // Check Gmail auth status
  const { data: gmailStatus } = useQuery({
    queryKey: ['gmail-status'],
    queryFn: () => authApi.getGmailStatus().then(r => r.data),
  })

  // Get campaigns
  const { data: campaignsData, isLoading: campaignsLoading } = useQuery({
    queryKey: ['campaigns'],
    queryFn: () => searchApi.getCampaigns().then(r => r.data),
    refetchInterval: 5000, // Refresh every 5 seconds to see status updates
  })

  // Start search mutation
  const searchMutation = useMutation({
    mutationFn: (keywords: string) => searchApi.startSearch(keywords),
    onSuccess: () => {
      setKeywords('')
      queryClient.invalidateQueries({ queryKey: ['campaigns'] })
    },
  })

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (keywords.trim()) {
      searchMutation.mutate(keywords.trim())
    }
  }

  const getStatusBadge = (status: string) => {
    const styles: Record<string, { bg: string; text: string; icon: React.ReactNode }> = {
      PENDING: { bg: 'bg-gray-100', text: 'text-gray-700', icon: <Clock className="w-3 h-3" /> },
      COLLECTING: { bg: 'bg-blue-100', text: 'text-blue-700', icon: <Loader2 className="w-3 h-3 animate-spin" /> },
      ENRICHING: { bg: 'bg-yellow-100', text: 'text-yellow-700', icon: <Loader2 className="w-3 h-3 animate-spin" /> },
      ACTIVE: { bg: 'bg-green-100', text: 'text-green-700', icon: <CheckCircle className="w-3 h-3" /> },
      COMPLETED: { bg: 'bg-green-100', text: 'text-green-700', icon: <CheckCircle className="w-3 h-3" /> },
      FAILED: { bg: 'bg-red-100', text: 'text-red-700', icon: <AlertCircle className="w-3 h-3" /> },
    }
    const style = styles[status] || styles.PENDING
    return (
      <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${style.bg} ${style.text}`}>
        {style.icon}
        {status}
      </span>
    )
  }

  return (
    <div className="space-y-8">
      {/* Gmail Auth Status */}
      {!gmailStatus?.authenticated && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-medium text-yellow-800">Gmail Not Connected</h3>
              <p className="text-sm text-yellow-700">Connect your Gmail account to send emails</p>
            </div>
            <button
              onClick={() => authApi.initiateGmailAuth()}
              className="px-4 py-2 bg-yellow-600 text-white rounded-lg hover:bg-yellow-700 transition-colors"
            >
              Connect Gmail
            </button>
          </div>
        </div>
      )}

      {/* Search Form */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-4">Find New Leads</h1>
        <p className="text-gray-600 mb-6">
          Enter keywords to describe the leads you're looking for. Our AI will convert this into a targeted search.
        </p>

        <form onSubmit={handleSearch} className="space-y-4">
          <div>
            <label htmlFor="keywords" className="block text-sm font-medium text-gray-700 mb-2">
              Search Keywords
            </label>
            <textarea
              id="keywords"
              value={keywords}
              onChange={(e) => setKeywords(e.target.value)}
              placeholder="e.g., Marketing managers at SaaS companies in the United States, CTOs at fintech startups in London..."
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-none"
              rows={3}
            />
          </div>

          <button
            type="submit"
            disabled={!keywords.trim() || searchMutation.isPending}
            className="flex items-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {searchMutation.isPending ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <Search className="w-5 h-5" />
            )}
            {searchMutation.isPending ? 'Starting Search...' : 'Start Lead Search'}
          </button>
        </form>

        {searchMutation.isSuccess && (
          <div className="mt-4 p-4 bg-green-50 border border-green-200 rounded-lg">
            <p className="text-green-800">
              Campaign started! Leads are being collected in the background.
            </p>
          </div>
        )}

        {searchMutation.isError && (
          <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg">
            <p className="text-red-800">
              Error starting search. Please try again.
            </p>
          </div>
        )}
      </div>

      {/* Campaigns List */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Recent Campaigns</h2>

        {campaignsLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-8 h-8 animate-spin text-gray-400" />
          </div>
        ) : !campaignsData?.campaigns?.length ? (
          <p className="text-gray-500 text-center py-8">No campaigns yet. Start your first search above!</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-500">Keywords</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-500">Status</th>
                  <th className="text-right py-3 px-4 text-sm font-medium text-gray-500">Found</th>
                  <th className="text-right py-3 px-4 text-sm font-medium text-gray-500">Valid</th>
                  <th className="text-right py-3 px-4 text-sm font-medium text-gray-500">Enriched</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-500">Created</th>
                </tr>
              </thead>
              <tbody>
                {campaignsData.campaigns.map((campaign) => (
                  <tr key={campaign.id} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-3 px-4">
                      <span className="text-gray-900 font-medium">{campaign.keywords}</span>
                    </td>
                    <td className="py-3 px-4">{getStatusBadge(campaign.status)}</td>
                    <td className="py-3 px-4 text-right text-gray-600">{campaign.leads_found}</td>
                    <td className="py-3 px-4 text-right text-gray-600">{campaign.leads_valid}</td>
                    <td className="py-3 px-4 text-right text-gray-600">{campaign.leads_enriched}</td>
                    <td className="py-3 px-4 text-gray-500 text-sm">
                      {new Date(campaign.created_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
