import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * Small data-fetching hook with loading / error / refetch support.
 * Prevents state updates after unmount and ignores stale responses.
 *
 * @param {Function} loader  async () => data
 * @param {Array} deps       dependency list (like useEffect)
 */
export function useAsync(loader, deps = []) {
  const [state, setState] = useState({ data: null, loading: true, error: null })
  const requestId = useRef(0)
  const mounted = useRef(true)

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])

  const run = useCallback(async () => {
    const id = ++requestId.current
    setState((s) => ({ ...s, loading: true, error: null }))
    try {
      const data = await loader()
      if (!mounted.current || id !== requestId.current) return
      setState({ data, loading: false, error: null })
    } catch (error) {
      if (!mounted.current || id !== requestId.current) return
      setState({ data: null, loading: false, error })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  useEffect(() => {
    run()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [run])

  return { ...state, refetch: run, setData: (data) => setState((s) => ({ ...s, data })) }
}

export default useAsync
