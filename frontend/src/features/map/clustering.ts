import Supercluster, { type AnyProps, type ClusterFeature, type PointFeature } from "supercluster";

import type { MapViewport } from "./NeshanMap";
import type { MapPoint } from "./types";

/** Cluster radius in screen pixels; one bubble groups businesses that would overlap. */
export const CLUSTER_RADIUS_PX = 60;
/** Above this zoom every business renders as its own pin. */
export const CLUSTER_MAX_ZOOM = 17;

export type MapFeature = ClusterFeature<AnyProps> | PointFeature<MapPoint>;

export function buildClusterIndex(points: MapPoint[]): Supercluster<MapPoint> | null {
  if (points.length === 0) return null;
  const index = new Supercluster<MapPoint>({
    radius: CLUSTER_RADIUS_PX,
    maxZoom: CLUSTER_MAX_ZOOM,
    minPoints: 2,
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

export function clusteredFeatures(
  index: Supercluster<MapPoint>,
  viewport: MapViewport,
): MapFeature[] {
  return index.getClusters(
    [viewport.bbox.west, viewport.bbox.south, viewport.bbox.east, viewport.bbox.north],
    Math.round(viewport.zoom),
  );
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
