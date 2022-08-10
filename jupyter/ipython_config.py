c = get_config()
c.InteractiveShellApp.exec_lines = [
    "from mate_common.models.cpg_types import *",
    "from mate_query.cpg.models import *",
    "from mate_query.cpg.query import *",
    "from mate_query import db, cfl",
    "db.initialize(\"postgresql://mate@db/mate\")",
]
