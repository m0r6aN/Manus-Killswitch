# This file makes Python treat the directory agents/tools_agent as a package.
# It can also be used for package-level initialization code if needed.

# Example: You could potentially initialize the DB here if running as a module,
# but typically initialization is done via the API startup or a separate script.
# from .db.database import init_db
# init_db() # Careful with when/where this runs