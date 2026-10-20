import '@testing-library/jest-dom'
import { vi } from 'vitest'

// jsdom in this vitest setup lacks matchMedia; shim it for components that
// read media queries (e.g. responsive layout logic).
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(), // deprecated
    removeListener: vi.fn(), // deprecated
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
})