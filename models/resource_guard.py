from flask import has_request_context, current_app, request
from sqlalchemy import event, inspect

from extensions import db
from models.user import User
from utils.resource_audit import is_resource_mutation_allowed


def _should_enforce() -> bool:
    if not has_request_context():
        return False
    try:
        if current_app and current_app.config.get("TESTING"):
            return False
    except Exception:
        return True
    return True


@event.listens_for(User, "before_update", propagate=True)
def _guard_user_resources(mapper, connection, target):
    if not _should_enforce():
        return

    state = inspect(target)
    watched = ("money", "bank_balance", "diamonds")
    changed = False
    for field in watched:
        try:
            if state.attrs[field].history.has_changes():
                changed = True
                break
        except Exception:
            continue

    if not changed:
        return

    if is_resource_mutation_allowed():
        return

    endpoint = getattr(request, "endpoint", "") or ""
    if endpoint.startswith("admin."):
        try:
            from flask_login import current_user
            from models.user import UserRole
            if not getattr(current_user, "is_authenticated", False):
                raise RuntimeError("Direct resource mutation blocked: use ResourceService.modify_resources")
            if current_user.role.value < UserRole.MODERATOR.value:
                raise RuntimeError("Direct resource mutation blocked: use ResourceService.modify_resources")

            from models.log import UserLog
            import json

            deltas = {}
            before_state = {}
            after_state = {}
            for field in watched:
                try:
                    hist = state.attrs[field].history
                    if not hist.has_changes():
                        continue
                    old_v = hist.deleted[0] if hist.deleted else None
                    new_v = hist.added[0] if hist.added else getattr(target, field)
                    before_state[field] = old_v
                    after_state[field] = new_v
                    if isinstance(old_v, (int, float)) and isinstance(new_v, (int, float)):
                        diff = int(new_v) - int(old_v)
                        if diff != 0:
                            deltas[field] = diff
                except Exception:
                    continue

            if deltas:
                db.session.add(UserLog(
                    user_id=target.id,
                    action="ADMIN_PANEL_EDIT",
                    details=json.dumps(deltas),
                    result="success",
                    before_state=before_state,
                    after_state=after_state,
                    ip_address=getattr(request, "remote_addr", None),
                    user_agent=getattr(getattr(request, "user_agent", None), "string", None),
                ))
        except Exception:
            raise RuntimeError("Direct resource mutation blocked: use ResourceService.modify_resources")
        return

    raise RuntimeError("Direct resource mutation blocked: use ResourceService.modify_resources")


_resource_guard_enabled = True
