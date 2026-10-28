import { useEffect, useState, type FormEvent } from 'react'
import FarmMap from './FarmMap'
import FarmOperations from './FarmOperations'
import FarmModules from './FarmModules'
import {
  FarmerAdvisorPanel,
  AdvisorPortal,
  AdminPortal,
} from './Portals'
import {
  Sprout,
  LayoutDashboard,
  Map,
  CalendarDays,
  CloudSun,
  ScanSearch,
  LogOut,
  Plus,
  ArrowUpRight,
  ShieldCheck,
  Leaf,
  LoaderCircle,
  Droplets,
  Wind,
  Thermometer,
  RefreshCw,
} from 'lucide-react'
const API = import.meta.env.VITE_API_URL ?? 'http://localhost:8002'

type User = {
  id: number
  email: string
  full_name: string
  role: string
}

type Farm = {
  id: number
  name: string
  location: string
  area: number
  area_unit: string
  soil_type: string | null
  latitude?: number | null
  longitude?: number | null
}

type Summary = {
  farms: number
  fields: number
  active_crop_cycles: number
  pending_tasks: number
  data_note: string
}

type WeatherResponse = {
  farm_id: number
  farm_name: string
  provider: string
  attribution: string
  fetched_at: string
  forecast: {
    latitude: number
    longitude: number
    timezone: string
    current_units: {
      temperature_2m: string
      relative_humidity_2m: string
      apparent_temperature: string
      precipitation: string
      wind_speed_10m: string
    }
    current: {
      time: string
      temperature_2m: number
      relative_humidity_2m: number
      apparent_temperature: number
      precipitation: number
      weather_code: number
      wind_speed_10m: number
    }
    daily: {
      time: string[]
      weather_code: number[]
      temperature_2m_max: number[]
      temperature_2m_min: number[]
      precipitation_sum: number[]
      precipitation_probability_max: number[]
      et0_fao_evapotranspiration: number[]
    }
  }
}

type PlantPrediction = {
  predicted_class: string
  confidence: number
  confidence_percent: number
  top_predictions: {
    class_name: string
    confidence: number
    confidence_percent: number
  }[]
  model?: string
  dataset?: string
  disclaimer?: string
}

function weatherDescription(code: number): string {
  if (code === 0) return 'Clear sky'
  if (code === 1) return 'Mainly clear'
  if (code === 2) return 'Partly cloudy'
  if (code === 3) return 'Overcast'
  if ([45, 48].includes(code)) return 'Fog'
  if ([51, 53, 55, 56, 57].includes(code)) return 'Drizzle'
  if ([61, 63, 65, 66, 67].includes(code)) return 'Rain'
  if ([71, 73, 75, 77, 85, 86].includes(code)) return 'Snow'
  if ([80, 81, 82].includes(code)) return 'Rain showers'
  if ([95, 96, 99].includes(code)) return 'Thunderstorm'
  return 'Conditions unavailable'
}

function formatDay(date: string): string {
  return new Date(`${date}T12:00:00`).toLocaleDateString('en-IN', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  })
}

function hasValidCoordinates(farm: Farm | undefined): boolean {
  return !!farm &&
    typeof farm.latitude === 'number' && Number.isFinite(farm.latitude) &&
    typeof farm.longitude === 'number' && Number.isFinite(farm.longitude) &&
    farm.latitude >= -90 && farm.latitude <= 90 &&
    farm.longitude >= -180 && farm.longitude <= 180 &&
    !(farm.latitude <= -89 && farm.longitude <= -179)
}

function isInvalidPlaceholderWeather(weather: WeatherResponse): boolean {
  return (
    (weather.forecast.latitude <= -89 && weather.forecast.longitude <= -179) ||
    weather.forecast.timezone === 'Antarctica/McMurdo'
  )
}

