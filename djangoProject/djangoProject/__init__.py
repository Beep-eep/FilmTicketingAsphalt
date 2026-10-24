# PyMySQL is a pure-Python MySQL driver (no compiler needed on Mac/Windows).
# It stands in for "MySQLdb", the module Django's MySQL backend imports.
try:
    import pymysql

    pymysql.install_as_MySQLdb()
except ImportError:  # only needed when the database is MySQL
    pass
