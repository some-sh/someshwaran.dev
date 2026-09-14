import '@testing-library/jest-dom/vitest'

// jsdom doesn't implement scrollTo; TanStack Router calls it by default
// on every navigation (defaultHashScrollIntoView). Harmless in tests,
// just noisy — stub it instead of disabling the feature app-wide.
window.scrollTo = () => {}
