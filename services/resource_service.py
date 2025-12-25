from dataclasses import dataclass
from db import DB

@dataclass
class ResourceItem:
    resource_id: int
    kind: str
    display_name: str
    zone_name: str
    floor_no: int | None
    status_code: str
    capacity: int | None
    is_hotdesk: bool | None

def list_resources(db: DB) -> list[ResourceItem]:
    rows = db.fetchall("""
    SELECT r.ResourceID, r.ResourceKind, r.DisplayName, z.ZoneName, z.FloorNo,
           rs.StatusCode, rm.Capacity, d.IsHotDesk
    FROM dbo.Resources r
    JOIN dbo.Zones z ON z.ZoneID = r.ZoneID
    JOIN dbo.ResourceStatuses rs ON rs.ResourceStatusID = r.ResourceStatusID
    LEFT JOIN dbo.Rooms rm ON rm.ResourceID = r.ResourceID
    LEFT JOIN dbo.Desks d ON d.ResourceID = r.ResourceID
    ORDER BY r.ResourceKind, z.FloorNo, r.DisplayName
    """)
    out = []
    for x in rows:
        out.append(ResourceItem(
            int(x.ResourceID), str(x.ResourceKind), str(x.DisplayName), str(x.ZoneName),
            int(x.FloorNo) if x.FloorNo is not None else None,
            str(x.StatusCode),
            int(x.Capacity) if x.Capacity is not None else None,
            bool(x.IsHotDesk) if x.IsHotDesk is not None else None,
        ))
    return out
