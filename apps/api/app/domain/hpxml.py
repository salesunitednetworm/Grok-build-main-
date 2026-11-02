from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from app.domain.building import CanonicalBuilding

HPXML_NS = "http://hpxmlonline.com/2025/12"
HPXML_SCHEMA_VERSION = "5.0"
HPXML_SCHEMA_LABEL = "5.0-rc1"
SOFTWARE_NAME = "Grok Build Home Energy"
SOFTWARE_VERSION = "0.1.0"

ET.register_namespace("", HPXML_NS)


def _el(tag: str, parent: ET.Element | None = None, text: object | None = None, **attrs: str) -> ET.Element:
    if parent is None:
        node = ET.Element(f"{{{HPXML_NS}}}{tag}", attrs)
    else:
        node = ET.SubElement(parent, f"{{{HPXML_NS}}}{tag}", attrs)
    if text is not None:
        node.text = str(text)
    return node


def generate_hpxml(model: CanonicalBuilding, building_id: str = "MyBuilding") -> str:
    """Author an HPXML v5.0-rc1 instance for OpenStudio-HPXML 1.12.0."""
    root = _el("HPXML", schemaVersion=HPXML_SCHEMA_VERSION)
    header = _el("XMLTransactionHeaderInformation", root)
    _el("XMLType", header, "HPXML")
    _el("XMLGeneratedBy", header, SOFTWARE_NAME)
    _el("CreatedDateAndTime", header, datetime.now(timezone.utc).replace(microsecond=0).isoformat())
    _el("Transaction", header, "create")

    software = _el("SoftwareInfo", root)
    _el("SoftwareProgramUsed", software, SOFTWARE_NAME)
    _el("SoftwareProgramVersion", software, SOFTWARE_VERSION)
    ext = _el("extension", software)
    scenarios = _el("UtilityBillScenarios", ext)
    scenario = _el("UtilityBillScenario", scenarios)
    _el("Name", scenario, "Default")

    building = _el("Building", root)
    _el("BuildingID", building, id=building_id)
    site = _el("Site", building)
    _el("SiteID", site, id="SiteID")
    address = _el("Address", site)
    _el("StateCode", address, model.site.state_code)
    _el("ZipCode", address, model.site.postal_code)
    status = _el("ProjectStatus", building)
    _el("EventType", status, "proposed workscope")

    details = _el("BuildingDetails", building)
    _summary(details, model)
    _climate(details, model)
    _enclosure(details, model)
    _systems(details, model)
    _appliances(details)
    _lighting(details)
    _misc(details)

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    xml = ET.tostring(root, encoding="unicode", xml_declaration=False)
    return f"<?xml version='1.0' encoding='UTF-8'?>\n{xml}\n"


def _summary(details: ET.Element, model: CanonicalBuilding) -> None:
    summary = _el("BuildingSummary", details)
    site = _el("Site", summary)
    _el("Surroundings", site, "stand-alone")
    _el("VerticalSurroundings", site, "no units above or below")
    _el("AzimuthOfFrontOfHome", site, model.site.azimuth_front)
    fuels = _el("FuelTypesAvailable", site)
    _el("Fuel", fuels, "electricity")
    if model.systems.heating_fuel == "natural gas" or model.systems.dhw_fuel == "natural gas":
        _el("Fuel", fuels, "natural gas")
    construction = _el("BuildingConstruction", summary)
    _el("ResidentialFacilityType", construction, model.construction.facility_type)
    _el("NumberofConditionedFloors", construction, f"{model.construction.stories:.1f}")
    _el("NumberofConditionedFloorsAboveGrade", construction, f"{model.construction.stories_above_grade:.1f}")
    _el("AverageCeilingHeight", construction, f"{model.construction.ceiling_height_ft:.1f}")
    _el("NumberofBedrooms", construction, model.construction.bedrooms)
    _el("NumberofBathrooms", construction, model.construction.bathrooms)
    _el("ConditionedFloorArea", construction, f"{model.construction.conditioned_floor_area_ft2:.1f}")
    _el("ConditionedBuildingVolume", construction, f"{model.conditioned_volume:.1f}")


