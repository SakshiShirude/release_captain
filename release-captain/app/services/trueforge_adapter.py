class TrueForgeAdapter:
    """Boundary for verified TrueForge integration; no SDK calls are invented here."""

    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled
