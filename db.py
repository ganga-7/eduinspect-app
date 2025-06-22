from pymongo import MongoClient
import certifi

def get_db():
    uri = "mongodb+srv://streamuser:stream123@cluster0.5bcqeej.mongodb.net/inspection_system?retryWrites=true&w=majority&appName=Cluster0"
    client = MongoClient(uri, tls=True, tlsCAFile=certifi.where())
    db = client["inspection_system"]
    return db
