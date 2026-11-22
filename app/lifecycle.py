"""Whether the app is still preparing its database after a start or an update.

The HTTP listener answers at once while startup (which may migrate the database after an update) runs on the
HTTPS listener; until it finishes, data requests get a clear "finishing an update" reply instead of errors.
"""
STARTING = False
