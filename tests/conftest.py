import os

# Explicit host names for HTTP integration tests, never production defaults.
os.environ['ALLOWED_HOSTS']='nas.test,testserver,localhost,127.0.0.1'
