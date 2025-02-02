from odmantic import SyncEngine, Model, Field
from pymongo import MongoClient

engine = SyncEngine(client=MongoClient("mongodb://localhost"), database="mcim_backend")

class A(Model):
    user: str = Field(primary_field=True)
    passwd: str
    enabled: bool

engine.save(A(user="joe", passwd="passwd", enabled=True), )

print(engine.find_one(A, A.user == "joe").model_dump())