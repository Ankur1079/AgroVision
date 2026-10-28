import { useEffect, useMemo, useState } from 'react'
import {
  MapContainer,
  Marker,
  Polygon,
  Popup,
  TileLayer,
  useMap,
  useMapEvents,
} from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

type Point = [latitude: number, longitude: number]

type FarmPin = {
  id: number
  name: string
  latitude: number | null
  longitude: number | null
}

type Plot = {
  id: number
  name: string
  latitude: number | null
  longitude: number | null
  boundary_geojson: string | null
}

type FarmMapProps = {
  farms: FarmPin[]
  plots: Plot[]
  onSelectLocation?: (point: Point) => void
  drawing?: boolean
  onBoundary?: (points: Point[]) => void
}

type ClickCaptureProps = {
  enabled: boolean
  onPoint: (point: Point) => void
}

const DEFAULT_CENTER: Point = [20, 0]

const farmMarkerIcon = new L.Icon({
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  iconRetinaUrl:
    'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
})

function hasValidCoordinates<
  T extends { latitude: number | null; longitude: number | null },
>(location: T): location is T & { latitude: number; longitude: number } {
  return (
    typeof location.latitude === 'number' &&
    typeof location.longitude === 'number' &&
    Number.isFinite(location.latitude) &&
    Number.isFinite(location.longitude) &&
    location.latitude >= -90 &&
    location.latitude <= 90 &&
    location.longitude >= -180 &&
    location.longitude <= 180 &&
    !(location.latitude === 0 && location.longitude === 0)
  )
}

function isGeoJsonPosition(
  value: unknown,
): value is [longitude: number, latitude: number] {
  return (
    Array.isArray(value) &&
    value.length === 2 &&
    typeof value[0] === 'number' &&
    typeof value[1] === 'number' &&
    Number.isFinite(value[0]) &&
    Number.isFinite(value[1]) &&
    value[0] >= -180 &&
    value[0] <= 180 &&
    value[1] >= -90 &&
    value[1] <= 90
  )
}

function parsePlotBoundary(boundaryGeoJson: string | null): Point[] {
  if (!boundaryGeoJson) return []

  try {
    const geometry: unknown = JSON.parse(boundaryGeoJson)
    if (
      typeof geometry !== 'object' ||
      geometry === null ||
      !('type' in geometry) ||
      geometry.type !== 'Polygon' ||
      !('coordinates' in geometry) ||
      !Array.isArray(geometry.coordinates) ||
      !Array.isArray(geometry.coordinates[0])
    ) {
      return []
    }

    const ring = geometry.coordinates[0]
    if (!ring.every(isGeoJsonPosition)) return []

    return ring.map(([longitude, latitude]) => [latitude, longitude])
  } catch {
    return []
  }
}

function ClickCapture({ enabled, onPoint }: ClickCaptureProps) {
  useMapEvents({
    click(event) {
      if (enabled) {
        onPoint([event.latlng.lat, event.latlng.lng])
      }
    },
  })

  return null
}

function FitMapToFeatures({ points }: { points: Point[] }) {
  const map = useMap()

  useEffect(() => {
    if (points.length === 0) return

    if (points.length === 1) {
      map.setView(points[0], 15)
      return
    }

    map.fitBounds(L.latLngBounds(points), {
      padding: [32, 32],
      maxZoom: 15,
    })
  }, [map, points])

  return null
}

export default function FarmMap({
  farms,
  plots,
  onSelectLocation,
  drawing = false,
  onBoundary,
}: FarmMapProps) {
  const [boundaryPoints, setBoundaryPoints] = useState<Point[]>([])

  const locatedFarms = useMemo(
    () => farms.filter((farm) => hasValidCoordinates(farm)),
    [farms],
  )

  const plotBoundaries = useMemo(
    () =>
      plots.map((plot) => ({
        plot,
        points: parsePlotBoundary(plot.boundary_geojson),
      })),
    [plots],
  )

  const featurePoints = useMemo(() => {
    const farmPoints = locatedFarms.map(
      (farm) => [farm.latitude, farm.longitude] as Point,
    )
    const plotPoints = plots.flatMap((plot) =>
      hasValidCoordinates(plot)
        ? [[plot.latitude, plot.longitude] as Point]
        : [],
    )
    const boundaryCoordinates = plotBoundaries.flatMap(({ points }) => points)

    return [...farmPoints, ...plotPoints, ...boundaryCoordinates]
  }, [locatedFarms, plotBoundaries, plots])

  const initialCenter = featurePoints[0] ?? DEFAULT_CENTER

  function handleMapPoint(point: Point) {
    if (drawing) {
      setBoundaryPoints((currentPoints) => [...currentPoints, point])
      return
    }

    onSelectLocation?.(point)
  }

  function closeBoundary() {
    if (boundaryPoints.length < 3) return

    const closedBoundary = [...boundaryPoints, boundaryPoints[0]]
    onBoundary?.(closedBoundary)
    setBoundaryPoints([])
  }

  useEffect(() => {
    if (!drawing) setBoundaryPoints([])
  }, [drawing])

  return (
    <div className="farm-map-wrap">
      <div className="map-help">
        <p>
          {drawing
            ? `Boundary drawing: click the map to add corners (${boundaryPoints.length} points).`
            : 'Map pins use saved coordinates. Click the map to select a farm or plot location.'}
        </p>
        {drawing && (
          <button
            type="button"
            className="secondary"
            onClick={closeBoundary}
            disabled={boundaryPoints.length < 3}
          >
            Close boundary
          </button>
        )}
      </div>

      <MapContainer
        center={initialCenter}
        zoom={featurePoints.length > 0 ? 13 : 2}
        scrollWheelZoom
        className="farm-map"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        <ClickCapture
          enabled={Boolean(onSelectLocation) || drawing}
          onPoint={handleMapPoint}
        />
        <FitMapToFeatures points={featurePoints} />

        {locatedFarms.map((farm) => (
          <Marker
            key={`farm-${farm.id}`}
            position={[farm.latitude, farm.longitude]}
            icon={farmMarkerIcon}
          >
            <Popup>
              <strong>{farm.name}</strong>
              <br />
              {farm.latitude.toFixed(6)}, {farm.longitude.toFixed(6)}
            </Popup>
          </Marker>
        ))}

        {plotBoundaries.map(({ plot, points }) =>
          points.length >= 4 ? (
            <Polygon key={`plot-boundary-${plot.id}`} positions={points}>
              <Popup>{plot.name} — saved field boundary</Popup>
            </Polygon>
          ) : hasValidCoordinates(plot) ? (
            <Marker
              key={`plot-${plot.id}`}
              position={[plot.latitude, plot.longitude]}
              icon={farmMarkerIcon}
            >
              <Popup>{plot.name} (boundary not drawn)</Popup>
            </Marker>
          ) : null,
        )}

        {boundaryPoints.length > 0 && (
          <Polygon
            positions={boundaryPoints}
            pathOptions={{ color: '#15803d', dashArray: '5 5' }}
          />
        )}
      </MapContainer>

      <p className="fine-print">
        Map tiles © OpenStreetMap contributors. Coordinates are user-selected;
        verify each marker against the actual property before relying on it.
      </p>
    </div>
  )
}
