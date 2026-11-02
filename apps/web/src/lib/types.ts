export type FieldError = { code: string; field: string; message: string };

export type Home = {
  id: string;
  name: string;
  address_line1: string | null;
  city: string | null;
  state_code: string | null;
  postal_code: string | null;
  created_at: string;
};

export type BuildingPayload = {
  schema: string;
  site: {
    state_code: string;
    postal_code: string;
    azimuth_front: number;
    iecc_zone: string;
    weather_station: string;
    official_weather_station?: string | null;
    weather_source?: string;
    weather_epw_available?: boolean;
  };
  construction: {
    facility_type: string;
    conditioned_floor_area_ft2: number;
    stories: number;
    stories_above_grade: number;
    ceiling_height_ft: number;
    bedrooms: number;
    bathrooms: number;
    year_built: number;
  };
  enclosure: {
    ach50: number;
    wall_area_ft2: number;
    wall_assembly_r: number;
    ceiling_area_ft2: number;
    ceiling_assembly_r: number;
    roof_area_ft2: number;
    attic_type?: string;
    foundation_type: string;
    rim_joist_area_ft2?: number;
    rim_joist_assembly_r?: number;
    window_u: number;
    window_shgc: number;
    window_area_by_azimuth: Record<string, number>;
    door_area_ft2: number;
    door_r: number;
  };
  systems: {
    heating_type: string;
    heating_fuel: string;
    heating_efficiency_afue: number;
    heating_efficiency_hspf2?: number;
    cooling_type: string;
    cooling_efficiency_seer2: number;
    dhw_type: string;
    dhw_fuel: string;
    dhw_uef: number;
    heating_setpoint_f: number;
    cooling_setpoint_f: number;
    ductless?: boolean;
    duct_leakage_supply_cfm25?: number;
    duct_leakage_return_cfm25?: number;
  };
  data_source: Record<string, string>;
};

export type BuildingModel = {
  id: string;
  home_id: string;
  version: number;
  role: string;
  status: string;
  payload: BuildingPayload;
  validation_errors: FieldError[] | null;
};

export type HpxmlDoc = {
  id: string;
  schema_version: string;
  namespace: string;
  xml_text: string;
  generated_at: string;
  validation_errors?: FieldError[];
};

export type EnergyResult = {
  source: string;
  total_mbtu: number | null;
  electricity_kwh: number | null;
  natural_gas_therm: number | null;
  end_uses: Record<string, number> | null;
  heating_design_load_btuh: number | null;
  cooling_sensible_design_load_btuh: number | null;
  loads_qualification: string;
  run_log_warnings?: string[] | null;
  software_defaults?: { element: string; value: string; data_source: string }[] | null;
};

export type WeatherStation = {
  zipcode: string;
  city: string;
  state_code: string;
  iecc_zone: string;
  official_station: string;
  official_station_name: string;
  used_station: string;
  weather_source: string;
  epw_available: boolean;
  notes: string;
};

export type Job = {
  id: string;
  status: string;
  job_type: string;
  unavailable_reason: string | null;
  error_message: string | null;
  artifacts: { id: string; kind: string; byte_size: number }[];
  energy_result: EnergyResult | null;
};

export type Scenario = {
  id: string;
  name: string;
  measure_type: string;
  measure_payload: { ceiling_assembly_r?: number };
  comparison: {
    status: string;
    electricity_kwh_delta: number | null;
    natural_gas_therm_delta: number | null;
    total_mbtu_delta: number | null;
    notes: string | null;
  } | null;
  baseline_job: Job | null;
  upgrade_job: Job | null;
};

export type EngineStatus = {
  provider: string;
  display_name: string;
  versions: Record<string, string>;
  available: boolean;
  reason: string | null;
  regulatory: string[];
};

export type UtilityHistory = {
  id: string;
  as_of: string;
  periods: Record<string, unknown>[];
  quality: {
    any_fuel_qualifies: boolean;
    label: string;
    gaps: string[];
    fuels: Record<string, { measured_kwh?: number | null; measured_therm?: number | null; qualifies_for_detailed_path?: boolean }>;
  };
};

export type CalibrationRun = {
  id: string;
  model_label: string;
  qualification: string;
  run_status: string;
  compliance_claim: string;
  residuals: Record<string, unknown>[];
  proposed_adjustments: { field: string; from_value: number; to_value: number; reason: string; permitted: boolean }[];
  applied_adjustments: { field: string; from_value: number; to_value: number }[];
  gaps: string[];
  notes: string;
  adjusted_job: Job | null;
};

export type ProgramPack = {
  pack_id: string;
  pack_version: string;
  state_code: string;
  program: string;
  public_name: string;
  effective_from: string | null;
  this_product_doe_approved: boolean;
  named_modeling_software: string | null;
  sources: { title: string; url: string; retrieved: string; status: string }[];
  unverified: string[];
};

export type ProgramEvaluation = {
  id: string;
  pack_id: string;
  pack_version: string;
  state_code: string;
  program: string;
  public_name: string;
  overall_status: string;
  compliance_claim: string;
  portal_status: string;
  reservation_status: string;
  payment_status: string;
  this_product_doe_approved: boolean;
  named_modeling_software: string | null;
  savings_percent: number | null;
  savings_method: string | null;
  savings_band: string | null;
  rebate_cap_usd: number | null;
  cost_share_percent: number | null;
  checks: { code: string; status: string; field: string; message: string }[];
  sources: { title: string; url: string }[];
  unverified: string[];
  notes: string;
  rule_pack_changed: boolean;
  current_pack_version: string | null;
  created_at: string;
};

export type PackageProposal = {
  id: string;
  name: string;
  measures: string[];
  status: string;
  electricity_kwh_delta: number | null;
  natural_gas_therm_delta: number | null;
  total_mbtu_delta: number | null;
  notes: string | null;
  upgrade_job: Job | null;
};
