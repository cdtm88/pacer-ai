import { create } from 'zustand'

const IOS_BANNER_KEY = 'ios-banner-dismissed'

interface UiState {
  activeTab: string
  iOSBannerDismissed: boolean
  setActiveTab: (tab: string) => void
  setIOSBannerDismissed: (dismissed: boolean) => void
}

function readDismissed(): boolean {
  try {
    return localStorage.getItem(IOS_BANNER_KEY) === 'true'
  } catch {
    return false
  }
}

export const useUiStore = create<UiState>(() => ({
  activeTab: 'today',
  // Seed from localStorage on init; wrapped in try/catch for SSR/test environments
  iOSBannerDismissed: readDismissed(),
  setActiveTab: (tab: string) => useUiStore.setState({ activeTab: tab }),
  setIOSBannerDismissed: (dismissed: boolean) => {
    localStorage.setItem(IOS_BANNER_KEY, String(dismissed))
    useUiStore.setState({ iOSBannerDismissed: dismissed })
  },
}))
