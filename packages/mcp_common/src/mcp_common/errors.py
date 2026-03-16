class UpstreamError(RuntimeError):
    pass


class UpstreamAuthError(UpstreamError):
    pass


class UpstreamNotFoundError(UpstreamError):
    pass


class UpstreamValidationError(UpstreamError):
    pass


class UpstreamRateLimitError(UpstreamError):
    pass


class UpstreamServerError(UpstreamError):
    pass
