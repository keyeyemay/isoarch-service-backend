from db.base import Base
from db.session import engine
from models import *

print("Dropping all tables...")
Base.metadata.drop_all(bind=engine)
print("Done.")
