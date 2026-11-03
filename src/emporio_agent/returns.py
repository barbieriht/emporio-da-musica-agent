from dataclasses import dataclass
from datetime import date, timedelta

from emporio_agent.orders import Order

# reason -> days counted from receipt (manual §4; defect window counted from receipt by decision)
_WINDOW_DAYS = {"arrependimento": 7, "preferencia": 7, "defeito": 30}
_LEGAL_WARRANTY_DAYS = 90


@dataclass(frozen=True)
class ReturnAssessment:
    outcome: str
    deadline: date | None = None
    days_left: int | None = None
    legal_warranty_until: date | None = None  # only for defects
    in_legal_warranty: bool | None = None
    starts_on: date | None = None  # shipped orders: when the window will start (estimated delivery)


def assess_return(order: Order, reason: str, today: date) -> ReturnAssessment:
    if order.status == "cancelled":
        return ReturnAssessment("cancelled")
    if order.status in ("pending", "confirmed"):
        return ReturnAssessment("not_shipped")
    if order.status == "shipped":
        return ReturnAssessment("not_received_yet", starts_on=order.estimated_delivery)
    received = order.estimated_delivery  # no actual delivery date in the data
    deadline = received + timedelta(days=_WINDOW_DAYS[reason])
    days_left = (deadline - today).days
    if days_left >= 0:
        return ReturnAssessment("eligible", deadline, days_left)
    if reason == "defeito":
        warranty_until = received + timedelta(days=_LEGAL_WARRANTY_DAYS)
        return ReturnAssessment("expired", deadline, None, warranty_until, today <= warranty_until)
    return ReturnAssessment("expired", deadline)
