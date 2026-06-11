export interface AdProfile {
  email?: string
  full_name?: string
  first_name?: string
  last_name?: string
  job_title?: string
  department?: string
  employee_id?: string
  is_active?: boolean
}

export interface ToolRow {
  work_email?: string
  tool_name?: string
  username?: string
  status?: string
  user_role?: string
  last_login_date?: string
}

export interface PickerUser {
  email?: string
  full_name?: string
  first_name?: string
  last_name?: string
  job_title?: string
  department?: string
}

export interface SearchResult {
  ad_profile: AdProfile | null
  tool_access: ToolRow[]
  picker_users: PickerUser[]
  error: string | null
}

export async function searchUsers(q: string): Promise<SearchResult> {
  const resp = await fetch(`/api/search?q=${encodeURIComponent(q)}`)
  if (!resp.ok) {
    return {
      ad_profile: null,
      tool_access: [],
      picker_users: [],
      error: `Request failed: HTTP ${resp.status}`,
    }
  }
  return resp.json() as Promise<SearchResult>
}
