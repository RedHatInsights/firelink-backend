"""Some helper functions for the adaptor classes"""
from bonfire import bonfire

class AdaptorClassHelpers:
    """Helper functions for the adaptor classes"""  
    def route_guard(self):
        """We run this before routes to ensure that the reservation system is available"""
        if not bonfire.has_ns_operator():
            bonfire._error(bonfire.NO_RESERVATION_SYS)