def _climate(details: ET.Element, model: CanonicalBuilding) -> None:
    climate = _el("ClimateandRiskZones", details)
    iecc = _el("ClimateZoneIECC", climate)
    _el("Year", iecc, model.construction.year_built)
    _el("ClimateZone", iecc, model.site.iecc_zone)
    station = _el("WeatherStation", climate)
    _el("SystemIdentifier", station, id="WeatherStation")
    _el("Name", station, model.site.weather_station)
    ext = _el("extension", station)
    _el("EPWFilePath", ext, f"{model.site.weather_station}.epw")


def _enclosure(details: ET.Element, model: CanonicalBuilding) -> None:
    enc = _el("Enclosure", details)
    air = _el("AirInfiltration", enc)
    measure = _el("AirInfiltrationMeasurement", air)
    _el("SystemIdentifier", measure, id="AirInfiltrationMeasurement1")
    _el("HousePressure", measure, "50.0")
    leakage = _el("BuildingAirLeakage", measure)
    _el("UnitofMeasure", leakage, "ACH")
    _el("AirLeakage", leakage, f"{model.enclosure.ach50:.1f}")

    attics = _el("Attics", enc)
    attic = _el("Attic", attics)
    _el("SystemIdentifier", attic, id="Attic1")
    attic_type = _el("AtticType", attic)
    attic_inner = _el("Attic", attic_type)
    _el("Vented", attic_inner, "false")
    _el("AttachedToRoof", attic, idref="Roof1")
    _el("AttachedToWall", attic, idref="Wall2")
    _el("AttachedToFloor", attic, idref="Floor1")

    foundations = _el("Foundations", enc)
    foundation = _el("Foundation", foundations)
    _el("SystemIdentifier", foundation, id="Foundation1")
    ftype = _el("FoundationType", foundation)
    if model.enclosure.foundation_type == "conditioned_basement":
        basement = _el("Basement", ftype)
        _el("Conditioned", basement, "true")
        _el("AttachedToRimJoist", foundation, idref="RimJoist1")
        _el("AttachedToFoundationWall", foundation, idref="FoundationWall1")
        _el("AttachedToSlab", foundation, idref="Slab1")
        interior_found = "basement - conditioned"
    else:
        _el("SlabOnGrade", ftype)
        _el("AttachedToSlab", foundation, idref="Slab1")
        interior_found = "conditioned space"

    roofs = _el("Roofs", enc)
    roof = _el("Roof", roofs)
    _el("SystemIdentifier", roof, id="Roof1")
    _el("InteriorAdjacentTo", roof, "attic - unvented")
    _el("Area", roof, f"{model.enclosure.roof_area_ft2:.1f}")
    _el("RoofType", roof, "asphalt or fiberglass shingles")
    _el("RoofColor", roof, "light")
    _el("Pitch", roof, "6.0")
    roof_ins = _el("Insulation", roof)
    _el("SystemIdentifier", roof_ins, id="Roof1Insulation")
    _el("AssemblyEffectiveRValue", roof_ins, "2.3")

    if model.enclosure.foundation_type == "conditioned_basement":
        rims = _el("RimJoists", enc)
        rim = _el("RimJoist", rims)
        _el("SystemIdentifier", rim, id="RimJoist1")
        _el("ExteriorAdjacentTo", rim, "outside")
        _el("InteriorAdjacentTo", rim, interior_found)
        _el("Area", rim, "115.6")
        _el("Siding", rim, "wood siding")
        _el("Color", rim, "medium")
        rim_ins = _el("Insulation", rim)
        _el("SystemIdentifier", rim_ins, id="RimJoist1Insulation")
        _el("AssemblyEffectiveRValue", rim_ins, "13.9")

    walls = _el("Walls", enc)
    wall = _el("Wall", walls)
    _el("SystemIdentifier", wall, id="Wall1")
    _el("ExteriorAdjacentTo", wall, "outside")
    _el("InteriorAdjacentTo", wall, "conditioned space")
    wall_type = _el("WallType", wall)
    _el("WoodStud", wall_type)
    _el("Area", wall, f"{model.enclosure.wall_area_ft2:.1f}")
    _el("Siding", wall, "wood siding")
    _el("Color", wall, "medium")
    wall_ins = _el("Insulation", wall)
    _el("SystemIdentifier", wall_ins, id="Wall1Insulation")
    _el("AssemblyEffectiveRValue", wall_ins, f"{model.enclosure.wall_assembly_r:.1f}")

    gable = _el("Wall", walls)
    _el("SystemIdentifier", gable, id="Wall2")
    _el("ExteriorAdjacentTo", gable, "outside")
    _el("InteriorAdjacentTo", gable, "attic - unvented")
    _el("AtticWallType", gable, "gable")
    gable_type = _el("WallType", gable)
    _el("WoodStud", gable_type)
    _el("Area", gable, "225.0")
    _el("Siding", gable, "wood siding")
    _el("Color", gable, "medium")
    gable_ins = _el("Insulation", gable)
    _el("SystemIdentifier", gable_ins, id="GableInsulation")
    _el("AssemblyEffectiveRValue", gable_ins, "4.0")

    if model.enclosure.foundation_type == "conditioned_basement":
        fwalls = _el("FoundationWalls", enc)
        fwall = _el("FoundationWall", fwalls)
        _el("SystemIdentifier", fwall, id="FoundationWall1")
        _el("ExteriorAdjacentTo", fwall, "ground")
        _el("InteriorAdjacentTo", fwall, interior_found)
        _el("Type", fwall, "solid concrete")
        _el("Height", fwall, "8.0")
        _el("Area", fwall, "1200.0")
        _el("DepthBelowGrade", fwall, "7.0")
        fw_ins = _el("Insulation", fwall)
        _el("SystemIdentifier", fw_ins, id="FoundationWall1Insulation")
        layer = _el("Layer", fw_ins)
        _el("InstallationType", layer, "continuous - exterior")
        _el("NominalRValue", layer, "10.0")
        layer2 = _el("Layer", fw_ins)
        _el("InstallationType", layer2, "continuous - interior")
        _el("NominalRValue", layer2, "0.0")

    floors = _el("Floors", enc)
    ceiling = _el("Floor", floors)
    _el("SystemIdentifier", ceiling, id="Floor1")
    _el("ExteriorAdjacentTo", ceiling, "attic - unvented")
    _el("InteriorAdjacentTo", ceiling, "conditioned space")
    _el("FloorOrCeiling", ceiling, "ceiling")
    floor_type = _el("FloorType", ceiling)
    _el("WoodFrame", floor_type)
    _el("Area", ceiling, f"{model.enclosure.ceiling_area_ft2:.1f}")
    ceil_ins = _el("Insulation", ceiling)
    _el("SystemIdentifier", ceil_ins, id="Floor1Insulation")
    _el("AssemblyEffectiveRValue", ceil_ins, f"{model.enclosure.ceiling_assembly_r:.1f}")

    slabs = _el("Slabs", enc)
    slab = _el("Slab", slabs)
    _el("SystemIdentifier", slab, id="Slab1")
    _el("InteriorAdjacentTo", slab, interior_found)
    slab_area = model.enclosure.ceiling_area_ft2
    _el("Area", slab, f"{slab_area:.1f}")
    _el("ExposedPerimeter", slab, "150.0")
    peri = _el("PerimeterInsulation", slab)
    _el("SystemIdentifier", peri, id="Slab1PerimeterInsulation")
    peri_layer = _el("Layer", peri)
    _el("NominalRValue", peri_layer, "0.0")
    _el("InsulationDepth", peri_layer, "0.0")
    under = _el("UnderSlabInsulation", slab)
    _el("SystemIdentifier", under, id="Slab1UnderSlabInsulation")
    under_layer = _el("Layer", under)
    _el("NominalRValue", under_layer, "0.0")
    _el("InsulationWidth", under_layer, "0.0")
    slab_ext = _el("extension", slab)
    _el("CarpetFraction", slab_ext, "0.0")
    _el("CarpetRValue", slab_ext, "0.0")

    windows = _el("Windows", enc)
    for index, (azimuth, area) in enumerate(sorted(model.enclosure.window_area_by_azimuth.items(), key=lambda item: int(item[0])), start=1):
        window = _el("Window", windows)
        _el("SystemIdentifier", window, id=f"Window{index}")
        _el("Area", window, f"{area:.1f}")
        _el("Azimuth", window, str(int(azimuth)))
        _el("UFactor", window, f"{model.enclosure.window_u:.2f}")
        _el("SHGC", window, f"{model.enclosure.window_shgc:.2f}")
        shade = _el("InteriorShading", window)
        _el("SystemIdentifier", shade, id=f"Window{index}InteriorShading")
        _el("Type", shade, "light curtains")
        _el("FractionOperable", window, "0.67")
        _el("AttachedToWall", window, idref="Wall1")

    doors = _el("Doors", enc)
    door = _el("Door", doors)
    _el("SystemIdentifier", door, id="Door1")
    _el("AttachedToWall", door, idref="Wall1")
    _el("Area", door, f"{model.enclosure.door_area_ft2:.1f}")
    _el("Azimuth", door, str(model.site.azimuth_front))
    _el("RValue", door, f"{model.enclosure.door_r:.1f}")


