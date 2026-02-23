import { useRef, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Search,
  Loader2,
  CheckCircle,
  AlertCircle,
  Clock,
  Upload,
  FileText,
  X,
  Building2,
} from 'lucide-react'
import { searchApi, authApi } from '../api/client'

type ActiveTab = 'search' | 'upload'

export default function SearchPage() {
  const [keywords, setKeywords] = useState('')
  const [activeTab, setActiveTab] = useState<ActiveTab>('search')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const companyFileInputRef = useRef<HTMLInputElement>(null)
  const queryClient = useQueryClient()

  // Check Gmail auth status
  const { data: gmailStatus } = useQuery({
    queryKey: ['gmail-status'],
    queryFn: () => authApi.getGmailStatus().then(r => r.data),
  })

  // Get company info status
  const { data: companyInfo } = useQuery({
    queryKey: ['company-info'],
    queryFn: () => searchApi.getCompanyInfo().then(r => r.data),
  })

  // Get campaigns
  const { data: campaignsData, isLoading: campaignsLoading } = useQuery({
    queryKey: ['campaigns'],
    queryFn: () => searchApi.getCampaigns().then(r => r.data),
    refetchInterval: 5000,
  })

  // Start search mutation
  const searchMutation = useMutation({
    mutationFn: (keywords: string) => searchApi.startSearch(keywords),
    onSuccess: () => {
      setKeywords('')
      queryClient.invalidateQueries({ queryKey: ['campaigns'] })
    },
  })

  // Upload mutation
  const uploadMutation = useMutation({
    mutationFn: (file: File) => searchApi.uploadLeads(file),
    onSuccess: () => {
      setSelectedFile(null)
      queryClient.invalidateQueries({ queryKey: ['campaigns'] })
    },
  })

  // Company info upload mutation
  const companyInfoMutation = useMutation({
    mutationFn: (file: File) => searchApi.uploadCompanyInfo(file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['company-info'] })
    },
  })

  const handleCompanyFileChange = (file: File | null) => {
    if (file && /\.(txt|md)$/i.test(file.name)) {
      companyInfoMutation.mutate(file)
    }
  }

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (keywords.trim()) {
      searchMutation.mutate(keywords.trim())
    }
  }

  const handleUpload = (e: React.FormEvent) => {
    e.preventDefault()
    if (selectedFile) {
      uploadMutation.mutate(selectedFile)
    }
  }

  const handleFileChange = (file: File | null) => {
    if (file && file.name.toLowerCase().endsWith('.csv')) {
      setSelectedFile(file)
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files[0] ?? null
    handleFileChange(file)
  }

  const getStatusBadge = (status: string) => {
    const styles: Record<string, { bg: string; text: string; icon: React.ReactNode }> = {
      PENDING:    { bg: 'bg-gray-100',   text: 'text-gray-700',  icon: <Clock className="w-3 h-3" /> },
      COLLECTING: { bg: 'bg-blue-100',   text: 'text-blue-700',  icon: <Loader2 className="w-3 h-3 animate-spin" /> },
      ENRICHING:  { bg: 'bg-yellow-100', text: 'text-yellow-700',icon: <Loader2 className="w-3 h-3 animate-spin" /> },
      ACTIVE:     { bg: 'bg-green-100',  text: 'text-green-700', icon: <CheckCircle className="w-3 h-3" /> },
      COMPLETED:  { bg: 'bg-green-100',  text: 'text-green-700', icon: <CheckCircle className="w-3 h-3" /> },
      FAILED:     { bg: 'bg-red-100',    text: 'text-red-700',   icon: <AlertCircle className="w-3 h-3" /> },
    }
    const style = styles[status] || styles.PENDING
    return (
      <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${style.bg} ${style.text}`}>
        {style.icon}
        {status}
      </span>
    )
  }

  const isUploadCampaign = (keywords: string) => keywords.startsWith('[Upload]')

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

      {/* Company Info Card */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Building2 className="w-5 h-5 text-gray-500" />
            <div>
              <h3 className="font-medium text-gray-900">Company Info</h3>
              <p className="text-sm text-gray-500">
                {companyInfo?.has_context
                  ? `Loaded (${companyInfo.text.length.toLocaleString()} chars) — used to personalize outreach emails`
                  : 'Upload a .txt or .md file describing your company to personalize cold emails'}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {companyInfoMutation.isPending && (
              <Loader2 className="w-4 h-4 animate-spin text-blue-500" />
            )}
            {companyInfoMutation.isSuccess && (
              <CheckCircle className="w-4 h-4 text-green-500" />
            )}
            {companyInfoMutation.isError && (
              <AlertCircle className="w-4 h-4 text-red-500" />
            )}
            <input
              ref={companyFileInputRef}
              type="file"
              accept=".txt,.md"
              className="hidden"
              onChange={(e) => {
                handleCompanyFileChange(e.target.files?.[0] ?? null)
                e.target.value = ''
              }}
            />
            <button
              onClick={() => companyFileInputRef.current?.click()}
              disabled={companyInfoMutation.isPending}
              className="flex items-center gap-2 px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 disabled:opacity-50 transition-colors text-sm font-medium"
            >
              <Upload className="w-4 h-4" />
              {companyInfo?.has_context ? 'Replace' : 'Upload Company Info'}
            </button>
          </div>
        </div>
      </div>

      {/* Search / Upload Card */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-4">Find New Leads</h1>

        {/* Tab Toggle */}
        <div className="flex gap-1 p-1 bg-gray-100 rounded-lg w-fit mb-6">
          <button
            onClick={() => setActiveTab('search')}
            className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              activeTab === 'search'
                ? 'bg-white text-blue-700 shadow-sm'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            <Search className="w-4 h-4" />
            Search
          </button>
          <button
            onClick={() => setActiveTab('upload')}
            className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              activeTab === 'upload'
                ? 'bg-white text-blue-700 shadow-sm'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            <Upload className="w-4 h-4" />
            Upload
          </button>
        </div>

        {/* Search Panel */}
        {activeTab === 'search' && (
          <>
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
                <p className="text-green-800">Campaign started! Leads are being collected in the background.</p>
              </div>
            )}
            {searchMutation.isError && (
              <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg">
                <p className="text-red-800">Error starting search. Please try again.</p>
              </div>
            )}
          </>
        )}

        {/* Upload Panel */}
        {activeTab === 'upload' && (
          <>
            <p className="text-gray-600 mb-6">
              Upload a CSV file with your lead list. Leads will be enriched with LinkedIn data and
              then enter the same outreach flow as search-sourced leads.
            </p>

            <form onSubmit={handleUpload} className="space-y-5">
              {/* Drop zone */}
              <div
                onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                className={`relative flex flex-col items-center justify-center gap-3 border-2 border-dashed rounded-xl p-10 cursor-pointer transition-colors ${
                  dragOver
                    ? 'border-blue-400 bg-blue-50'
                    : 'border-gray-300 hover:border-blue-400 hover:bg-gray-50'
                }`}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".csv"
                  className="hidden"
                  onChange={(e) => handleFileChange(e.target.files?.[0] ?? null)}
                />

                {selectedFile ? (
                  <>
                    <FileText className="w-10 h-10 text-blue-500" />
                    <div className="text-center">
                      <p className="font-medium text-gray-900">{selectedFile.name}</p>
                      <p className="text-sm text-gray-500">
                        {(selectedFile.size / 1024).toFixed(1)} KB
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={(e) => { e.stopPropagation(); setSelectedFile(null) }}
                      className="absolute top-3 right-3 p-1 rounded-full text-gray-400 hover:text-gray-600 hover:bg-gray-100"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </>
                ) : (
                  <>
                    <Upload className="w-10 h-10 text-gray-400" />
                    <div className="text-center">
                      <p className="font-medium text-gray-700">Drop a CSV file here or click to browse</p>
                      <p className="text-sm text-gray-500 mt-1">CSV files only</p>
                    </div>
                  </>
                )}
              </div>

              {/* Column reference */}
              <div className="bg-gray-50 rounded-lg p-4 text-sm text-gray-600 space-y-1">
                <p className="font-medium text-gray-700 mb-2">Expected CSV columns</p>
                <p>
                  <span className="font-medium text-gray-800">Required: </span>
                  <code className="bg-white px-1 rounded border border-gray-200">email</code>,{' '}
                  <code className="bg-white px-1 rounded border border-gray-200">linkedin</code>,{' '}
                  <code className="bg-white px-1 rounded border border-gray-200">first_name</code>,{' '}
                  <code className="bg-white px-1 rounded border border-gray-200">last_name</code>
                </p>
                <p>
                  <span className="font-medium text-gray-800">Optional: </span>
                  <code className="bg-white px-1 rounded border border-gray-200">full_name</code>,{' '}
                  <code className="bg-white px-1 rounded border border-gray-200">job_title</code>,{' '}
                  <code className="bg-white px-1 rounded border border-gray-200">headline</code>,{' '}
                  <code className="bg-white px-1 rounded border border-gray-200">city</code>,{' '}
                  <code className="bg-white px-1 rounded border border-gray-200">country</code>,{' '}
                  <code className="bg-white px-1 rounded border border-gray-200">company_name</code>,{' '}
                  <code className="bg-white px-1 rounded border border-gray-200">industry</code>,{' '}
                  <code className="bg-white px-1 rounded border border-gray-200">company_description</code>
                </p>
                <p className="text-gray-500 text-xs pt-1">
                  Rows missing <code className="bg-white px-1 rounded border border-gray-200">email</code> or{' '}
                  <code className="bg-white px-1 rounded border border-gray-200">linkedin</code> are skipped automatically.
                </p>
              </div>

              <button
                type="submit"
                disabled={!selectedFile || uploadMutation.isPending}
                className="flex items-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {uploadMutation.isPending ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <Upload className="w-5 h-5" />
                )}
                {uploadMutation.isPending ? 'Uploading...' : 'Upload Leads'}
              </button>
            </form>

            {uploadMutation.isSuccess && (
              <div className="mt-4 p-4 bg-green-50 border border-green-200 rounded-lg">
                <p className="text-green-800">
                  Upload accepted! Leads are being enriched in the background.
                </p>
              </div>
            )}
            {uploadMutation.isError && (
              <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg">
                <p className="text-red-800">
                  {(uploadMutation.error as { response?: { data?: { detail?: string } } })
                    ?.response?.data?.detail ?? 'Error uploading file. Please try again.'}
                </p>
              </div>
            )}
          </>
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
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-500">Source / Keywords</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-500">Status</th>
                  <th className="text-right py-3 px-4 text-sm font-medium text-gray-500">Found</th>
                  <th className="text-right py-3 px-4 text-sm font-medium text-gray-500">Valid</th>
                  <th className="text-right py-3 px-4 text-sm font-medium text-gray-500">Enriched</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-500">Created</th>
                </tr>
              </thead>
              <tbody>
                {campaignsData.campaigns.map((campaign) => {
                  const isUpload = isUploadCampaign(campaign.keywords)
                  const displayLabel = isUpload
                    ? campaign.keywords.replace(/^\[Upload\]\s*/, '')
                    : campaign.keywords

                  return (
                    <tr key={campaign.id} className="border-b border-gray-100 hover:bg-gray-50">
                      <td className="py-3 px-4">
                        <div className="flex items-start gap-2 flex-wrap">
                          {isUpload ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-700 shrink-0">
                              <Upload className="w-3 h-3" />
                              Upload
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-700 shrink-0">
                              <Search className="w-3 h-3" />
                              Search
                            </span>
                          )}
                          <span className="text-gray-900 font-medium text-sm">{displayLabel}</span>
                        </div>
                      </td>
                      <td className="py-3 px-4">{getStatusBadge(campaign.status)}</td>
                      <td className="py-3 px-4 text-right text-gray-600">{campaign.leads_found}</td>
                      <td className="py-3 px-4 text-right text-gray-600">{campaign.leads_valid}</td>
                      <td className="py-3 px-4 text-right text-gray-600">{campaign.leads_enriched}</td>
                      <td className="py-3 px-4 text-gray-500 text-sm">
                        {new Date(campaign.created_at).toLocaleDateString()}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
