import type { MapViewport } from "./NeshanMap";

/** Slightly padded around every approved business coordinate in Behbahan. */
export const BEHBAHAN_BOUNDS = {
  west: 50.17,
  south: 30.55,
  east: 50.33,
  north: 30.73,
};

export const BEHBAHAN_VIEW_BOUNDS: [[number, number], [number, number]] = [
  [BEHBAHAN_BOUNDS.south, BEHBAHAN_BOUNDS.west],
  [BEHBAHAN_BOUNDS.north, BEHBAHAN_BOUNDS.east],
];

export const INITIAL_MAP_VIEWPORT: MapViewport = {
  zoom: 13,
  center: { lat: 30.5959, lng: 50.2417 },
  bbox: BEHBAHAN_BOUNDS,
};
