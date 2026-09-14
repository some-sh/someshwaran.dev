import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import App from './App'

describe('App', () => {
  it('renders the shadcn/ui wiring check button', () => {
    render(<App />)

    expect(screen.getByRole('button', { name: /shadcn\/ui is wired up/i })).toBeInTheDocument()
  })
})
