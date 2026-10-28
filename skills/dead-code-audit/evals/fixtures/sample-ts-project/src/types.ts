export interface ActivePayload {
  id: string;
  active: boolean;
}

// Exported but never imported anywhere: a planted unused exported type.
export interface DeprecatedPayload {
  id: string;
  legacy: boolean;
}
