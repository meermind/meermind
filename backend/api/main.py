import os, json
from flask import Flask, flash, request, redirect, url_for, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import logging 

import api.database.functions as db
import api.ai_tools.main as ai
import pandas as pd

logging.basicConfig(
        level=logging.DEBUG, 
        # format='%(asctime)s %(levelname)s %(name)s %(threadName)s : %(message)s'
        )

logger = logging.getLogger(__name__)

load_dotenv()

ALLOWED_EXTENSIONS = set(['txt', 'rsp', 'rtf'])
UPLOAD_FOLDER = os.path.abspath(os.path.join(os.path.dirname(__file__), 'Downloads'))

app = Flask(__name__)
CORS(app,resource={r"/*": {"origins": "http://localhost:3000"}
}, supports_credentials=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 500 * 1000 * 1000  # 500 MB
app.config['CORS_HEADER'] = 'application/json'

# Debug is on
if os.environ.get("DEBUG") is not None:
    logger.debug(f' msg --> DEBUG is set {os.environ.get("DEBUG")}')

@app.route('/', methods=['GET'])
def home():
    return 'Hello, World!'

def allowedFile(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/search_content', methods=['POST', 'GET'])
def searchContent():
    if request.method == 'POST':
        search_term = request.args['search_term']
        # search_term = 'A regression is able to predict future values based on past data'
        # search_term = 'What is an indicator variable? How does it relates to regression?'
        cursor = db.transcript_collection.find({}, {'document_hash_id', 'embeddings'})
        embeddings = [doc for doc in cursor]
        # Create a dataframe from the cursor
        df_embeddings = pd.DataFrame(embeddings)

        # TODO search similar content
        search_results = ai.search_term_in_transcript(df_embeddings, search_term)
        # Filter on similarity threshold
        filtered_results = search_results[search_results['similarities'] > 0.2]
        hash_ids=filtered_results['document_hash_id'].tolist()

        filtered_results[['document_hash_id', 'similarities']]

        top_result_cursor = db.transcript_summary_collection.find(
                {'document_hash_id': {'$in': hash_ids}}, 
                {'_id': 0}
            )
        
        # Get Top Results and sort them by similarity
        top_results = [doc for doc in top_result_cursor]
        top_results = sorted(top_results, key=lambda x: hash_ids.index(x['document_hash_id']))
        return jsonify(top_results)
    else:
        return jsonify({"status": "Search API GET Request Running"})

@app.route('/upload', methods=['POST', 'GET'])
def fileUpload():
    if request.method == 'POST':
        files = request.files.getlist('files')
        module_name = request.args.get("module_name")
        for file in files:
            if file.filename is not None:
                filename = secure_filename(file.filename)

                if allowedFile(filename):
                    name, file_ext = os.path.splitext(filename)
                    # module_name='meermind' # FIX delete this later
                    file_data = file.read()

                    db.insert_transcript(module_name, name, file_ext, file_data)

                    # Start to openai-api service
                    formatted_response = ai.process_transcript(file_data.decode('utf-8'))
                    # For Testing -> To avoid using the API, we can use the following:
                    # formatted_response = '{\n"title": "Fascinating Facts about Meerkats",\n"oneLineSummary": "Discussion of interesting facts about meerkats, including their unique markings, social behavior, and diet.",\n"studentSummary": [\n{\n"summaryTitle": "Interesting Facts about Meerkats",\n"summaryPoints": [\n"The dark markings under their eyes act like sunglasses, allowing them to see in harsh desert light.",\n"Meerkats stand guard to protect the group from predators like eagles and jackals.",\n"They live in social groups called mobs, ranging from five to thirty members.",\n"Meerkats are fiercely territorial and will defend their territory from threats like snakes.",\n"They use their claws to dig burrows and tunnels where they sleep.",\n"Meerkats belong to the Mongoose family and enjoy wrestling as a form of play.",\n"They have a diverse diet, including scorpions, beetles, spiders, lizards, and small rodents."\n]\n}\n],\n"relatedInformation": [],\n"benefits": [],\n"limitations": [],\n"realWorldExample": "",\n"stateOfTheArtResearch": "",\n"references": []\n}'

                    # Might need this to debug JSON formatting issues - There will be some other issues... let's try to document them.
                    try:
                        data = json.loads(formatted_response)
                    except json.JSONDecodeError as e:
                        # formatted_response_clean = formatted_response.replace('\\n', '\n').replace('\\', '')
                        print(f"JSON decoding error: {e.msg} at line {e.lineno} column {e.colno}")
                        print(f"Problematic JSON snippet: {formatted_response[e.pos - 10:e.pos + 10]}. Please try re-uploading the Document.")
                        raise e

                    # save the formatted reponse 
                    hash_id = db.insert_transcript_summary(module_name, name, file_ext, data)
                    print(hash_id)

                else:
                    return jsonify({'message': 'File type not allowed'}), 400

        return jsonify({"id": hash_id, "status": "success"})
    else:
        return jsonify({"status": "Upload API GET Request Running"})


@app.route('/get-notes', methods=['GET'])
def get_summaries():
    # get objects from the mongodb 
    summaries = db.get_all_summaries()

    # send data to frontend
    return jsonify(summaries);

@app.route('/get-transcript/<hash>', methods=['GET'])
def get_transcript(hash):
    # get objects from the mongodb 
    transcript = db.get_transcript(hash)

    # send data to frontend
    return jsonify(transcript);

@app.route('/get-note/<hash>/update', methods=['POST'])
def update_summary(hash):
    if request.method == 'POST':
        # Get new data from the request body
        new_data = request.json
        
        # Update the document in MongoDB
        success = db.update_summary(hash, new_data)
        
        if success:
            return jsonify({"status": "Update successful"}), 200
        else:
            return jsonify({"status": "Update failed or no document found"}), 404
    else:
        return jsonify({"status": "Invalid request method"}), 405


@app.route('/get-note/<hash>/delete', methods=['POST'])
def delete_summary_route(hash):
    if request.method == 'POST':
        success = db.delete_summary(hash)
        if success:
            return jsonify({"status": "delete successful"}), 200
        else:
            return jsonify({"status": "delete failed or no document found"}), 404
    else:
        return jsonify({"status": "Invalid request method"}), 405


@app.route('/get-note/<hash>', methods=['GET'])
def get_summary(hash):
    if request.method == 'GET':
        # get objects from the mongodb 
        logger.debug(f"hash: {hash}");
        result = db.get_summary(hash)

        # send data to frontend
        return jsonify(result), 200 
    else:
        return jsonify({"status":"POST request"}), 200

if __name__ == '__main__':
   app.run(port=5000)
