import { create } from "zustand";

import type { Coordinates } from "@/types";

const envLat = Number(import.meta.env.VITE_MAP_CENTER_LAT ?? 30.638);
const envLng = Number(import.meta.env.VITE_MAP_CENTER_LNG ?? 50.838);

export const BEHBAHAN_CENTER: Coordinates = {
  lat: Number.isFinite(envLat) ? envLat : 30.638,
  lng: Number.isFinite(envLng) ? envLng : 50.838,
};

export const DEFAULT_MAP_ZOOM = Number(import.meta.env.VITE_MAP_DEFAULT_ZOOM ?? 13) || 13;

type LocationSource = "default" | "gps";

interface UiState {
  location: Coordinates;
  locationSource: LocationSource;
  locationPromptOpen: boolean;
  /** Search-style pages collapse the app header and bottom nav while scrolling. */
  chromeHidden: boolean;
  setChromeHidden: (hidden: boolean) => void;
  setLocation: (location: Coordinates, source?: LocationSource) => void;
  resetLocation: () => void;
  openLocationPrompt: () => void;
  closeLocationPrompt: () => void;
}

export const useUi = create<UiState>((set) => ({
  location: BEHBAHAN_CENTER,
  locationSource: "default",
  locationPromptOpen: false,
  chromeHidden: false,
  setChromeHidden(hidden) {
    set({ chromeHidden: hidden });
  },
  setLocation(location, source = "gps") {
    set({ location, locationSource: source });
  },
  resetLocation() {
    set({ location: BEHBAHAN_CENTER, locationSource: "default" });
  },
  openLocationPrompt() {
    set({ locationPromptOpen: true });
  },
  closeLocationPrompt() {
    set({ locationPromptOpen: false });
  },
}));
