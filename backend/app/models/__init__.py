"""Registro central de modelos ORM del backend."""

from .change_request import ChangeRequest
from .change_request_value import ChangeRequestValue
from .catalog_change_log import CatalogChangeLog
from .dailytimebracket import Dailytimebracket
from .daytype import Daytype
from .emission import Emission
from .fuel import Fuel
from .mode_of_operation import ModeOfOperation
from .osemosys_param_value import OsemosysParamValue
from .osemosys_output_param_value import OsemosysOutputParamValue
from .parameter import Parameter
from .parameter_storage import ParameterStorage
from .parameter_value_audit import ParameterValueAudit
from .parameter_value import ParameterValue
from .region import Region
from .scenario import Scenario
from .scenario_operation_job import ScenarioOperationJob
from .scenario_operation_job_event import ScenarioOperationJobEvent
from .scenario_permission import ScenarioPermission
from .season import Season
from .simulation_benchmark import SimulationBenchmark
from .simulation_job import SimulationJob
from .simulation_job_event import SimulationJobEvent
from .solver import Solver
from .storage_set import StorageSet
from .timeslice import Timeslice
from .technology import Technology
from .udc_set import UdcSet
from .core.document_type import DocumentType
from .core.user import User

__all__ = [
    "Scenario",
    "ScenarioOperationJob",
    "ScenarioOperationJobEvent",
    "Parameter",
    "Region",
    "Technology",
    "Fuel",
    "Emission",
    "Solver",
    "Timeslice",
    "ModeOfOperation",
    "Season",
    "Daytype",
    "Dailytimebracket",
    "StorageSet",
    "UdcSet",
    "OsemosysParamValue",
    "ParameterValue",
    "ParameterValueAudit",
    "ParameterStorage",
    "OsemosysOutputParamValue",
    "ScenarioPermission",
    "ChangeRequest",
    "ChangeRequestValue",
    "CatalogChangeLog",
    "SimulationJob",
    "SimulationJobEvent",
    "SimulationBenchmark",
    "DocumentType",
    "User",
]


# ============================================================================
# Arquitectura y Consideraciones Técnicas
# ============================================================================
#
# Responsabilidad del módulo:
# - Centralizar imports para autodescubrimiento de metadata SQLAlchemy/Alembic.
#
# Posibles mejoras:
# - Separar `__all__` por dominios para mejorar mantenibilidad.
#
# Riesgos en producción:
# - Omisión de imports puede provocar migraciones incompletas.
#
# Escalabilidad:
# - No aplica.
