import axios from 'axios'

// Use environment variable for API URL, fallback to relative path for local dev
const API_BASE_URL = import.meta.env.VITE_API_URL || '/api'
console.log('API_BASE_URL:', API_BASE_URL)
console.log('VITE_API_URL env:', import.meta.env.VITE_API_URL)

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Types
export interface DashboardStats {
  leads_contacted: number
  replies_received: number
  interested_leads: number
  not_interested_leads: number
  closed_leads: number
  awaiting_reply: number
  total_leads: number
  total_campaigns: number
}

export interface Campaign {
  id: number
  keywords: string
  status: string
  leads_found: number
  leads_valid: number
  leads_enriched: number
  leads_emailed: number
  created_at: string
}

export interface Lead {
  id: number
  campaign_id: number
  state: string
  first_name: string
  last_name: string
  email: string
  linkedin_url: string
  job_title?: string
  company_name?: string
  industry?: string
  created_at: string
  emails_sent_count: number
}

export interface EmailThread {
  id: number
  lead_id: number
  lead_name: string
  lead_email: string
  lead_company?: string
  lead_state: string
  subject: string
  messages_count: number
  has_reply: boolean
  requires_human: boolean
  reply_sentiment?: string
  created_at: string
  updated_at: string
}

export interface GmailStatus {
  authenticated: boolean
  rate_limits: {
    daily_sent: number
    daily_limit: number
    remaining: number
    can_send_now: boolean
  }
}

// API functions
export const searchApi = {
  startSearch: (keywords: string) =>
    api.post<{ campaign_id: number; status: string; message: string }>('/search', { keywords }),

  uploadLeads: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return api.post<{ campaign_id: number; status: string; message: string }>(
      '/search/upload',
      form,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    )
  },

  getCampaigns: () =>
    api.get<{ campaigns: Campaign[] }>('/search/campaigns'),

  getCampaign: (id: number) =>
    api.get<Campaign>(`/search/campaigns/${id}`),

  uploadCompanyInfo: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return api.post<{ message: string; length: number }>(
      '/search/company-info',
      form,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    )
  },

  getCompanyInfo: () =>
    api.get<{ has_context: boolean; text: string }>('/search/company-info'),
}

export const leadsApi = {
  getLeads: (params?: { page?: number; per_page?: number; state?: string; campaign_id?: number }) =>
    api.get<{ leads: Lead[]; total: number; page: number; per_page: number }>('/leads', { params }),

  getLead: (id: number) =>
    api.get(`/leads/${id}`),

  sendEmail: (id: number) =>
    api.post(`/leads/${id}/send-email`),

  getStatesSummary: () =>
    api.get<{ states: Record<string, number> }>('/leads/states/summary'),

  downloadExportCsv: (params?: { state?: string; campaign_id?: number }) =>
    api.get('/leads/export/csv', { params, responseType: 'blob' }),

  generateFirstMessage: (id: number) =>
    api.post<{ subject: string; body: string }>(`/leads/${id}/generate-first-message`),

  generateAllFirstMessages: () =>
    api.post<{ generated: number; skipped: number; message: string }>('/leads/generate-all-first-messages'),
}

export const inboxApi = {
  getThreads: (params?: { requires_human?: boolean; has_reply?: boolean }) =>
    api.get<{ threads: EmailThread[]; total: number }>('/inbox', { params }),

  getThread: (id: number) =>
    api.get(`/inbox/${id}`),

  sendReply: (id: number, content: string) =>
    api.post(`/inbox/${id}/reply`, { content }),

  getStats: () =>
    api.get('/inbox/summary/stats'),
}

export const dashboardApi = {
  getStats: () =>
    api.get<DashboardStats>('/dashboard/stats'),

  getOverview: () =>
    api.get('/dashboard/overview'),
}

export const authApi = {
  getGmailStatus: () =>
    api.get<GmailStatus>('/auth/gmail/status'),

  initiateGmailAuth: () => {
    window.location.href = `${API_BASE_URL}/auth/gmail`
  },
}

export default api
