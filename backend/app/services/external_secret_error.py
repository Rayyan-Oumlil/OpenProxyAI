"""The shared base of every "an external secret manager could not give the secret" error."""


class ExternalSecretError(Exception):
    """``str(error)`` is safe to log and to show an admin: it never holds the secret or the manager's response body."""
