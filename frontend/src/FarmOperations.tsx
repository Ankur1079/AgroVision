import { useEffect, useState, type FormEvent } from 'react'
import FarmMap from './FarmMap'

const API = import.meta.env.VITE_API_URL ?? 'http://localhost:8002'

type Farm = {
  id: number
  name: string
  location: string
  latitude: number | null
  longitude: number | null
}

type Field = {
  id: number
  farm_id: number
  name: string
  area: number
  soil_type: string | null
  irrigation_method: string | null
  latitude: number | null
  longitude: number | null
  boundary_geojson: string | null
}

type Cycle = {
  id: number
  field_id: number
  crop_name: string
  variety: string | null
  season: string | null
  planting_date: string
  expected_harvest_date: string | null
  expected_harvest_quantity: number | null
  expected_harvest_unit: string | null
  harvest_date: string | null
  status: string
}

async function apiRequest<T>(token: string, path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    ...init,
    headers: {
      ...(init.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      Authorization: `Bearer ${token}`,
      ...init.headers,
    },
  })

  const body = await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail = typeof body?.detail === 'string' ? body.detail : `Request failed (${response.status})`
    throw new Error(detail)
  }
  return body as T
}

export default function FarmOperations({
  token,
  farms,
}: {
  token: string
  farms: Farm[]
}) {
  const [farmId, setFarmId] = useState<number>(0)
  const [fields, setFields] = useState<Field[]>([])
  const [fieldId, setFieldId] = useState<number>(0)
  const [cycles, setCycles] = useState<Cycle[]>([])
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const [drawing, setDrawing] = useState(false)
  const [boundary, setBoundary] = useState<number[][]>([])
  const [location, setLocation] = useState<[number, number] | null>(null)
  const [fieldsReload, setFieldsReload] = useState(0)
  const [cyclesReload, setCyclesReload] = useState(0)

  // Keep the selected farm valid when the dashboard's farm list loads or changes.
  useEffect(() => {
    if (farms.length === 0) {
      setFarmId(0)
      return
    }
    setFarmId((current) => farms.some((farm) => farm.id === current) ? current : farms[0].id)
  }, [farms])

  // Load plots for the selected farm. Cancellation prevents stale responses
  // from a previous farm overwriting the current farm's plots.
  useEffect(() => {
    let cancelled = false

    if (!token || !farmId) {
      setFields([])
      setFieldId(0)
      setCycles([])
      return () => { cancelled = true }
    }

    setFields([])
    setFieldId(0)
    setCycles([])
    setError('')

    apiRequest<Field[]>(token, `/api/v1/farms/${farmId}/fields`)
      .then((data) => {
        if (cancelled) return
        setFields(data)
        setFieldId(data[0]?.id ?? 0)
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Could not load fields')
      })

    return () => { cancelled = true }
  }, [token, farmId, fieldsReload])

  // Load crop-cycle history for the currently selected plot.
  useEffect(() => {
    let cancelled = false

    if (!token || !fieldId) {
      setCycles([])
      return () => { cancelled = true }
    }

    setCycles([])
    apiRequest<Cycle[]>(token, `/api/v1/fields/${fieldId}/crop-cycles`)
      .then((data) => {
        if (!cancelled) setCycles(data)
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Could not load crop-cycle history')
      })

    return () => { cancelled = true }
  }, [token, fieldId, cyclesReload])

  async function createField(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!farmId) {
      setError('Select a farm before adding a field.')
      return
    }

    const formElement = event.currentTarget
    const form = new FormData(formElement)
    setBusy(true)
    setError('')
    setNotice('')

    const geoJson = boundary.length >= 4
      ? JSON.stringify({
          type: 'Polygon',
          coordinates: [boundary.map(([lat, lng]) => [lng, lat])],
        })
      : null

    try {
      await apiRequest<Field>(token, `/api/v1/farms/${farmId}/fields`, {
        method: 'POST',
        body: JSON.stringify({
          name: String(form.get('name') ?? '').trim(),
          area: Number(form.get('area')),
          soil_type: form.get('soil_type') || null,
          irrigation_method: form.get('irrigation_method') || null,
          latitude: location?.[0] ?? null,
          longitude: location?.[1] ?? null,
          boundary_geojson: geoJson,
        }),
      })

      formElement.reset()
      setBoundary([])
      setLocation(null)
      setDrawing(false)
      setNotice('Field/plot saved successfully.')
      setFieldsReload((value) => value + 1)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not save field/plot')
    } finally {
      setBusy(false)
    }
  }

  async function createCycle(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!fieldId) {
      setError('Select a field before creating a crop cycle.')
      return
    }

    const formElement = event.currentTarget
    const form = new FormData(formElement)
    setBusy(true)
    setError('')
    setNotice('')

    try {
      await apiRequest<Cycle>(token, `/api/v1/fields/${fieldId}/crop-cycles`, {
        method: 'POST',
        body: JSON.stringify({
          crop_name: String(form.get('crop_name') ?? '').trim(),
          variety: form.get('variety') || null,
          season: form.get('season') || null,
          planting_date: form.get('planting_date'),
          expected_harvest_date: form.get('expected_harvest_date') || null,
          expected_harvest_quantity: form.get('expected_harvest_quantity')
            ? Number(form.get('expected_harvest_quantity'))
            : null,
          expected_harvest_unit: form.get('expected_harvest_unit') || null,
        }),
      })
      formElement.reset()
      setNotice('Crop cycle saved successfully.')
      setCyclesReload((value) => value + 1)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not save crop cycle')
    } finally {
      setBusy(false)
    }
  }

  async function completeCycle(cycle: Cycle) {
    setError('')
    setNotice('')
    try {
      await apiRequest(token, `/api/v1/crop-cycles/${cycle.id}/status`, {
        method: 'PATCH',
        body: JSON.stringify({ status: 'completed' }),
      })
      setNotice('Crop cycle marked completed. Its history has been retained.')
      setCyclesReload((value) => value + 1)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not update crop cycle')
    }
  }

  return (
    <section className="panel farm-operations" id="crops">
      <div className="panel-heading">
        <div>
          <div className="eyebrow">FIELD & CROP MANAGEMENT</div>
          <h2>Farms, fields and crop history</h2>
          <p>Save plot details, map locations and boundaries, and track planting cycles.</p>
        </div>
      </div>

      {error && <div className="alert error" role="alert">{error}</div>}
      {notice && <div className="alert success" role="status">{notice}</div>}

      {farms.length === 0 ? (
        <p className="muted">Register a farm first to add fields and crop cycles.</p>
      ) : (
        <>
          <label className="ops-select">
            Select farm
            <select value={farmId || ''} onChange={(event) => setFarmId(Number(event.target.value))}>
              <option value="">Select farm</option>
              {farms.map((farm) => <option key={farm.id} value={farm.id}>{farm.name} — {farm.location}</option>)}
            </select>
          </label>

          <h3>Farm and field map</h3>
          <FarmMap
            farms={farms}
            plots={fields}
            drawing={drawing}
            onBoundary={(points) => { setBoundary(points); setDrawing(false) }}
            onSelectLocation={(point) => setLocation(point)}
          />
          <p className="fine-print">
            Selected field location: {location ? `${location[0].toFixed(6)}, ${location[1].toFixed(6)}` : 'click the map to set it'}.
            {' '}Verify map coordinates against the real property before relying on them.
          </p>

          <form className="farm-form ops-form" onSubmit={createField}>
            <h3 className="wide">Add a field / plot</h3>
            <label>Plot name<input name="name" required minLength={1} maxLength={120} placeholder="North plot" /></label>
            <label>Area<input name="area" type="number" min="0.01" step="any" required placeholder="Field area" /></label>
            <label>Soil type<select name="soil_type"><option value="">Not recorded</option><option>Alluvial</option><option>Clay</option><option>Sandy</option><option>Loamy</option><option>Black cotton</option><option>Red</option><option>Laterite</option><option>Other</option></select></label>
            <label>Irrigation method<select name="irrigation_method"><option value="">Not recorded</option><option>Rainfed</option><option>Drip</option><option>Sprinkler</option><option>Canal</option><option>Flood</option><option>Borewell</option><option>Other</option></select></label>
            <div className="wide boundary-actions">
              <button type="button" className="secondary" onClick={() => { setDrawing((value) => !value); setBoundary([]) }}>
                {drawing ? 'Stop boundary drawing' : 'Draw field boundary on map'}
              </button>
              <span>{boundary.length >= 4 ? `${boundary.length - 1} boundary points captured` : 'Optional: click at least 3 corners, then close the boundary on the map.'}</span>
            </div>
            <div className="wide form-actions">
              <button className="primary" type="submit" disabled={busy || !farmId}>{busy ? 'Saving…' : 'Save field / plot'}</button>
            </div>
          </form>

          <div className="panel-heading ops-subhead">
            <div><h3>Fields / plots ({fields.length})</h3><p>Select a plot to view its planting history.</p></div>
          </div>

          {fields.length === 0 ? (
            <p className="muted">{error ? 'Fields could not be loaded; check the error above.' : 'No fields recorded for this farm yet.'}</p>
          ) : (
            <div className="field-chip-list">
              {fields.map((field) => (
                <button type="button" key={field.id} className={`field-chip ${fieldId === field.id ? 'selected' : ''}`} onClick={() => setFieldId(field.id)}>
                  <strong>{field.name}</strong>
                  <small>{field.area} area units · {field.soil_type || 'soil not recorded'} · {field.irrigation_method || 'irrigation not recorded'}</small>
                </button>
              ))}
            </div>
          )}

          {fieldId > 0 && (
            <>
              <form className="farm-form ops-form" onSubmit={createCycle}>
                <h3 className="wide">Record crop cycle</h3>
                <label>Crop name<input name="crop_name" required maxLength={100} placeholder="Rice, wheat, tomato…" /></label>
                <label>Variety<input name="variety" placeholder="Variety (optional)" /></label>
                <label>Season<select name="season"><option value="">Select season</option><option>Kharif</option><option>Rabi</option><option>Zaid</option><option>Perennial</option><option>Other</option></select></label>
                <label>Planting date<input name="planting_date" type="date" required /></label>
                <label>Expected harvest date<input name="expected_harvest_date" type="date" /></label>
                <label>Expected harvest quantity<input name="expected_harvest_quantity" type="number" min="0.001" step="any" placeholder="Optional" /></label>
                <label>Expected quantity unit<input name="expected_harvest_unit" placeholder="kg, tonnes, crates" /></label>
                <div className="wide form-actions"><button className="primary" type="submit" disabled={busy}>{busy ? 'Saving…' : 'Save crop cycle'}</button></div>
              </form>

              <div className="panel-heading ops-subhead"><div><h3>Crop-cycle history</h3><p>Active and completed records remain attached to this field.</p></div></div>
              {cycles.length === 0 ? (
                <p className="muted">No crop cycles recorded for this field yet.</p>
              ) : (
                <div className="cycle-list">
                  {cycles.map((cycle) => (
                    <article className="cycle-row" key={cycle.id}>
                      <div>
                        <strong>{cycle.crop_name}{cycle.variety ? ` · ${cycle.variety}` : ''}</strong>
                        <span>{cycle.season || 'Season not recorded'} · {cycle.planting_date} → {cycle.expected_harvest_date || 'Harvest date not set'}{cycle.expected_harvest_quantity ? ` · Expected ${cycle.expected_harvest_quantity} ${cycle.expected_harvest_unit || ''}` : ''}</span>
                      </div>
                      <span className={`pill ${cycle.status === 'completed' ? 'success' : 'neutral'}`}>{cycle.status}</span>
                      {cycle.status !== 'completed' && <button type="button" className="secondary" disabled={busy} onClick={() => completeCycle(cycle)}>Mark completed</button>}
                    </article>
                  ))}
                </div>
              )}
            </>
          )}
        </>
      )}
    </section>
  )
}