def _systems(details: ET.Element, model: CanonicalBuilding) -> None:
    systems = _el("Systems", details)
    hvac = _el("HVAC", systems)
    plant = _el("HVACPlant", hvac)
    primary = _el("PrimarySystems", plant)
    _el("PrimaryHeatingSystem", primary, idref="HeatingSystem1")
    _el("PrimaryCoolingSystem", primary, idref="CoolingSystem1")

    heating = _el("HeatingSystem", plant)
    _el("SystemIdentifier", heating, id="HeatingSystem1")
    _el("DistributionSystem", heating, idref="HVACDistribution1")
    htype = _el("HeatingSystemType", heating)
    _el("Furnace", htype)
    _el("HeatingSystemFuel", heating, model.systems.heating_fuel)
    eff = _el("AnnualHeatingEfficiency", heating)
    _el("Units", eff, "AFUE")
    _el("Value", eff, f"{model.systems.heating_efficiency_afue:.2f}")
    _el("FractionHeatLoadServed", heating, "1.0")

    cooling = _el("CoolingSystem", plant)
    _el("SystemIdentifier", cooling, id="CoolingSystem1")
    _el("DistributionSystem", cooling, idref="HVACDistribution1")
    _el("CoolingSystemType", cooling, model.systems.cooling_type)
    _el("CoolingSystemFuel", cooling, "electricity")
    _el("CompressorType", cooling, "single stage")
    _el("FractionCoolLoadServed", cooling, "1.0")
    ceff = _el("AnnualCoolingEfficiency", cooling)
    _el("Units", ceff, "SEER2")
    _el("Value", ceff, f"{model.systems.cooling_efficiency_seer2:.1f}")

    control = _el("HVACControl", hvac)
    _el("SystemIdentifier", control, id="HVACControl1")
    _el("SetpointTempHeatingSeason", control, f"{model.systems.heating_setpoint_f:.1f}")
    _el("SetpointTempCoolingSeason", control, f"{model.systems.cooling_setpoint_f:.1f}")

    dist = _el("HVACDistribution", hvac)
    _el("SystemIdentifier", dist, id="HVACDistribution1")
    dtype = _el("DistributionSystemType", dist)
    air = _el("AirDistribution", dtype)
    _el("AirDistributionType", air, "regular velocity")
    for duct_type, cfm in (("supply", "81.0"), ("return", "27.0")):
        leak = _el("DuctLeakageMeasurement", air)
        _el("DuctType", leak, duct_type)
        leakage = _el("DuctLeakage", leak)
        _el("Units", leakage, "CFM25")
        _el("Value", leakage, cfm)
        _el("TotalOrToOutside", leakage, "to outside")
    for idx, (duct_type, r_value, location, fraction) in enumerate(
        (
            ("supply", "4.0", "attic - unvented", "0.75"),
            ("return", "4.0", "attic - unvented", "0.75"),
            ("supply", "0.0", "conditioned space", "0.25"),
            ("return", "0.0", "conditioned space", "0.25"),
        ),
        start=1,
    ):
        ducts = _el("Ducts", air)
        _el("SystemIdentifier", ducts, id=f"Ducts{idx}")
        _el("DuctType", ducts, duct_type)
        _el("DuctInsulationRValue", ducts, r_value)
        _el("DuctLocation", ducts, location)
        _el("FractionDuctArea", ducts, fraction)
    _el("ConditionedFloorAreaServed", dist, f"{model.construction.conditioned_floor_area_ft2:.1f}")

    water = _el("WaterHeating", systems)
    wh = _el("WaterHeatingSystem", water)
    _el("SystemIdentifier", wh, id="WaterHeatingSystem1")
    _el("FuelType", wh, model.systems.dhw_fuel)
    _el("WaterHeaterType", wh, model.systems.dhw_type)
    _el("Location", wh, "conditioned space")
    _el("FractionDHWLoadServed", wh, "1.0")
    _el("UniformEnergyFactor", wh, f"{model.systems.dhw_uef:.2f}")
    hw_dist = _el("HotWaterDistribution", water)
    _el("SystemIdentifier", hw_dist, id="HotWaterDistribution1")
    hw_type = _el("SystemType", hw_dist)
    _el("Standard", hw_type)
    pipe = _el("PipeInsulation", hw_dist)
    _el("PipeRValue", pipe, "0.0")
    for idx, fixture_type in enumerate(("shower head", "faucet"), start=1):
        fixture = _el("WaterFixture", water)
        _el("SystemIdentifier", fixture, id=f"WaterFixture{idx}")
        _el("WaterFixtureType", fixture, fixture_type)
        _el("LowFlow", fixture, "false")


