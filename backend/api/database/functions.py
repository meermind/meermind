import os
import logging
import hashlib
from pymongo import MongoClient
from bson.binary import Binary
from dotenv import load_dotenv

from api.ai_tools.gptagent import EmbeddingAgent

logger = logging.getLogger(__name__)

# Load config from a .env file:
load_dotenv()
MONGODB_URI = os.environ['MONGODB_URI']

# Replace the following with your MongoDB Atlas connection string
connection_string = MONGODB_URI
client = MongoClient(connection_string)

# Create a database
db_name = "meermind_v01"
db = client[db_name]

# Retrieve the transcript collection
transcript_collection = db["transcript"]
transcript_summary_collection = db["transcript_summary"]
document_hash_id_collection = db['document_hash_id']

def connect():
    # Create a new client and connect to the server
    try:
        client.admin.command('ping')
        logger.debug(f'database pinged')
    except Exception as e:
        print(e)

# Function to generate embeddings
def generate_embeddings(text):
    agent = EmbeddingAgent()
    agent.open_client()

    embeddings = agent.generate_embeddings(text)
    return embeddings#.squeeze().tolist()

# Function to generate document hash ID
def generate_document_hash_id(module_name, file_name, file_ext):
    hash_input = f"{module_name}_{file_name}_{file_ext}".encode('utf-8')
    return hashlib.md5(hash_input).hexdigest()

# Function to insert file data and metadata
def insert_transcript(module_name, file_name, file_ext, file_data):

    document_hash_id = generate_document_hash_id(module_name, file_name, file_ext)
    mapping_filter = {"document_hash_id": document_hash_id}

    # Generate embeddings from file_data
    text_data = file_data.decode('utf-8')  # Assuming file_data is binary text data
    embeddings = generate_embeddings(text_data)

    update_data = {
        "$set": {
            "module_name": module_name,
            "file_name": file_name,
            "file_data": Binary(file_data),
            "embeddings": embeddings
        }
    }
    result = transcript_collection.update_one(mapping_filter, update_data, upsert=True)

    if result.upserted_id:
        print(f"Inserted summary document for file {module_name}:{file_name}{file_ext}")
    else:
        print(f"Updated summary document for file {module_name}:{file_name}{file_ext}")


# Function to insert file data and metadata
def insert_transcript_summary(module_name, file_name, file_ext, json_data):

    document_hash_id = generate_document_hash_id(module_name, file_name, file_ext)
    mapping_filter = {"document_hash_id": document_hash_id}
    update_data = {
        "$set": {
            "module_name": module_name,
            "file_name": file_name,
            "transcript_summary": json_data
        }
    }

    result = transcript_summary_collection.update_one(mapping_filter, update_data, upsert=True)

    if result.upserted_id:
        print(f"Inserted summary document for file {module_name}:{file_name}{file_ext}")
    else:
        print(f"Updated summary document for file {module_name}:{file_name}{file_ext}")

    # Update mapping collection
    mapping_update = {
        "$set": {
            "module_name": module_name,
            "file_name": file_name,
            "file_ext": file_ext
        }
    }
    result = document_hash_id_collection.update_one(mapping_filter, mapping_update, upsert=True)

    if result.upserted_id:
        print(f"Inserted summary document for file {module_name}:{file_name}{file_ext}")
    else:
        print(f"Updated summary document for file {module_name}:{file_name}{file_ext}")

    return document_hash_id

def clean_collection(connection_string, db_name, collection_name):
    # Connect to MongoDB Atlas
    client = MongoClient(connection_string)
    db = client[db_name]
    collection = db[collection_name]

    # Delete all documents in the collection
    result = collection.delete_many({})
    print(f"Deleted {result.deleted_count} documents from the {collection_name} collection.")

def careful_clean_collections():
    """
    Helper function to clean collections in the database.
    Careful: This function will delete all documents in the collections.
    """
    # # # Clean Collections
    # # clean_collection(connection_string, db_name, "transcript")
    # # clean_collection(connection_string, db_name, "transcript_summary")
    pass

def careful_delete_collections():
    """
    Helper function to delete collections in the database.
    Careful: This function will delete the collections.
    """
    # # # # # Delete Collections
    # transcript_collection.drop()
    # print("Transcript collection dropped")

    # transcript_summary_collection.drop()
    # print("Transcript summary collection dropped")

    # document_hash_id_collection.drop()
    # print("Mapping collection dropped")
    pass

def get_transcript(hash):
    result = transcript_collection.find({"document_hash_id":hash}, {'_id': 0})
    return result

def get_all_summaries():
    results = transcript_summary_collection.find({}, {'_id': 0})
    return list(results)

def get_summary(hash):
    result = transcript_summary_collection.find_one({"document_hash_id":hash},{'_id': 0})
    return result

def update_summary(hash, new_data):
    result = transcript_summary_collection.update_one(
        {"document_hash_id": hash},
        {"$set": new_data}
    )
    return result.modified_count > 0

def delete_summary(hash):
    result = transcript_summary_collection.delete_one({"document_hash_id": hash})
    return result.deleted_count > 0
