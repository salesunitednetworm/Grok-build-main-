export type AddressDraft = {
  street: string;
  city: string;
  state: string;
  zip: string;
};

/** Example jobs only. Not a geocoder and not a USPS CASS list. */
export const EXAMPLE_ADDRESSES: AddressDraft[] = [
  { street: "12 Pine Street", city: "Denver", state: "CO", zip: "80202" },
  { street: "100 Fayetteville Street", city: "Raleigh", state: "NC", zip: "27601" },
  { street: "1 Peachtree Street", city: "Atlanta", state: "GA", zip: "30301" },
];

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

export function exampleByZip(zip: string): AddressDraft | undefined {
  const digits = zip5(zip);
  return EXAMPLE_ADDRESSES.find((row) => row.zip === digits);
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
