import '@testing-library/jest-dom'
import { afterEach } from 'vitest'

// Global safety net: several test files stub globalThis.localStorage with a
// custom in-memory mock (vi.stubGlobal) for individual tests. Under Node's
// experimental native Web Storage implementation, that stub/unstub bookkeeping
// can leak across test FILES within the same worker even when each file's own
// afterEach looks correct in isolation (only reproduces with the full suite).
// Force a clean slate after every single test, everywhere, regardless of
// whether the current test file remembered to clean up after itself.
afterEach(() => {
  try {
    localStorage.clear()
  } catch {
    // localStorage may not exist in some test environments — ignore.
  }
})
