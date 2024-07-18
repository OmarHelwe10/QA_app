from flask import  g
from pymongo import MongoClient
from dotenv import load_dotenv
import os
load_dotenv()
uri = os.getenv("MONGODB_URI")
db_name = os.getenv("DB_NAME")
def get_db():
    if "db" not in g:
        client = MongoClient(uri)
        g.db = client[db_name]
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.client.close()