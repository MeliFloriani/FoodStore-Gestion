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

function make422Error(detail: unknown) {
  return new axios.AxiosError(
    'Validation error',
    '422',
    undefined,
    undefined,
    {
      data: { detail },
      status: 422,
      statusText: 'Unprocessable Entity',
      headers: {},
      config: { headers: new axios.AxiosHeaders() },
    },
  )
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

  // ---------------------------------------------------------------------------
  // Task 10.4 — FastAPI 422 detail array parsing (D-H key derivation rule)
  // ---------------------------------------------------------------------------

  it('maps 422 to VALIDATION_ERROR with fieldErrors from FastAPI detail array', () => {
    const detail = [
      { loc: ['body', 'email'], msg: 'value is not a valid email address', type: 'value_error' },
    ]
    const result = normalizeError(make422Error(detail))
    expect(result.code).toBe('VALIDATION_ERROR')
    expect(result.status).toBe(422)
    expect(result.fieldErrors).toEqual({
      email: ['value is not a valid email address'],
    })
  })

  it('422: single body field (loc.length === 2) → key = loc[1]', () => {
    const detail = [
      { loc: ['body', 'password'], msg: 'String should have at least 8 characters', type: 'string_too_short' },
    ]
    const result = normalizeError(make422Error(detail))
    expect(result.fieldErrors?.['password']).toEqual(['String should have at least 8 characters'])
  })

  it('422: nested body field (loc.length > 2) → key = loc.slice(1).join(".")', () => {
    const detail = [
      { loc: ['body', 'address', 'city'], msg: 'Field required', type: 'missing' },
    ]
    const result = normalizeError(make422Error(detail))
    expect(result.fieldErrors?.['address.city']).toEqual(['Field required'])
  })

  it('422: non-body location → key = loc.join(".")', () => {
    const detail = [
      { loc: ['query', 'page'], msg: 'Input should be a valid integer', type: 'int_parsing' },
    ]
    const result = normalizeError(make422Error(detail))
    expect(result.fieldErrors?.['query.page']).toEqual(['Input should be a valid integer'])
  })

  it('422: multiple errors for the same field are accumulated into an array', () => {
    const detail = [
      { loc: ['body', 'password'], msg: 'String should have at least 8 characters', type: 'string_too_short' },
      { loc: ['body', 'password'], msg: 'Password must contain a number', type: 'value_error' },
    ]
    const result = normalizeError(make422Error(detail))
    expect(result.fieldErrors?.['password']).toHaveLength(2)
    expect(result.fieldErrors?.['password']).toContain('String should have at least 8 characters')
    expect(result.fieldErrors?.['password']).toContain('Password must contain a number')
  })

  it('422: flat-string detail does not crash — fieldErrors is undefined', () => {
    const result = normalizeError(make422Error('Validation failed'))
    expect(result.code).toBe('VALIDATION_ERROR')
    expect(result.fieldErrors).toBeUndefined()
  })

  it('422: object detail (non-array) does not crash — fieldErrors is undefined', () => {
    const result = normalizeError(make422Error({ field: 'required' }))
    expect(result.code).toBe('VALIDATION_ERROR')
    expect(result.fieldErrors).toBeUndefined()
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

  it('maps plain Error to UNKNOWN with null status', () => {
    const result = normalizeError(new Error('something broke'))
    expect(result.code).toBe('UNKNOWN')
    expect(result.message).toBe('something broke')
    expect(result.status).toBeNull()
  })

  it('maps unknown non-error to UNKNOWN with null status', () => {
    const result = normalizeError('some string')
    expect(result.code).toBe('UNKNOWN')
    expect(result.status).toBeNull()
  })
})
