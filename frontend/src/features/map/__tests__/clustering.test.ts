import { describe, expect, it } from "vitest";

import { INITIAL_MAP_VIEWPORT } from "@/features/map/city";
import {
  buildClusterIndex,
  clusteredFeatures,
  clusterZoomTarget,
  isClusterFeature,
  paddedBounds,
  pointMatchesFilters,
} from "@/features/map/clustering";
import type { MapPoint } from "@/features/map/types";

function point(
  id: string,
  lat: number,
  lng: number,
  category = "retail",
  subcategories: string[] = [],
): MapPoint {
  return {
    id,
    slug: id,
    name: id,
    lat,
    lng,
    address: "بهبهان",
    rating_avg: 4,
    rating_count: 1,
    is_24h: false,
    is_verified: false,
    category: { id: 1, slug: category, name: category, icon: "•" },
    subcategory_slugs: subcategories,
  };
}

describe("map clustering", () => {
  it("returns clusters at city zoom without losing any business", () => {
    const points = [
      point("a", 30.5959, 50.2417),
      point("b", 30.5961, 50.2419),
      point("c", 30.6, 50.25),
      point("d", 30.62, 50.27),
    ];
    const index = buildClusterIndex(points);
    expect(index).not.toBeNull();

    const features = clusteredFeatures(index!, INITIAL_MAP_VIEWPORT);
    const total = features.reduce(
      (sum, feature) => sum + (isClusterFeature(feature) ? feature.properties.point_count : 1),
      0,
    );
    expect(total).toBe(points.length);

    const cluster = features.find(isClusterFeature);
    expect(cluster).toBeDefined();
    if (cluster) {
      expect(index!.getClusterExpansionZoom(cluster.properties.cluster_id)).toBeGreaterThan(
        INITIAL_MAP_VIEWPORT.zoom,
      );
    }
  });

  it("renders individual points once the map is fully zoomed in", () => {
    const index = buildClusterIndex([
      point("a", 30.5959, 50.2417),
      point("b", 30.5961, 50.2419),
    ]);
    const features = clusteredFeatures(index!, { ...INITIAL_MAP_VIEWPORT, zoom: 18 });
    expect(features.every((feature) => !isClusterFeature(feature))).toBe(true);
    expect(features).toHaveLength(2);
  });

  it("treats the radius as screen pixels on a 256 px Leaflet tile", () => {
    // At zoom 14 the world is 256 * 2^14 px wide, so 1 px is 360 / 4194304
    // degrees of longitude. Two points 40 px apart must merge; a third point
    // 140 px from the first (100 px from the second) must stay separate.
    const px = 360 / (256 * 2 ** 14);
    const index = buildClusterIndex([
      point("a", 30.6, 50.24),
      point("b", 30.6, 50.24 + 40 * px),
      point("c", 30.6, 50.24 + 140 * px),
    ]);
    const features = clusteredFeatures(index!, {
      zoom: 14,
      center: { lat: 30.6, lng: 50.24 },
      bbox: { west: 50.23, south: 30.59, east: 50.25, north: 30.61 },
    });

    expect(features).toHaveLength(2);
    expect(features.filter(isClusterFeature)[0]?.properties.point_count).toBe(2);
  });

  it("keeps a point just outside the viewport so edge clusters do not pop", () => {
    const viewport = {
      zoom: 13,
      center: { lat: 30.6, lng: 50.24 },
      bbox: { west: 50.24, south: 30.59, east: 50.25, north: 30.61 },
    };
    const padded = paddedBounds(viewport.bbox);
    expect(padded.west).toBeLessThan(viewport.bbox.west);

    const index = buildClusterIndex([point("edge", 30.6, 50.2386)]);
    expect(clusteredFeatures(index!, viewport)).toHaveLength(1);
  });

  it("computes a forward-only click target for clusters", () => {
    expect(clusterZoomTarget(13, 15)).toBe(15);
    expect(clusterZoomTarget(13.6, 14)).toBe(14);
    // A stale expansion zoom must never zoom the user back out.
    expect(clusterZoomTarget(15.7, 13)).toBe(16);
    expect(clusterZoomTarget(17.8, 18)).toBe(18);
    expect(clusterZoomTarget(18, 18)).toBe(18);
    expect(clusterZoomTarget(12)).toBe(13);
  });

  it("filters by category and subcategory before indexing", () => {
    const shop = point("shop", 30.5959, 50.2417, "retail", ["grocery"]);
    const mechanic = point("mechanic", 30.596, 50.242, "automotive", ["mechanic"]);

    expect(pointMatchesFilters(shop, "", "")).toBe(true);
    expect(pointMatchesFilters(shop, "retail", "")).toBe(true);
    expect(pointMatchesFilters(shop, "", "grocery")).toBe(true);
    expect(pointMatchesFilters(shop, "automotive", "")).toBe(false);
    expect(pointMatchesFilters(mechanic, "", "mechanic")).toBe(true);
    expect(pointMatchesFilters(mechanic, "retail", "")).toBe(false);
  });
});
