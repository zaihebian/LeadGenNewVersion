import { useQuery } from '@tanstack/react-query'
import { Loader2, Users, MessageSquare, ThumbsUp, ThumbsDown, Clock, XCircle, BarChart3 } from 'lucide-react'
import { dashboardApi } from '../api/client'

export default function DashboardPage() {
  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: () => dashboardApi.getStats().then(r => r.data),
    refetchInterval: 30000,
  })

  const { data: overview, isLoading: overviewLoading } = useQuery({
    queryKey: ['dashboard-overview'],
    queryFn: () => dashboardApi.getOverview().then(r => r.data),
    refetchInterval: 30000,
  })

  const statCards = [
    {
      label: 'Leads Contacted',
      value: stats?.leads_contacted || 0,
      icon: Users,
      color: 'blue',
    },
    {
      label: 'Replies Received',
      value: stats?.replies_received || 0,
      icon: MessageSquare,
      color: 'purple',
    },
    {
      label: 'Interested',
      value: stats?.interested_leads || 0,
      icon: ThumbsUp,
      color: 'green',
    },
    {
      label: 'Not Interested',
      value: stats?.not_interested_leads || 0,
      icon: ThumbsDown,
      color: 'red',
    },
    {
      label: 'Awaiting Reply',
      value: stats?.awaiting_reply || 0,
      icon: Clock,
      color: 'yellow',
    },
    {
      label: 'Closed',
      value: stats?.closed_leads || 0,
      icon: XCircle,
      color: 'gray',
    },
  ]

  const colorStyles: Record<string, { bg: string; text: string; icon: string }> = {
    blue: { bg: 'bg-blue-50', text: 'text-blue-700', icon: 'text-blue-500' },
    purple: { bg: 'bg-purple-50', text: 'text-purple-700', icon: 'text-purple-500' },
    green: { bg: 'bg-green-50', text: 'text-green-700', icon: 'text-green-500' },
    red: { bg: 'bg-red-50', text: 'text-red-700', icon: 'text-red-500' },
    yellow: { bg: 'bg-yellow-50', text: 'text-yellow-700', icon: 'text-yellow-500' },
    gray: { bg: 'bg-gray-50', text: 'text-gray-700', icon: 'text-gray-500' },
  }

  if (statsLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-10 h-10 animate-spin text-gray-400" />
      </div>
    )
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center gap-3">
        <BarChart3 className="w-8 h-8 text-blue-600" />
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        {statCards.map(({ label, value, icon: Icon, color }) => {
          const styles = colorStyles[color]
          return (
            <div
              key={label}
              className={`${styles.bg} rounded-xl p-4 border border-${color}-100`}
            >
              <div className="flex items-center gap-2 mb-2">
                <Icon className={`w-5 h-5 ${styles.icon}`} />
                <span className="text-sm text-gray-600">{label}</span>
              </div>
              <p className={`text-3xl font-bold ${styles.text}`}>{value}</p>
            </div>
          )
        })}
      </div>

      {/* Summary Cards */}
      <div className="grid md:grid-cols-2 gap-6">
        {/* Total Summary */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Overall Summary</h2>
          <div className="space-y-3">
            <div className="flex justify-between items-center py-2 border-b border-gray-100">
              <span className="text-gray-600">Total Leads</span>
              <span className="font-semibold text-gray-900">{stats?.total_leads || 0}</span>
            </div>
            <div className="flex justify-between items-center py-2 border-b border-gray-100">
              <span className="text-gray-600">Total Campaigns</span>
              <span className="font-semibold text-gray-900">{stats?.total_campaigns || 0}</span>
            </div>
            <div className="flex justify-between items-center py-2 border-b border-gray-100">
              <span className="text-gray-600">Response Rate</span>
              <span className="font-semibold text-gray-900">
                {stats?.leads_contacted
                  ? ((stats.replies_received / stats.leads_contacted) * 100).toFixed(1)
                  : 0}%
              </span>
            </div>
            <div className="flex justify-between items-center py-2">
              <span className="text-gray-600">Interest Rate</span>
              <span className="font-semibold text-green-600">
                {stats?.replies_received
                  ? ((stats.interested_leads / stats.replies_received) * 100).toFixed(1)
                  : 0}%
              </span>
            </div>
          </div>
        </div>

        {/* Leads Requiring Attention */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Leads Requiring Attention</h2>
          {overviewLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
            </div>
          ) : !overview?.leads_requiring_attention?.length ? (
            <p className="text-gray-500 text-center py-8">No leads need attention right now</p>
          ) : (
            <div className="space-y-3">
              {overview.leads_requiring_attention.map((lead: { id: number; name: string; email: string; company: string }) => (
                <div
                  key={lead.id}
                  className="flex items-center justify-between p-3 bg-orange-50 border border-orange-100 rounded-lg"
                >
                  <div>
                    <p className="font-medium text-gray-900">{lead.name}</p>
                    <p className="text-sm text-gray-500">{lead.company}</p>
                  </div>
                  <span className="text-xs text-orange-600 font-medium">Interested</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* State Breakdown */}
      {overview?.state_breakdown && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Lead State Distribution</h2>
          <div className="grid grid-cols-4 md:grid-cols-8 gap-4">
            {Object.entries(overview.state_breakdown).map(([state, count]) => (
              <div key={state} className="text-center">
                <p className="text-2xl font-bold text-gray-900">{count as number}</p>
                <p className="text-xs text-gray-500">{state.replace(/_/g, ' ')}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent Campaigns */}
      {overview?.recent_campaigns && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Recent Campaigns</h2>
          {!overview.recent_campaigns.length ? (
            <p className="text-gray-500 text-center py-4">No campaigns yet</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-gray-200">
                    <th className="text-left py-2 text-sm font-medium text-gray-500">Keywords</th>
                    <th className="text-left py-2 text-sm font-medium text-gray-500">Status</th>
                    <th className="text-right py-2 text-sm font-medium text-gray-500">Valid Leads</th>
                    <th className="text-left py-2 text-sm font-medium text-gray-500">Created</th>
                  </tr>
                </thead>
                <tbody>
                  {overview.recent_campaigns.map((campaign: { id: number; keywords: string; status: string; leads_valid: number; created_at: string }) => (
                    <tr key={campaign.id} className="border-b border-gray-100">
                      <td className="py-3 text-gray-900">{campaign.keywords}</td>
                      <td className="py-3">
                        <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                          campaign.status === 'ACTIVE' ? 'bg-green-100 text-green-700' :
                          campaign.status === 'COLLECTING' ? 'bg-blue-100 text-blue-700' :
                          'bg-gray-100 text-gray-700'
                        }`}>
                          {campaign.status}
                        </span>
                      </td>
                      <td className="py-3 text-right text-gray-600">{campaign.leads_valid}</td>
                      <td className="py-3 text-gray-500 text-sm">
                        {new Date(campaign.created_at).toLocaleDateString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
