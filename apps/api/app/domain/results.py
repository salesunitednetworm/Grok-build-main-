from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# OS-HPXML documents MBtu as one million Btu.
# Electricity: 1 kWh = 3412 Btu → kWh = MBtu * 1e6 / 3412
# Natural gas: 1 therm = 100,000 Btu → therm = MBtu * 10
BTU_PER_KWH = 3412.0
THERM_PER_MBTU = 10.0

ENERGY_TOTAL = "Energy Use: Total (MBtu)"
FUEL_ELEC = "Fuel Use: Electricity: Total (MBtu)"
FUEL_GAS = "Fuel Use: Natural Gas: Total (MBtu)"
FUEL_OIL = "Fuel Use: Fuel Oil: Total (MBtu)"
FUEL_PROPANE = "Fuel Use: Propane: Total (MBtu)"
HEAT_LOAD = "HVAC Design Load: Heating: Total (Btu/h)"
COOL_LOAD = "HVAC Design Load: Cooling Sensible: Total (Btu/h)"


class ParsedAnnual(BaseModel):
    source: str = "openstudio_hpxml_energyplus"
    total_mbtu: float | None = None
    electricity_mbtu: float | None = None
    electricity_kwh: float | None = None
    natural_gas_mbtu: float | None = None
    natural_gas_therm: float | None = None
    fuel_oil_mbtu: float | None = None
    propane_mbtu: float | None = None
    end_uses: dict[str, float] = Field(default_factory=dict)
    heating_design_load_btuh: float | None = None
    cooling_sensible_design_load_btuh: float | None = None
    loads_qualification: str = "preliminary"
    raw_annual: dict[str, Any] = Field(default_factory=dict)


def _flatten(node: Any, prefix: str = "") -> dict[str, float]:
    flat: dict[str, float] = {}
    if isinstance(node, dict):
        for key, value in node.items():
            next_prefix = f"{prefix}: {key}" if prefix else str(key)
            if isinstance(value, dict):
                flat.update(_flatten(value, next_prefix))
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                flat[next_prefix] = float(value)
                flat[str(key)] = float(value)
    return flat


def parse_annual_results(data: dict[str, Any]) -> ParsedAnnual:
    """Map documented OS-HPXML annual keys. Missing keys stay None. Never invents use."""
    flat = _flatten(data)
    # Also accept already-flat documented keys.
    for key, value in data.items():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            flat[key] = float(value)

    def pick(*names: str) -> float | None:
        for name in names:
            if name in flat:
                return flat[name]
        return None

    elec_mbtu = pick(FUEL_ELEC, "Electricity: Total (MBtu)")
    gas_mbtu = pick(FUEL_GAS, "Natural Gas: Total (MBtu)")
    end_uses = {key: value for key, value in flat.items() if key.startswith("End Use:")}
    parsed = ParsedAnnual(
        total_mbtu=pick(ENERGY_TOTAL, "Total (MBtu)"),
        electricity_mbtu=elec_mbtu,
        electricity_kwh=None if elec_mbtu is None else elec_mbtu * 1_000_000.0 / BTU_PER_KWH,
        natural_gas_mbtu=gas_mbtu,
        natural_gas_therm=None if gas_mbtu is None else gas_mbtu * THERM_PER_MBTU,
        fuel_oil_mbtu=pick(FUEL_OIL),
        propane_mbtu=pick(FUEL_PROPANE),
        end_uses=end_uses,
        heating_design_load_btuh=pick(HEAT_LOAD),
        cooling_sensible_design_load_btuh=pick(COOL_LOAD),
        raw_annual=data,
    )
    return parsed
