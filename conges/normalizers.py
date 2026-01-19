# conges/normalizers.py
from typing import Optional

class LeaveTypeNormalizer:
    """
    Normalise les valeurs métier de leave_type
    sans dépendre de la DB.
    """

    MAP = {
        # formes DB / UI possibles -> valeur canonique
        "annualleave": "ANNUAL",
        "annual_leave": "ANNUAL",
        "annual": "ANNUAL",

        "sickleave": "SICK",
        "sick_leave": "SICK",
        "sick": "SICK",

        "exceptional": "EXCEPTIONAL",
        "exceptional_leave": "EXCEPTIONAL",

        "unpaid": "UNPAID",
        "unpaid_leave": "UNPAID",
    }

    @classmethod
    def normalize(cls, raw: Optional[str]) -> Optional[str]:
        if not raw:
            return None
        key = raw.strip().lower().replace(" ", "").replace("-", "_")
        return cls.MAP.get(key, raw.upper())
