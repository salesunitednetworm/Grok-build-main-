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
    foundation_type: string;
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
    cooling_type: string;
    cooling_efficiency_seer2: number;
    dhw_type: string;
    dhw_fuel: string;
    dhw_uef: number;
    heating_setpoint_f: number;
    cooling_setpoint_f: number;
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
