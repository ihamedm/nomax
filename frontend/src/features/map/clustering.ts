import Supercluster, { type AnyProps, type ClusterFeature, type PointFeature } from "supercluster";

import type { MapViewport } from "./NeshanMap";
import type { MapPoint } from "./types";

/**
 * Leaflet draws a tile at 256 px. Supercluster defaults to a 512 px extent,
 * which would make every configured radius render at half size on this map and
 * let bubbles overlap. Passing the real tile size keeps the radius a true
 * on-screen pixel distance at every zoom.
 */
const CLUSTER_TILE_SIZE_PX = 256;

/**
 * Cluster radius in screen pixels. It is intentionally larger than the biggest
 * bubble (44 px) so neighbouring bubbles keep a visible gap at every zoom.
 */
export const CLUSTER_RADIUS_PX = 64;
/** Above this zoom every business has its own marker. */
export const CLUSTER_MAX_ZOOM = 17;
/** Deepest zoom the Neshan/Leaflet map supports; used to clamp click-to-expand. */
export const MAP_MAX_ZOOM = 18;

/**
 * Extra area (as a fraction of the viewport) fetched around the visible box.
 * Clusters are positioned at their centroid, so without padding a group whose
 * centroid sits just off-screen would make its members inside the viewport
 * disappear while panning.
 */
const VIEWPORT_PADDING = 0.15;

export type MapFeature = ClusterFeature<AnyProps> | PointFeature<MapPoint>;

export function isClusterFeature(feature: MapFeature): feature is ClusterFeature<AnyProps> {
  return "cluster" in feature.properties && feature.properties.cluster === true;
}

export function buildClusterIndex(points: MapPoint[]): Supercluster<MapPoint> | null {
  if (points.length === 0) return null;
  const index = new Supercluster<MapPoint>({
    radius: CLUSTER_RADIUS_PX,
    maxZoom: CLUSTER_MAX_ZOOM,
    minPoints: 2,
    extent: CLUSTER_TILE_SIZE_PX,
  });
  index.load(
    points.map((point) => ({
      type: "Feature" as const,
      properties: point,
      geometry: {
        type: "Point" as const,
        coordinates: [point.lng, point.lat] as [number, number],
      },
    })),
  );
  return index;
}

/** Grow a bbox by `ratio` on every side, clamped to valid coordinates. */
export function paddedBounds(
  bbox: MapViewport["bbox"],
  ratio = VIEWPORT_PADDING,
): MapViewport["bbox"] {
  const latPad = (bbox.north - bbox.south) * ratio;
  const lngPad = (bbox.east - bbox.west) * ratio;
  return {
    west: Math.max(-180, bbox.west - lngPad),
    south: Math.max(-85, bbox.south - latPad),
    east: Math.min(180, bbox.east + lngPad),
    north: Math.min(85, bbox.north + latPad),
  };
}

export function clusteredFeatures(
  index: Supercluster<MapPoint>,
  viewport: MapViewport,
): MapFeature[] {
  const bbox = paddedBounds(viewport.bbox);
  return index.getClusters(
    [bbox.west, bbox.south, bbox.east, bbox.north],
    // Supercluster itself floors the zoom; being explicit documents that a
    // fractional Leaflet zoom (zoomSnap is 0.25) uses the lower zoom level.
    Math.floor(viewport.zoom),
  );
}

/**
 * Zoom to use after tapping a cluster. Always moves forward at least one
 * level, never zooms back out when the viewport has moved since the marker was
 * rendered, and stops at the map's maximum zoom.
 */
export function clusterZoomTarget(
  currentZoom: number,
  expansionZoom?: number,
  maxZoom = MAP_MAX_ZOOM,
): number {
  const current = Math.max(0, Math.floor(currentZoom));
  const desired = Math.max(expansionZoom ?? current + 1, current + 1);
  return Math.min(Math.round(desired), maxZoom);
}

export function pointMatchesFilters(
  point: MapPoint,
  categorySlug: string,
  subcategorySlug: string,
): boolean {
  if (categorySlug && point.category?.slug !== categorySlug) return false;
  if (subcategorySlug && !(point.subcategory_slugs ?? []).includes(subcategorySlug)) {
    return false;
  }
  return true;
}
