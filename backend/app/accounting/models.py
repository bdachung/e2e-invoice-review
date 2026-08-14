"""Fixed fictional Northstar general-ledger catalog and suggestion models."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, computed_field


class GeneralLedgerAccountCode(StrEnum):
    CLEANING_SERVICES = "6100"
    REPAIRS_AND_MAINTENANCE = "6200"
    ELECTRICAL_SERVICES = "6210"
    PLUMBING_SERVICES = "6220"
    FACILITIES_SUPPLIES = "6300"
    EQUIPMENT_AND_TOOLS = "6400"
    FUEL_AND_VEHICLE_COSTS = "6500"
    UTILITIES = "6600"
    IT_AND_SOFTWARE = "6700"
    PROFESSIONAL_SERVICES = "6800"


class GeneralLedgerAccount(BaseModel):
    """One selectable Northstar GL account."""

    code: GeneralLedgerAccountCode
    name: str
    description: str


GENERAL_LEDGER_CATALOG: tuple[GeneralLedgerAccount, ...] = (
    GeneralLedgerAccount(
        code=GeneralLedgerAccountCode.CLEANING_SERVICES,
        name="Cleaning services",
        description="Cleaning contractors, janitorial work, and related services.",
    ),
    GeneralLedgerAccount(
        code=GeneralLedgerAccountCode.REPAIRS_AND_MAINTENANCE,
        name="Repairs and maintenance",
        description="General building maintenance, repairs, and servicing.",
    ),
    GeneralLedgerAccount(
        code=GeneralLedgerAccountCode.ELECTRICAL_SERVICES,
        name="Electrical services",
        description="Electrical installation, inspection, repair, and materials.",
    ),
    GeneralLedgerAccount(
        code=GeneralLedgerAccountCode.PLUMBING_SERVICES,
        name="Plumbing services",
        description="Plumbing installation, repair, drainage, and related materials.",
    ),
    GeneralLedgerAccount(
        code=GeneralLedgerAccountCode.FACILITIES_SUPPLIES,
        name="Facilities supplies",
        description="Consumable supplies used to operate and maintain facilities.",
    ),
    GeneralLedgerAccount(
        code=GeneralLedgerAccountCode.EQUIPMENT_AND_TOOLS,
        name="Equipment and tools",
        description="Small equipment, tools, and operational hardware purchases.",
    ),
    GeneralLedgerAccount(
        code=GeneralLedgerAccountCode.FUEL_AND_VEHICLE_COSTS,
        name="Fuel and vehicle costs",
        description="Fuel, vehicle charging, parking, and operating costs.",
    ),
    GeneralLedgerAccount(
        code=GeneralLedgerAccountCode.UTILITIES,
        name="Utilities",
        description="Electricity, gas, water, waste, and other utility services.",
    ),
    GeneralLedgerAccount(
        code=GeneralLedgerAccountCode.IT_AND_SOFTWARE,
        name="IT and software",
        description="Software subscriptions, IT support, and technology services.",
    ),
    GeneralLedgerAccount(
        code=GeneralLedgerAccountCode.PROFESSIONAL_SERVICES,
        name="Professional services",
        description="Legal, consulting, accounting, and other professional advice.",
    ),
)
GENERAL_LEDGER_ACCOUNTS_BY_CODE = {account.code: account for account in GENERAL_LEDGER_CATALOG}


class GeneralLedgerSuggestion(BaseModel):
    """Structured model suggestion constrained to the fixed GL catalog."""

    account_code: GeneralLedgerAccountCode
    rationale: str

    @computed_field
    @property
    def account(self) -> GeneralLedgerAccount:
        return GENERAL_LEDGER_ACCOUNTS_BY_CODE[self.account_code]
