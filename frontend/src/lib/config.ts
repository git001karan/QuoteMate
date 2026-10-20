export const APP_NAME = 'QuoteMate'
export const WORKSPACE = 'Cerevyn Solutions · PS05'

// Exact phrases verified against the backend's trained NLP intents:
// "Yes, please confirm this quotation."  -> confirmation intent
// "No, please cancel this quotation."    -> decline intent
export const CONFIRM_TEXT = 'Yes, please confirm this quotation.'
export const DECLINE_TEXT = 'No, please cancel this quotation.'

export const DEFAULT_SENDER = 'customer_001'
export const HEALTH_POLL_INTERVAL_MS = 8000