"""Construcción de instancia via DataPortal → CSVs.

Replica la celda 23 del notebook osemosys_notebook_UPME_OPT_YA_20260220:
carga CSVs generados por data_processing usando DataPortal de Pyomo y crea
la instancia concreta.

Los parámetros comentados usan sus valores default del modelo (model_definition.py).
Orden de uso: data_processing.run_data_processing() → build_instance() → solver.solve_model().
"""

from __future__ import annotations

import logging
import os

from pyomo.environ import AbstractModel, ConcreteModel, DataPortal

logger = logging.getLogger(__name__)


def build_instance(
    model: AbstractModel,
    csv_dir: str,
    *,
    has_storage: bool = False,
    has_udc: bool = True,
) -> ConcreteModel:
    """Carga CSVs via DataPortal y crea instancia concreta.

    Replica la celda 23 del notebook OPT_YA_20260220.
    - model: AbstractModel devuelto por model_definition.create_abstract_model().
    - csv_dir: directorio con los CSVs (sets + parámetros) generados por data_processing.
    - has_storage / has_udc: deben coincidir con los usados al crear el abstract model.
    """
    data = DataPortal()
    p = csv_dir

    def _load_set(filename: str, set_name: str) -> None:
        """Carga un set desde CSV si el archivo existe y no está vacío (salta header)."""
        fpath = os.path.join(p, filename)
        if os.path.exists(fpath):
            with open(fpath, encoding="utf-8") as f:
                f.readline()  # header
                first_data = f.readline().strip()
            if not first_data:
                logger.debug("Skipping empty set CSV: %s", filename)
                return
            data.load(filename=fpath, set=set_name)

    def _load_param(filename: str, param_name: str, index: list[str] | str) -> None:
        """Carga un parámetro desde CSV; index es la lista de conjuntos que indexan el parámetro."""
        fpath = os.path.join(p, filename)
        if os.path.exists(fpath):
            with open(fpath, encoding="utf-8") as f:
                f.readline()  # header
                first_data = f.readline().strip()
            if not first_data:
                logger.debug("Skipping empty param CSV: %s", filename)
                return
            data.load(filename=fpath, param=param_name, index=index)

    # ==========================
    # CARGA DE SETS (orden compatible con el modelo abstracto)
    # ==========================

    _load_set("EMISSION.csv", "EMISSION")
    _load_set("FUEL.csv", "FUEL")
    _load_set("TIMESLICE.csv", "TIMESLICE")
    _load_set("MODE_OF_OPERATION.csv", "MODE_OF_OPERATION")
    _load_set("TECHNOLOGY.csv", "TECHNOLOGY")
    _load_set("YEAR.csv", "YEAR")
    _load_set("REGION.csv", "REGION")

    if has_storage:
        _load_set("STORAGE.csv", "STORAGE")
        _load_set("SEASON.csv", "SEASON")
        _load_set("DAYTYPE.csv", "DAYTYPE")
        _load_set("DAILYTIMEBRACKET.csv", "DAILYTIMEBRACKET")

    # ==========================
    # CARGA DE PARÁMETROS
    # ==========================

    # Globales
    _load_param("YearSplit.csv", "YearSplit", ["TIMESLICE", "YEAR"])
    _load_param("DiscountRate.csv", "DiscountRate", ["REGION"])
    # _load_param("DiscountRateIdv.csv", "DiscountRateIdv", ["REGION", "TECHNOLOGY"])
    # TB-04 (paridad notebook vs app): habilitamos DepreciationMethod para evitar
    # resolver un LP distinto al notebook cuando el escenario provee este parámetro.
    # Si el CSV no existe o está vacío, el modelo usa su default (no debe fallar).
    _load_param("DepreciationMethod.csv", "DepreciationMethod", ["REGION"])
    _load_param("CapacityToActivityUnit.csv", "CapacityToActivityUnit", ["REGION", "TECHNOLOGY"])
    # TB-04 (paridad notebook vs app): este parámetro restringe inversión a unidades discretas.
    # Sin cargarlo, el solver puede encontrar soluciones más “fraccionarias” y baratas que el notebook.
    _load_param(
        "CapacityOfOneTechnologyUnit.csv", "CapacityOfOneTechnologyUnit",
        ["REGION", "TECHNOLOGY", "YEAR"],
    )
    _load_param("OperationalLife.csv", "OperationalLife", ["REGION", "TECHNOLOGY"])

    # Inversión y capacidad
    # TB-04 (paridad notebook vs app): límite superior anual de inversión/capacidad nueva.
    _load_param(
        "TotalAnnualMaxCapacityInvestment.csv", "TotalAnnualMaxCapacityInvestment",
        ["REGION", "TECHNOLOGY", "YEAR"],
    )
    # TB-04 (paridad notebook vs app): límite inferior anual de inversión/capacidad nueva.
    _load_param(
        "TotalAnnualMinCapacityInvestment.csv", "TotalAnnualMinCapacityInvestment",
        ["REGION", "TECHNOLOGY", "YEAR"],
    )
    _load_param(
        "TotalTechnologyAnnualActivityLowerLimit.csv", "TotalTechnologyAnnualActivityLowerLimit",
        ["REGION", "TECHNOLOGY", "YEAR"],
    )
    _load_param(
        "TotalTechnologyAnnualActivityUpperLimit.csv", "TotalTechnologyAnnualActivityUpperLimit",
        ["REGION", "TECHNOLOGY", "YEAR"],
    )
    _load_param(
        "TotalTechnologyModelPeriodActivityLowerLimit.csv",
        "TotalTechnologyModelPeriodActivityLowerLimit", ["REGION", "TECHNOLOGY"],
    )
    _load_param(
        "TotalTechnologyModelPeriodActivityUpperLimit.csv",
        "TotalTechnologyModelPeriodActivityUpperLimit", ["REGION", "TECHNOLOGY"],
    )

    # Performance
    _load_param(
        "CapacityFactor.csv", "CapacityFactor",
        ["REGION", "TECHNOLOGY", "TIMESLICE", "YEAR"],
    )
    _load_param("AvailabilityFactor.csv", "AvailabilityFactor", ["REGION", "TECHNOLOGY", "YEAR"])
    _load_param("ResidualCapacity.csv", "ResidualCapacity", ["REGION", "TECHNOLOGY", "YEAR"])

    # Costos
    _load_param("CapitalCost.csv", "CapitalCost", ["REGION", "TECHNOLOGY", "YEAR"])
    _load_param("FixedCost.csv", "FixedCost", ["REGION", "TECHNOLOGY", "YEAR"])
    _load_param(
        "VariableCost.csv", "VariableCost",
        ["REGION", "TECHNOLOGY", "MODE_OF_OPERATION", "YEAR"],
    )

    # Emisiones
    _load_param(
        "EmissionActivityRatio.csv", "EmissionActivityRatio",
        ["REGION", "TECHNOLOGY", "EMISSION", "MODE_OF_OPERATION", "YEAR"],
    )
    # TB-04 (paridad notebook vs app): penalidad por emisiones (si existe en el escenario).
    _load_param("EmissionsPenalty.csv", "EmissionsPenalty", ["REGION", "EMISSION", "YEAR"])
    _load_param(
        "ModelPeriodEmissionLimit.csv", "ModelPeriodEmissionLimit", ["REGION", "EMISSION"],
    )
    # TB-04 (paridad notebook vs app): emisiones exógenas por periodo y por año.
    _load_param(
        "ModelPeriodExogenousEmission.csv", "ModelPeriodExogenousEmission", ["REGION", "EMISSION"],
    )
    _load_param(
        "AnnualExogenousEmission.csv", "AnnualExogenousEmission",
        ["REGION", "EMISSION", "YEAR"],
    )
    _load_param(
        "AnnualEmissionLimit.csv", "AnnualEmissionLimit", ["REGION", "EMISSION", "YEAR"],
    )

    # Activity ratios
    _load_param(
        "InputActivityRatio.csv", "InputActivityRatio",
        ["REGION", "TECHNOLOGY", "FUEL", "MODE_OF_OPERATION", "YEAR"],
    )
    _load_param(
        "OutputActivityRatio.csv", "OutputActivityRatio",
        ["REGION", "TECHNOLOGY", "FUEL", "MODE_OF_OPERATION", "YEAR"],
    )

    # TB-04 (paridad notebook vs app): Reserve Margin y metas RE.
    _load_param("ReserveMarginTagFuel.csv", "ReserveMarginTagFuel", ["REGION", "FUEL", "YEAR"])
    _load_param("RETagTechnology.csv", "RETagTechnology", ["REGION", "TECHNOLOGY", "YEAR"])
    _load_param("RETagFuel.csv", "RETagFuel", ["REGION", "FUEL", "YEAR"])
    _load_param("REMinProductionTarget.csv", "REMinProductionTarget", ["REGION", "YEAR"])
    _load_param(
        "ReserveMarginTagTechnology.csv", "ReserveMarginTagTechnology",
        ["REGION", "TECHNOLOGY", "YEAR"],
    )
    _load_param("ReserveMargin.csv", "ReserveMargin", ["REGION", "YEAR"])

    # Demandas
    _load_param(
        "AccumulatedAnnualDemand.csv", "AccumulatedAnnualDemand", ["REGION", "FUEL", "YEAR"],
    )
    # TB-04 (paridad notebook vs app): demanda especificada y su perfil por timeslice.
    _load_param(
        "SpecifiedAnnualDemand.csv", "SpecifiedAnnualDemand", ["REGION", "FUEL", "YEAR"],
    )
    _load_param(
        "SpecifiedDemandProfile.csv", "SpecifiedDemandProfile",
        ["REGION", "FUEL", "TIMESLICE", "YEAR"],
    )

    # Capacidad
    _load_param(
        "TotalAnnualMaxCapacity.csv", "TotalAnnualMaxCapacity",
        ["REGION", "TECHNOLOGY", "YEAR"],
    )
    # TB-04 (paridad notebook vs app): capacidad mínima anual requerida.
    _load_param(
        "TotalAnnualMinCapacity.csv", "TotalAnnualMinCapacity",
        ["REGION", "TECHNOLOGY", "YEAR"],
    )

    # MUIO (no cargados en notebook OPT_YA_20260220)
    # _load_param(
    #     "TechnologyActivityByModeUpperLimit.csv", "TechnologyActivityByModeUpperLimit",
    #     ["REGION", "TECHNOLOGY", "MODE_OF_OPERATION", "YEAR"],
    # )
    # _load_param(
    #     "TechnologyActivityByModeLowerLimit.csv", "TechnologyActivityByModeLowerLimit",
    #     ["REGION", "TECHNOLOGY", "MODE_OF_OPERATION", "YEAR"],
    # )
    # _load_param(
    #     "TechnologyActivityIncreaseByModeLimit.csv", "TechnologyActivityIncreaseByModeLimit",
    #     ["REGION", "TECHNOLOGY", "MODE_OF_OPERATION", "YEAR"],
    # )
    # _load_param(
    #     "TechnologyActivityDecreaseByModeLimit.csv", "TechnologyActivityDecreaseByModeLimit",
    #     ["REGION", "TECHNOLOGY", "MODE_OF_OPERATION", "YEAR"],
    # )

    # Disposal / Recovery (no cargados en notebook OPT_YA_20260220)
    # _load_param("DisposalCostPerCapacity.csv", "DisposalCostPerCapacity", ["REGION", "TECHNOLOGY"])
    # _load_param(
    #     "RecoveryValuePerCapacity.csv", "RecoveryValuePerCapacity", ["REGION", "TECHNOLOGY"],
    # )

    # Storage
    if has_storage:
        _load_param("DaySplit.csv", "DaySplit", ["DAILYTIMEBRACKET", "YEAR"])
        _load_param("Conversionls.csv", "Conversionls", ["TIMESLICE", "SEASON"])
        _load_param("Conversionld.csv", "Conversionld", ["TIMESLICE", "DAYTYPE"])
        _load_param("Conversionlh.csv", "Conversionlh", ["TIMESLICE", "DAILYTIMEBRACKET"])
        _load_param("DaysInDayType.csv", "DaysInDayType", ["SEASON", "DAYTYPE", "YEAR"])
        _load_param(
            "TechnologyToStorage.csv", "TechnologyToStorage",
            ["REGION", "TECHNOLOGY", "STORAGE", "MODE_OF_OPERATION"],
        )
        _load_param(
            "TechnologyFromStorage.csv", "TechnologyFromStorage",
            ["REGION", "TECHNOLOGY", "STORAGE", "MODE_OF_OPERATION"],
        )
        _load_param("StorageLevelStart.csv", "StorageLevelStart", ["REGION", "STORAGE"])
        _load_param("StorageMaxChargeRate.csv", "StorageMaxChargeRate", ["REGION", "STORAGE"])
        _load_param(
            "StorageMaxDischargeRate.csv", "StorageMaxDischargeRate", ["REGION", "STORAGE"],
        )
        _load_param("MinStorageCharge.csv", "MinStorageCharge", ["REGION", "STORAGE", "YEAR"])
        _load_param("OperationalLifeStorage.csv", "OperationalLifeStorage", ["REGION", "STORAGE"])
        _load_param(
            "CapitalCostStorage.csv", "CapitalCostStorage", ["REGION", "STORAGE", "YEAR"],
        )
        _load_param(
            "ResidualStorageCapacity.csv", "ResidualStorageCapacity",
            ["REGION", "STORAGE", "YEAR"],
        )

    # UDC
    if has_udc:
        _load_set("UDC.csv", "UDC")
        _load_param(
            "UDCMultiplierTotalCapacity.csv", "UDCMultiplierTotalCapacity",
            ["REGION", "TECHNOLOGY", "UDC", "YEAR"],
        )
        _load_param(
            "UDCMultiplierNewCapacity.csv", "UDCMultiplierNewCapacity",
            ["REGION", "TECHNOLOGY", "UDC", "YEAR"],
        )
        _load_param(
            "UDCMultiplierActivity.csv", "UDCMultiplierActivity",
            ["REGION", "TECHNOLOGY", "UDC", "YEAR"],
        )
        _load_param("UDCConstant.csv", "UDCConstant", ["REGION", "UDC", "YEAR"])
        _load_param("UDCTag.csv", "UDCTag", ["REGION", "UDC"])

    # ==========================
    # CREAR INSTANCIA CONCRETA
    # ==========================
    # create_instance rellena sets y parámetros con los datos del DataPortal;
    # los no cargados usan default del AbstractModel.

    logger.info("Creando instancia del modelo...")
    instance = model.create_instance(data, report_timing=True)
    logger.info("Instancia creada exitosamente")

    return instance
