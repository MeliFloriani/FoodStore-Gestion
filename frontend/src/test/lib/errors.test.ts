import { describe, it, expect } from 'vitest'
import axios from 'axios'
import { normalizeError } from '@/shared/lib/errors'

function makeAxiosError(status: number, detail?: string) {
  const error = new axios.AxiosError(
    `Request failed with status code ${status}`,
    String(status),
    undefined,
    undefined,
    {
      data: detail ? { detail } : {},
      status,
      statusText: String(status),
      headers: {},
      config: { headers: new axios.AxiosHeaders() },
    },
  )
  return error
}

describe('normalizeError', () => {
  it('maps 401 to AUTH_EXPIRED', () => {
    const error = makeAxiosError(401, 'Token expired')
    const result = normalizeError(error)
    expect(result.code).toBe('AUTH_EXPIRED')
    expect(result.status).toBe(401)
  })

  it('maps 403 to FORBIDDEN', () => {
    const error = makeAxiosError(403)
    const result = normalizeError(error)
    expect(result.code).toBe('FORBIDDEN')
    expect(result.status).toBe(403)
  })

  it('maps 404 to NOT_FOUND', () => {
    const error = makeAxiosError(404)
    const result = normalizeError(error)
    expect(result.code).toBe('NOT_FOUND')
    expect(result.status).toBe(404)
  })

  it('maps 422 to VALIDATION_ERROR with details', () => {
    const axisError = new axios.AxiosError(
      'Validation error',
      '422',
      undefined,
      undefined,
      {
        data: { detail: { field: 'required' } },
        status: 422,
        statusText: 'Unprocessable Entity',
        headers: {},
        config: { headers: new axios.AxiosHeaders() },
      },
    )
    const result = normalizeError(axisError)
    expect(result.code).toBe('VALIDATION_ERROR')
    expect(result.details).toEqual({ field: 'required' })
  })

  it('maps 429 to RATE_LIMITED', () => {
    const error = makeAxiosError(429)
    const result = normalizeError(error)
    expect(result.code).toBe('RATE_LIMITED')
    expect(result.status).toBe(429)
  })

  it('maps 500 to SERVER_ERROR', () => {
    const error = makeAxiosError(500)
    const result = normalizeError(error)
    expect(result.code).toBe('SERVER_ERROR')
    expect(result.status).toBe(500)
  })

  it('maps 503 to SERVER_ERROR', () => {
    const error = makeAxiosError(503)
    const result = normalizeError(error)
    expect(result.code).toBe('SERVER_ERROR')
  })

  it('maps plain Error to UNKNOWN', () => {
    const result = normalizeError(new Error('something broke'))
    expect(result.code).toBe('UNKNOWN')
    expect(result.message).toBe('something broke')
  })

  it('maps unknown non-error to UNKNOWN', () => {
    const result = normalizeError('some string')
    expect(result.code).toBe('UNKNOWN')
  })
})
