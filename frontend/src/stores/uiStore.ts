import { create } from 'zustand'

const IOS_BANNER_KEY = 'ios-banner-dismissed'

interface UiState {
  activeTab: string
  iOSBannerDismissed: boolean
  setActiveTab: (tab: string) => void
  setIOSBannerDismissed: (dismissed: boolean) => void
}

export const useUiStore = create<UiState>(() => ({
  activeTab: 'today',
  // Seed from localStorage on init
  iOSBannerDismissed: localStorage.getItem(IOS_BANNER_KEY) === 'true',
  setActiveTab: (tab: string) => useUiStore.setState({ activeTab: tab }),
  setIOSBannerDismissed: (dismissed: boolean) => {
    localStorage.setItem(IOS_BANNER_KEY, String(dismissed))
    useUiStore.setState({ iOSBannerDismissed: dismissed })
  },
}))