def _appliances(details: ET.Element) -> None:
    appliances = _el("Appliances", details)
    washer = _el("ClothesWasher", appliances)
    _el("SystemIdentifier", washer, id="ClothesWasher1")
    _el("IntegratedModifiedEnergyFactor", washer, "1.21")
    _el("RatedAnnualkWh", washer, "380.0")
    _el("LabelElectricRate", washer, "0.12")
    _el("LabelGasRate", washer, "1.09")
    _el("LabelAnnualGasCost", washer, "27.0")
    _el("LabelUsage", washer, "6.0")
    _el("Capacity", washer, "3.2")
    dryer = _el("ClothesDryer", appliances)
    _el("SystemIdentifier", dryer, id="ClothesDryer1")
    _el("FuelType", dryer, "electricity")
    _el("DryingMethod", dryer, "conventional")
    _el("CombinedEnergyFactor", dryer, "3.73")
    dishwasher = _el("Dishwasher", appliances)
    _el("SystemIdentifier", dishwasher, id="Dishwasher1")
    _el("RatedAnnualkWh", dishwasher, "307.0")
    _el("PlaceSettingCapacity", dishwasher, "12")
    _el("LabelElectricRate", dishwasher, "0.12")
    _el("LabelGasRate", dishwasher, "1.09")
    _el("LabelAnnualGasCost", dishwasher, "22.32")
    _el("LabelUsage", dishwasher, "4.0")
    fridge = _el("Refrigerator", appliances)
    _el("SystemIdentifier", fridge, id="Refrigerator1")
    _el("RatedAnnualkWh", fridge, "650.0")
    range_el = _el("CookingRange", appliances)
    _el("SystemIdentifier", range_el, id="CookingRange1")
    _el("FuelType", range_el, "electricity")
    _el("IsInduction", range_el, "false")
    oven = _el("Oven", appliances)
    _el("SystemIdentifier", oven, id="Oven1")
    _el("IsConvection", oven, "false")


