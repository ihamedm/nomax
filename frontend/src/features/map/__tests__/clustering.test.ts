import { describe, expect, it } from "vitest";

import { INITIAL_MAP_VIEWPORT } from "@/features/map/city";
import {
  buildClusterIndex,
  clusteredFeatures,
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
      (sum, feature) =>
        sum + ("cluster" in feature.properties ? feature.properties.point_count : 1),
      0,
    );
    expect(total).toBe(points.length);

    const cluster = features.find(
      (feature) => "cluster" in feature.properties && feature.properties.cluster,
    );
    expect(cluster).toBeDefined();
    if (cluster && "cluster" in cluster.properties) {
      expect(
        index!.getClusterExpansionZoom(cluster.properties.cluster_id),
      ).toBeGreaterThan(INITIAL_MAP_VIEWPORT.zoom);
    }
  });

  it("renders individual points once the map is fully zoomed in", () => {
    const index = buildClusterIndex([
      point("a", 30.5959, 50.2417),
      point("b", 30.5961, 50.2419),
    ]);
    const features = clusteredFeatures(index!, { ...INITIAL_MAP_VIEWPORT, zoom: 18 });
    expect(features.every((feature) => !("cluster" in feature.properties))).toBe(true);
    expect(features).toHaveLength(2);
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
