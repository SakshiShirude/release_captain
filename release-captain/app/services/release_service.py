from app.models import ReleaseSession, SessionStatus


def approve(session: ReleaseSession) -> ReleaseSession:
    if session.status != SessionStatus.ready_for_approval:
        raise ValueError("Only a release plan waiting for approval can be approved")
    session.status = SessionStatus.approved
    session.audit.append({"action": "approval", "status": "approved", "detail": "Human approval recorded"})
    return session
