import { create } from 'zustand'

const IOS_BANNER_KEY = 'ios-banner-dismissed'

interface UiState {
  activeTab: string
  iOSBannerDismissed: boolean
  freeRideDurationMins: number | null
  setActiveTab: (tab: string) => void
  setIOSBannerDismissed: (dismissed: boolean) => void
  setFreeRideDurationMins: (mins: number | null) => void
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
  // Ephemeral per-navigation handoff for rest-day free rides; not persisted
  freeRideDurationMins: null,
  setActiveTab: (tab: string) => useUiStore.setState({ activeTab: tab }),
  setIOSBannerDismissed: (dismissed: boolean) => {
    localStorage.setItem(IOS_BANNER_KEY, String(dismissed))
    useUiStore.setState({ iOSBannerDismissed: dismissed })
  },
  setFreeRideDurationMins: (mins: number | null) =>
    useUiStore.setState({ freeRideDurationMins: mins }),
}))