export default function App() {
  const [token, setToken] = useState(
    localStorage.getItem('agrovision_token') ?? '',
  )
  const [user, setUser] = useState<User | null>(null)
  const [farms, setFarms] = useState<Farm[]>([])
  const [summary, setSummary] = useState<Summary | null>(null)
  const [mode, setMode] = useState<'login' | 'register'>('register')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [showFarmForm, setShowFarmForm] = useState(false)
  const [activePage, setActivePage] = useState('overview')

  const [selectedFarmId, setSelectedFarmId] = useState<number | ''>('')
  const [weather, setWeather] = useState<WeatherResponse | null>(null)
  const [weatherBusy, setWeatherBusy] = useState(false)
  const [weatherError, setWeatherError] = useState('')
  const [weatherReload, setWeatherReload] = useState(0)

  const [plantImage, setPlantImage] = useState<File | null>(null)
  const [plantPrediction, setPlantPrediction] = useState<PlantPrediction | null>(null)
  const [plantBusy, setPlantBusy] = useState(false)
  const [plantError, setPlantError] = useState('')

  async function request(path: string, init: RequestInit = {}) {
    const response = await fetch(`${API}${path}`, {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...init.headers,
      },
    })

    const body = await response.json().catch(() => ({}))
    if (!response.ok) {
      const detail = typeof body?.detail === 'string'
        ? body.detail
        : `Request failed (${response.status})`
      throw new Error(detail)
    }

    return body
  }

  async function loadDashboard() {
    const [me, farmList, counts] = await Promise.all([
      request('/api/v1/auth/me'),
      request('/api/v1/farms'),
      request('/api/v1/dashboard/summary'),
    ])

    setUser(me)
    setFarms(farmList)
    setSummary(counts)

    setSelectedFarmId((current) => {
      if (farmList.some((farm: Farm) => farm.id === current)) {
        return current
      }
      return farmList[0]?.id ?? ''
    })
  }

  useEffect(() => {
    if (!token) return

    loadDashboard().catch((e: Error) => {
      setError(e.message)
      localStorage.removeItem('agrovision_token')
      setToken('')
    })
  }, [token])

  useEffect(() => {
    if (!token || selectedFarmId === '') {
      const selectedFarm = farms.find((farm) => farm.id === selectedFarmId)
      if (!hasValidCoordinates(selectedFarm)) {
        setWeather(null)
        setWeatherBusy(false)
        setWeatherError(
           'This farm has no valid latitude/longitude. Add its real coordinates in the farm record before requesting weather.',
  )
  return
}
    }

    let cancelled = false

    async function fetchWeather() {
      setWeatherBusy(true)
      setWeatherError('')
      setWeather(null)

      try {
        const result = (await request(
          `/api/v1/farms/${selectedFarmId}/weather`,
        )) as WeatherResponse

        if (cancelled) return

        if (
          !result.forecast?.current ||
          !result.forecast?.daily ||
          !Array.isArray(result.forecast.daily.time)
        ) {
          throw new Error('The weather service returned an unexpected response.')
        }

        if (isInvalidPlaceholderWeather(result)) {
          throw new Error(
            'This farm has invalid placeholder coordinates. Update its latitude and longitude to the real farm location before viewing weather.',
          )
        }

        setWeather(result)
      } catch (e) {
        if (!cancelled) {
          setWeatherError(
            e instanceof Error ? e.message : 'Unable to load weather.',
          )
        }
      } finally {
        if (!cancelled) setWeatherBusy(false)
      }
    }

    void fetchWeather()

    return () => {
      cancelled = true
    }
  }, [token, selectedFarmId, weatherReload])

  async function submitAuth(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setBusy(true)
    setError('')
    setNotice('')

    const form = new FormData(e.currentTarget)

    try {
      if (mode === 'register') {
        await request('/api/v1/auth/register', {
          method: 'POST',
          body: JSON.stringify({
            email: form.get('email'),
            full_name: form.get('full_name'),
            password: form.get('password'),
          }),
        })

        setNotice('Account created. Sign in using your email and password.')
        setMode('login')
      } else {
        const body = new URLSearchParams({
          username: String(form.get('email')),
          password: String(form.get('password')),
        })

        const response = await fetch(`${API}/api/v1/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body,
        })

        const result = await response.json()

        if (!response.ok) {
          throw new Error(result.detail ?? 'Login failed')
        }

        localStorage.setItem('agrovision_token', result.access_token)
        setToken(result.access_token)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unexpected error')
    } finally {
      setBusy(false)
    }
  }

  async function createFarm(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setBusy(true)
    setError('')

    const form = new FormData(e.currentTarget)

    try {
      await request('/api/v1/farms', {
        method: 'POST',
        body: JSON.stringify({
          name: form.get('name'),
          location: form.get('location'),
          area: Number(form.get('area')),
          area_unit: form.get('area_unit'),
          soil_type: form.get('soil_type') || null,
          latitude: form.get('latitude') ? Number(form.get('latitude')) : null,
          longitude: form.get('longitude') ? Number(form.get('longitude')) : null,
        }),
      })

      setShowFarmForm(false)
      await loadDashboard()
      setNotice('Farm saved successfully.')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not save farm')
    } finally {
      setBusy(false)
    }
  }

  async function submitPlantPrediction(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()

    if (!plantImage) {
      setPlantError('Choose a plant image first.')
      return
    }

    setPlantBusy(true)
    setPlantError('')
    setPlantPrediction(null)

    try {
      const formData = new FormData()
      formData.append('file', plantImage)

      const response = await fetch(
        `${API}/api/v1/plant-health/predict`,
        {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${token}`,
          },
          body: formData,
        },
      )

      const result = await response.json().catch(() => ({}))

      if (!response.ok) {
        throw new Error(
          result.detail ?? `Prediction failed (${response.status})`,
        )
      }

      setPlantPrediction(result as PlantPrediction)
    } catch (e) {
      setPlantError(
        e instanceof Error
          ? e.message
          : 'Unable to analyze this image.',
      )
    } finally {
      setPlantBusy(false)
    }
  }

  function logout() {
    localStorage.removeItem('agrovision_token')
    setToken('')
    setUser(null)
    setFarms([])
    setSummary(null)
    setWeather(null)
    setSelectedFarmId('')
  }

  if (!token) {
    return (
      <main className="auth-page">
        <div className="auth-brand">
          <div className="brand-icon"><Sprout size={25} /></div>
          <span>AgroVision</span>
        </div>

        <section className="auth-card">
          <div className="eyebrow">PRECISION FARMING PLATFORM</div>
          <h1>{mode === 'register' ? 'Start with your farm.' : 'Welcome back.'}</h1>
          <p className="muted">Manage farm records and crop activities in one place.</p>

          {error && <div className="alert error">{error}</div>}
          {notice && <div className="alert success">{notice}</div>}

          <form onSubmit={submitAuth} className="form-stack">
            {mode === 'register' && (
              <label>
                Full name
                <input name="full_name" minLength={2} required placeholder="Your full name" autoComplete="name" />
              </label>
            )}

            <label>
              Email address
              <input name="email" type="email" required placeholder="you@example.com" autoComplete="email" />
            </label>

            <label>
              Password
              <input
                name="password"
                type="password"
                minLength={10}
                required
                placeholder="At least 10 characters"
                autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
              />
            </label>

            <button className="primary full" disabled={busy}>
              {busy && <LoaderCircle className="spin" size={16} />}
              {mode === 'register' ? 'Create account' : 'Sign in'}
            </button>
          </form>

          <p className="switch-auth">
            {mode === 'register' ? 'Already registered?' : 'New to AgroVision?'}{' '}
            <button
              className="text-button"
              onClick={() => {
                setMode(mode === 'register' ? 'login' : 'register')
                setError('')
                setNotice('')
              }}
            >
              {mode === 'register' ? 'Sign in' : 'Create account'}
            </button>
          </p>

          <p className="fine-print">
            <ShieldCheck size={14} /> Your farm records are private to your account.
          </p>
        </section>

        <p className="auth-foot">A data-first workspace for better farm decisions.</p>
      </main>
    )
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon"><Sprout size={23} /></div>
          <div>
            <strong>AgroVision</strong>
            <small>FARM INTELLIGENCE</small>
          </div>
        </div>

        <div className="nav-label">WORKSPACE</div>

        <nav>
          <a className="nav-item active" href="#"><LayoutDashboard size={18} />Overview</a>
          <a className="nav-item" href="#farms"><Map size={18} />Farms & fields</a>
          <a className="nav-item" href="#crops"><Leaf size={18} />Crop cycles</a>
          <a className="nav-item" href="#tasks"><CalendarDays size={18} />Activities</a>
          <a className="nav-item" href="#weather"><CloudSun size={18} />Weather</a>
          <a className="nav-item" href="#farm-map"><Map size={18} />Farm Map</a>
          {user?.role === 'farmer' && (
            <button
              type="button"
              className={`nav-item ${activePage === 'farmer-advisory' ? 'active' : ''}`}
              onClick={() => setActivePage('farmer-advisory')}
            >
              <Leaf size={18} />
              Farmer Advisory
            </button>
          )}

          {user?.role === 'advisor' && (
            <button
              type="button"
              className={`nav-item ${activePage === 'advisor-portal' ? 'active' : ''}`}
              onClick={() => setActivePage('advisor-portal')}
            >
              <ShieldCheck size={18} />
              Advisor Portal
            </button>
          )}

          {user?.role === 'admin' && (
            <button
              type="button"
              className={`nav-item ${activePage === 'admin-portal' ? 'active' : ''}`}
              onClick={() => setActivePage('admin-portal')}
            >
              <ShieldCheck size={18} />
              Admin Portal
            </button>
          )}
        </nav>

        <div className="sidebar-bottom">
          <div className="user-mini">
            <div className="avatar">{user?.full_name?.slice(0, 1).toUpperCase()}</div>
            <div className="user-info">
              <strong>{user?.full_name}</strong>
              <small>{user?.email}</small>
            </div>
          </div>

          <button className="nav-item logout" onClick={logout}>
            <LogOut size={17} />Sign out
          </button>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div><span className="crumb">Workspace /</span> <strong>Overview</strong></div>
          <div className="top-user">
            <span className="status-dot" />Live database
            <div className="avatar small">{user?.full_name?.slice(0, 1).toUpperCase()}</div>
          </div>
        </header>

        {activePage === 'farmer-advisory' && user?.role === 'farmer' ? (
          <section className="page-content">
            <FarmerAdvisorPanel
              token={token}
              farms={farms.map((farm) => ({ id: farm.id, name: farm.name }))}
            />
          </section>
        ) : activePage === 'advisor-portal' && user?.role === 'advisor' ? (
          <section className="page-content">
            <AdvisorPortal token={token} />
          </section>
        ) : activePage === 'admin-portal' && user?.role === 'admin' ? (
          <section className="page-content">
            <AdminPortal token={token} />
          </section>
        ) : (
          <section className="page-content">
            <div className="welcome-row">
            <div>
              <div className="eyebrow">FARM MANAGEMENT</div>
              <h1>Good to see you, {user?.full_name?.split(' ')[0]}.</h1>
              <p className="muted">Here is the current state of the records in your workspace.</p>
            </div>
            <button className="primary" onClick={() => setShowFarmForm(!showFarmForm)}>
              <Plus size={17} /> Add farm
            </button>
          </div>

          {error && <div className="alert error">{error}</div>}
          {notice && <div className="alert success">{notice}</div>}

          {showFarmForm && (
            <section className="panel farm-form-panel">
              <div className="panel-heading">
                <div>
                  <h2>Register a farm</h2>
                  <p>Enter details from a real farm record.</p>
                </div>
                <button className="icon-button" onClick={() => setShowFarmForm(false)}>×</button>
              </div>

              <form onSubmit={createFarm} className="farm-form">
                <label>Farm name<input name="name" required minLength={2} placeholder="e.g. Family farm" /></label>
                <label>Location<input name="location" required minLength={2} placeholder="Village, district, state" /></label>
                <label>Area<input name="area" type="number" min="0.01" step="any" required placeholder="Measured area" /></label>
                <label>
                  Area unit
                  <select name="area_unit">
                    <option value="hectare">Hectare</option>
                    <option value="acre">Acre</option>
                    <option value="bigha">Bigha</option>
                  </select>
                </label>
                <label className="wide">Soil type (optional)<input name="soil_type" placeholder="Only if known" /></label>
                <label>Latitude (optional)<input name="latitude" type="number" min="-90" max="90" step="any" placeholder="e.g. 22.5726" /></label>
                <label>Longitude (optional)<input name="longitude" type="number" min="-180" max="180" step="any" placeholder="e.g. 88.3639" /></label>
                <p className="wide fine-print">Enter the real farm coordinates. Do not use example coordinates for a real farm.</p>
                <div className="wide form-actions">
                  <button type="button" className="secondary" onClick={() => setShowFarmForm(false)}>Cancel</button>
                  <button className="primary" disabled={busy}>{busy ? 'Saving…' : 'Save farm record'}</button>
                </div>
              </form>
            </section>
          )}

          <div className="metric-grid">
            {[
              { label: 'Registered farms', value: summary?.farms, icon: Map, sub: 'Your farm records' },
              { label: 'Fields / plots', value: summary?.fields, icon: Leaf, sub: 'Across your farms' },
              { label: 'Active crop cycles', value: summary?.active_crop_cycles, icon: Sprout, sub: 'Currently recorded' },
              { label: 'Pending tasks', value: summary?.pending_tasks, icon: CalendarDays, sub: 'Awaiting completion' },
            ].map((item) => (
              <article className="metric-card" key={item.label}>
                <div className="metric-top"><span>{item.label}</span><item.icon size={19} /></div>
                <div className="metric-number">{item.value ?? '—'}</div>
                <div className="metric-sub">{item.sub}</div>
              </article>
            ))}
          </div>

          <div className="content-grid">
            <section className="panel" id="farms">
              <div className="panel-heading">
                <div><h2>Your farms</h2><p>Records linked to your account</p></div>
                <button className="subtle-button" onClick={() => setShowFarmForm(true)}>
                  Add farm <ArrowUpRight size={15} />
                </button>
              </div>

              {farms.length === 0 ? (
                <div className="empty-state">
                  <div className="empty-icon"><Sprout size={25} /></div>
                  <h3>No farm records yet</h3>
                  <p>Add a real farm record to begin. Dashboard totals update from saved data.</p>
                  <button className="primary" onClick={() => setShowFarmForm(true)}>
                    <Plus size={16} /> Register first farm
                  </button>
                </div>
              ) : (
                <div className="farm-list">
                  {farms.map((farm) => (
                    <article className="farm-row" key={farm.id}>
                      <div className="farm-symbol"><Sprout size={20} /></div>
                      <div className="farm-details">
                        <strong>{farm.name}</strong>
                        <span>{farm.location}</span>
                        <small>{farm.soil_type || 'Soil type not recorded'}</small>
                      </div>
                      <div className="farm-area">
                        <strong>{farm.area}</strong>
                        <small>{farm.area_unit}</small>
                      </div>
                    </article>
                  ))}
                </div>
              )}
            </section>

            <section className="panel farm-map-panel" id="farm-map">
              <div className="panel-heading">
                <div>
                  <div className="eyebrow">GEOGRAPHIC FARM VIEW</div>
                  <h2>Farm Map</h2>
                  <p>Explore the locations recorded for your farms.</p>
                </div>
                <div className="integration-icon weather">
                  <Map size={21} />
                </div>
              </div>

              <FarmMap
                farms={farms.map((farm) => ({
                  ...farm,
                  latitude: farm.latitude ?? null,
                  longitude: farm.longitude ?? null,
                }))}
                plots={[]}
              />
            </section>

            <section className="panel plant-health-panel" id="crop-health">
              <div className="panel-heading">
                <div>
                  <div className="eyebrow">AI-POWERED CROP ANALYSIS</div>
                  <h2>Plant disease detection</h2>
                  <p>Upload a clear plant-leaf photograph for an AI prediction.</p>
                </div>
                <div className="integration-icon ai">
                  <ScanSearch size={22} />
                </div>
              </div>

              <form className="form-stack" onSubmit={submitPlantPrediction}>
                <label>
                  Plant image
                  <input
                    type="file"
                    accept="image/jpeg,image/png,image/webp,image/bmp"
                    required
                    onChange={(e) => {
                      setPlantImage(e.target.files?.[0] ?? null)
                      setPlantPrediction(null)
                      setPlantError('')
                    }}
                  />
                </label>

                {plantImage && (
                  <p className="muted">
                    Selected: {plantImage.name} (
                    {(plantImage.size / (1024 * 1024)).toFixed(2)} MB)
                  </p>
                )}

                <button
                  className="primary"
                  type="submit"
                  disabled={plantBusy || !plantImage}
                >
                  {plantBusy ? (
                    <>
                      <LoaderCircle className="spin" size={16} />
                      Analyzing image…
                    </>
                  ) : (
                    <>
                      <ScanSearch size={16} />
                      Analyze plant image
                    </>
                  )}
                </button>
              </form>

              {plantError && (
                <div className="alert error" role="alert">
                  {plantError}
                </div>
              )}

              {plantPrediction && (
                <div className="plant-prediction-results" aria-live="polite">
                  <div className="eyebrow">TOP PREDICTION</div>
                  <h3>
                    {plantPrediction.predicted_class
                      .replace(/___/g, ' — ')
                      .replace(/_/g, ' ')}
                  </h3>

                  <p>
                    Model confidence score:{' '}
                    <strong>{plantPrediction.confidence_percent.toFixed(2)}%</strong>
                  </p>

                  <h4>Other likely classes</h4>
                  <div className="plant-prediction-list">
                    {plantPrediction.top_predictions.map((item) => (
                      <div className="plant-prediction-row" key={item.class_name}>
                        <div className="plant-prediction-label">
                          <span>
                            {item.class_name.replace(/___/g, ' — ').replace(/_/g, ' ')}
                          </span>
                          <strong>{item.confidence_percent.toFixed(2)}%</strong>
                        </div>
                        <div className="prediction-track">
                          <div
                            className="prediction-fill"
                            style={{
                              width: `${Math.min(100, Math.max(0, item.confidence_percent))}%`,
                            }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>

                  <p className="muted">
                    {plantPrediction.disclaimer ??
                      'AI predictions are not confirmed diagnoses. Results may differ on real-world farm images.'}
                  </p>
                </div>
              )}
            </section>

            <section className="panel" id="integrations">
              <div className="panel-heading">
                <div><h2>Connected intelligence</h2><p>External data and model status</p></div>
              </div>

              <div className="integration-row">
                <div className="integration-icon weather"><CloudSun size={20} /></div>
                <div className="integration-copy">
                  <strong>Weather provider</strong>
                  <span>{weather ? `Connected · ${weather.provider}` : weatherBusy ? 'Fetching weather…' : 'Open-Meteo integration'}</span>
                </div>
                <a className="subtle-button" href="#weather">View forecast <ArrowUpRight size={15} /></a>
              </div>

              <div className="integration-row">
                <div className="integration-icon ai"><ScanSearch size={20} /></div>
                <div className="integration-copy">
                  <strong>Crop-health model</strong>
                  <span>AI-powered diagnosis available</span>
                </div>
                <span className="pill neutral">Available</span>
              </div>

              <div className="integration-row">
                <div className="integration-icon market"><ArrowUpRight size={20} /></div>
                <div className="integration-copy">
                  <strong>Market prices</strong>
                  <span>Official source integration pending</span>
                </div>
                <span className="pill neutral">Planned</span>
              </div>

              <div className="data-note">
                <ShieldCheck size={17} />
                <span>Only saved records are counted. No sample farms or fabricated live data are displayed.</span>
              </div>
            </section>
          </div>

          <section className="panel weather-panel" id="weather">
            <div className="panel-heading">
              <div>
                <div className="eyebrow">LIVE FARM CONDITIONS</div>
                <h2>Weather forecast</h2>
                <p>Current conditions and the next seven days</p>
              </div>
              <button
                className="icon-button"
                title="Refresh weather"
                aria-label="Refresh weather"
                disabled={weatherBusy || selectedFarmId === ''}
                onClick={() => setWeatherReload((n) => n + 1)}
              >
                {weatherBusy ? <LoaderCircle className="spin" size={20} /> : <RefreshCw size={19} />}
              </button>
            </div>

            <label className="weather-farm-select">
              Select farm
              <select
                value={selectedFarmId}
                onChange={(e) => setSelectedFarmId(e.target.value ? Number(e.target.value) : '')}
              >
                <option value="">Choose a farm</option>
                {farms.map((farm) => (
                  <option key={farm.id} value={farm.id}>
                    {farm.name} — {farm.location}
                  </option>
                ))}
              </select>
            </label>

            {weatherBusy && (
              <div className="weather-message">
                <LoaderCircle className="spin" size={20} />
                Fetching weather data for the selected farm…
              </div>
            )}

            {!weatherBusy && weatherError && (
              <div className="alert error">
                <strong>Weather unavailable</strong>
                <p>{weatherError}</p>
                <p>Check the farm coordinates and backend connection, then try again.</p>
              </div>
            )}

            {!weatherBusy && !weatherError && !weather && (
              <div className="empty-state">
                <CloudSun size={28} />
                <p>Select a farm to load its forecast.</p>
              </div>
            )}

            {!weatherBusy && weather && (
              <>
                <div className="weather-current">
                  <div className="weather-main">
                    <span className="muted">Current temperature · {weather.farm_name}</span>
                    <div className="weather-temperature">
                      {weather.forecast.current.temperature_2m}
                      {weather.forecast.current_units.temperature_2m}
                    </div>
                    <strong>{weatherDescription(weather.forecast.current.weather_code)}</strong>
                    <p className="muted">
                      Feels like {weather.forecast.current.apparent_temperature}
                      {weather.forecast.current_units.apparent_temperature}
                    </p>
                    <p className="muted">Timezone: {weather.forecast.timezone}</p>
                  </div>

                  <div className="weather-stats">
                    <article className="weather-stat">
                      <Droplets size={19} />
                      <span>Humidity</span>
                      <strong>{weather.forecast.current.relative_humidity_2m}%</strong>
                    </article>
                    <article className="weather-stat">
                      <CloudSun size={19} />
                      <span>Rainfall</span>
                      <strong>{weather.forecast.current.precipitation} mm</strong>
                    </article>
                    <article className="weather-stat">
                      <Wind size={19} />
                      <span>Wind speed</span>
                      <strong>{weather.forecast.current.wind_speed_10m} km/h</strong>
                    </article>
                    <article className="weather-stat">
                      <Thermometer size={19} />
                      <span>Weather code</span>
                      <strong>{weather.forecast.current.weather_code}</strong>
                    </article>
                  </div>
                </div>

                <h3 className="forecast-heading">7-day forecast</h3>

                <div className="forecast-grid">
                  {weather.forecast.daily.time.map((date, index) => (
                    <article className="forecast-day" key={date}>
                      <strong>{formatDay(date)}</strong>
                      <span>{weatherDescription(weather.forecast.daily.weather_code[index])}</span>
                      <div className="forecast-temperatures">
                        <strong>{weather.forecast.daily.temperature_2m_max[index]}°</strong>
                        <span>{weather.forecast.daily.temperature_2m_min[index]}°</span>
                      </div>
                      <span>Rain: {weather.forecast.daily.precipitation_sum[index]} mm</span>
                      <span>Rain chance: {weather.forecast.daily.precipitation_probability_max[index]}%</span>
                      <span>ET₀: {weather.forecast.daily.et0_fao_evapotranspiration[index]} mm</span>
                    </article>
                  ))}
                </div>

                <p className="weather-attribution">{weather.attribution}</p>
                <p className="muted">
                  Retrieved: {new Date(weather.fetched_at).toLocaleString()}
                </p>
              </>
            )}
          </section>

          <FarmOperations
            token={token}
            farms={farms.map((farm) => ({
              id: farm.id,
              name: farm.name,
              location: farm.location,
              latitude: farm.latitude ?? null,
              longitude: farm.longitude ?? null,
            }))}
          />

          <FarmModules
            token={token}
            farms={farms.map((farm) => ({
              id: farm.id,
              name: farm.name,
              location: farm.location,
            }))}
          />

          <footer className="footer">
            AgroVision <span>·</span> Data-backed farm management <span>·</span> v0.1.0
          </footer>
        </section>
        )}
      </main>
    </div>
  )
}