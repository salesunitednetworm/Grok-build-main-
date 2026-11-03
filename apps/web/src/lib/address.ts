export type AddressDraft = {
  street: string;
  city: string;
  state: string;
  zip: string;
};

export function zip5(value: string): string {
  return value.replace(/\D/g, "").slice(0, 5);
}

export function applyZipPlace(
  current: AddressDraft,
  place: { city: string; state_code: string; zipcode: string },
): AddressDraft {
  return {
    ...current,
    city: place.city,
    state: place.state_code,
    zip: place.zipcode,
  };
}

export function applySuggestion(
  current: AddressDraft,
  suggestion: {
    street: string;
    city: string | null;
    state_code: string | null;
    postal_code: string | null;
  },
): AddressDraft {
  return {
    street: suggestion.street || current.street,
    city: suggestion.city || current.city,
    state: suggestion.state_code || current.state,
    zip: suggestion.postal_code || current.zip,
  };
}

export function geocoderLabel(source: string): string {
  if (source === "census") return "US Census Geocoder";
  if (source === "smarty") return "Smarty";
  if (source === "google") return "Google Places";
  if (source === "mapbox") return "Mapbox";
  if (source === "esri") return "Esri World Geocoding Service";
  return "the street geocoder";
}