def _lighting(details: ET.Element) -> None:
    lighting = _el("Lighting", details)
    groups = (
        ("1", "interior", "0.4", "CompactFluorescent"),
        ("2", "interior", "0.1", "FluorescentTube"),
        ("3", "interior", "0.25", "LightEmittingDiode"),
        ("4", "exterior", "0.4", "CompactFluorescent"),
        ("5", "exterior", "0.1", "FluorescentTube"),
        ("6", "exterior", "0.25", "LightEmittingDiode"),
    )
    for ident, location, fraction, kind in groups:
        group = _el("LightingGroup", lighting)
        _el("SystemIdentifier", group, id=f"LightingGroup{ident}")
        _el("Location", group, location)
        _el("FractionofUnitsInLocation", group, fraction)
        ltype = _el("LightingType", group)
        _el(kind, ltype)


def _misc(details: ET.Element) -> None:
    misc = _el("MiscLoads", details)
    for ident, kind in (("1", "TV other"), ("2", "other")):
        plug = _el("PlugLoad", misc)
        _el("SystemIdentifier", plug, id=f"PlugLoad{ident}")
        _el("PlugLoadType", plug, kind)


def inspect_hpxml(xml_text: str) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        return [{"code": "xml_parse", "field": "hpxml", "message": str(exc)}]
    tag = root.tag
    if tag != f"{{{HPXML_NS}}}HPXML":
        errors.append(
            {
                "code": "namespace",
                "field": "hpxml",
                "message": f"expected namespace {HPXML_NS}, got {tag}",
            }
        )
    if root.attrib.get("schemaVersion") != HPXML_SCHEMA_VERSION:
        errors.append(
            {
                "code": "schema_version",
                "field": "hpxml.schemaVersion",
                "message": f"expected {HPXML_SCHEMA_VERSION}",
            }
        )
    required = (
        "SoftwareInfo",
        "Building",
    )
    for name in required:
        if root.find(f"{{{HPXML_NS}}}{name}") is None:
            errors.append({"code": "missing", "field": name, "message": f"{name} is required"})
    if "BuildingSummary" not in xml_text or "Enclosure" not in xml_text:
        errors.append({"code": "missing", "field": "BuildingDetails", "message": "summary/enclosure missing"})
    if "<HeatingSystem>" not in xml_text or "<CoolingSystem>" not in xml_text:
        errors.append({"code": "missing", "field": "systems.hvac", "message": "heating and cooling are required"})
    if "<WaterHeatingSystem>" not in xml_text:
        errors.append({"code": "missing", "field": "systems.dhw", "message": "water heating is required"})
    return errors


def ceiling_r_from_xml(xml_text: str) -> float | None:
    root = ET.fromstring(xml_text)
    for floor in root.iter(f"{{{HPXML_NS}}}Floor"):
        floor_or_ceiling = floor.find(f"{{{HPXML_NS}}}FloorOrCeiling")
        if floor_or_ceiling is not None and floor_or_ceiling.text == "ceiling":
            ins = floor.find(f"{{{HPXML_NS}}}Insulation")
            if ins is not None:
                r_el = ins.find(f"{{{HPXML_NS}}}AssemblyEffectiveRValue")
                if r_el is not None and r_el.text:
                    return float(r_el.text)
    return None
