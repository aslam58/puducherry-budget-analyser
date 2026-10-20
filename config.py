from dataclasses import dataclass

@dataclass(frozen=True)
class Department:
    number: int
    name: str
    sheet_name: str

DEPARTMENTS = [
    Department(1, "Adi Dravidar Welfare", "D01 Adi Dravidar"),
    Department(2, "Administrator", "D02 Administrator"),
    Department(3, "Agriculture & Forest", "D03 Agriculture"),
    Department(4, "Animal Husbandry", "D04 Animal Husbandry"),
    Department(5, "Art and Culture", "D05 Art and Culture"),
    Department(6, "Chief Secretariat", "D06 Chief Secretariat"),
    Department(7, "Civil Supplies", "D07 Civil Supplies"),
    Department(8, "Council of Ministers", "D08 Council of Ministers"),
    Department(9, "Co-operation", "D09 Co-operation"),
    Department(10, "Education", "D10 Education"),
    Department(11, "Elections", "D11 Elections"),
    Department(12, "Electricity", "D12 Electricity"),
    Department(13, "Finance", "D13 Finance"),
    Department(14, "Fisheries", "D14 Fisheries"),
    Department(15, "General Administration", "D15 General Administration"),
    Department(16, "Health", "D16 Health"),
    Department(17, "Home", "D17 Home"),
    Department(18, "Information and Publicity", "D18 Information Publicity"),
    Department(19, "Information Technology", "D19 Information Technology"),
    Department(20, "Industries", "D20 Industries"),
    Department(21, "Labour and Employment", "D21 Labour Employment"),
    Department(22, "Law & Justice", "D22 Law Justice"),
    Department(23, "Legislative Assembly", "D23 Legislative Assembly"),
    Department(24, "Local Administration", "D24 Local Administration"),
    Department(25, "Planning & Statistics", "D25 Planning Statistics"),
    Department(26, "Public Debt & Interest Payments", "D26 Public Debt"),
    Department(27, "Public Works", "D27 Public Works"),
    Department(28, "Revenue & District Administration", "D28 Revenue District"),
    Department(29, "Rural Development", "D29 Rural Development"),
    Department(30, "Science and Technology", "D30 Science Technology"),
    Department(31, "Social Welfare", "D31 Social Welfare"),
    Department(32, "State Taxation", "D32 State Taxation"),
    Department(33, "Stationery and Printing", "D33 Stationery Printing"),
    Department(34, "Tourism", "D34 Tourism"),
    Department(35, "Town and Country Planning", "D35 Town Country Planning"),
    Department(36, "Transport", "D36 Transport"),
    Department(37, "Port", "D37 Port"),
    Department(38, "Women and Child Development", "D38 Women Child Development"),
    Department(39, "Building Programmes", "D39 Building Programmes"),
]

DEPARTMENT_BY_NUMBER = {d.number: d for d in DEPARTMENTS}
DEPARTMENT_BY_NAME = {d.name.lower(): d for d in DEPARTMENTS}

YEARS = ["2024-25 Actual", "2025-26 BE", "2025-26 RE", "2026-27 BE"]

# Source PDFs state that values are in thousands. Conversion to crore:
# ₹1 crore = ₹10,000 thousand.
THOUSANDS_PER_CRORE = 10_000
