from bonfire import bonfire

class AdaptorClassHelpers:  
    def route_guard(self):
        if not bonfire.has_ns_operator():
            bonfire._error(bonfire.NO_RESERVATION_SYS)