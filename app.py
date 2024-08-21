import os
from flask import Flask, redirect, request, url_for, session, render_template  # Added render_template
from msal import ConfidentialClientApplication
from flask_session import Session
from werkzeug.utils import secure_filename  # Import secure_filename
from azure.storage.blob import BlobServiceClient  # For Blob Storage
from azure.storage.fileshare import ShareFileClient  # For File Shares

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_flask_secret_key'  # Replace with a strong secret key
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

# Azure Entra ID configuration
CLIENT_ID = 'a109f55a-8a1d-466c-8c26-edf30a6e53b6'  # Application (client) ID from Azure Entra ID
CLIENT_SECRET = 'J6k8Q~vTX~rf7fcXuFm4_yt3g3p2-tK_p7PVZawW'  # Client secret from Azure Entra ID
AUTHORITY = "https://login.microsoftonline.com/d504a0d5-4523-48c6-91ef-db88ea60a873"  # Replace with your Azure Entra tenant ID
REDIRECT_PATH = "/getAToken"
SCOPE = ["User.Read"]

# Azure Storage configuration
AZURE_STORAGE_CONNECTION_STRING = 'DefaultEndpointsProtocol=https;AccountName=project3storage;AccountKey=MnUuyr8NzicHlnr9D6lo66meh+Li+Pq3NZfD/9I0jxauMeAQDR8krtluJt4psK7iReB0ANFiF5tH+AStlSnZnA==;EndpointSuffix=core.windows.net'  # Replace with your Azure Storage connection string
AZURE_STORAGE_ACCOUNT_NAME = 'project3storage'  # Replace with your Azure Storage account name
AZURE_STORAGE_ACCOUNT_KEY = 'MnUuyr8NzicHlnr9D6lo66meh+Li+Pq3NZfD/9I0jxauMeAQDR8krtluJt4psK7iReB0ANFiF5tH+AStlSnZnA=='  # Replace with your Azure Storage account key
AZURE_FILE_SHARE_NAME = 'project3-fileshare'  # Replace with your Azure File Share name
AZURE_BLOB_CONTAINER_NAME = 'uploads'  # Replace with your Azure Blob container name

# MSAL Client
msal_client = ConfidentialClientApplication(
    CLIENT_ID, authority=AUTHORITY,
    client_credential=CLIENT_SECRET,
    token_cache=None  # We aren't using a token cache in this example
)

# File upload configuration
UPLOAD_FOLDER = 'uploads'  # Folder to store uploaded files
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}  # Allowed file extensions

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Function to check allowed file extensions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Ensure the uploads folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

@app.route('/')
def index():
    if not session.get("user"):
        return redirect(url_for("login"))
    return f'Hello, {session["user"]["name"]}! <br> <a href="{url_for("input_form")}">Input Data</a> <br> <a href="{url_for("upload_form")}">Upload a File</a>'


@app.route("/login")
def login():
    auth_url = msal_client.get_authorization_request_url(SCOPE, redirect_uri=url_for('authorized', _external=True))
    return redirect(auth_url)

@app.route('/upload')
def upload_form():
    return render_template('upload.html')  # Make sure you have this HTML template

@app.route('/upload_file', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return redirect(request.url)
    file = request.files['file']
    if file.filename == '' or not allowed_file(file.filename):
        return redirect(request.url)
    filename = secure_filename(file.filename)
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

    # Upload file to Azure File Share
    file_client = ShareFileClient.from_connection_string(
        AZURE_STORAGE_CONNECTION_STRING,
        share_name=AZURE_FILE_SHARE_NAME,
        file_path=filename
    )
    
    with open(os.path.join(app.config['UPLOAD_FOLDER'], filename), "rb") as data:
        file_client.upload_file(data)

    # Upload file to Azure Blob Storage
    blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
    blob_client = blob_service_client.get_blob_client(container=AZURE_BLOB_CONTAINER_NAME, blob=filename)
    
    with open(os.path.join(app.config['UPLOAD_FOLDER'], filename), "rb") as data:
        blob_client.upload_blob(data)

    return f'''
        File {filename} uploaded successfully! <br>
        <a href="{url_for('logout')}">Logout</a>  <!-- Logout link -->
    '''


@app.route(REDIRECT_PATH)
def authorized():
    code = request.args.get('code')
    result = msal_client.acquire_token_by_authorization_code(
        code,
        scopes=SCOPE,
        redirect_uri=url_for('authorized', _external=True)
    )
    if "error" in result:
        return f"Login failed: {result['error']}"
    session["user"] = result.get("id_token_claims")
    return redirect(url_for("index"))

@app.route('/input_form')
def input_form():
    return render_template('input_form.html')

@app.route('/submit_data', methods=['POST'])
def submit_data():
    title = request.form['title']
    description = request.form['description']
    
    if 'file' not in request.files:
        return redirect(request.url)
    
    file = request.files['file']
    if file.filename == '' or not allowed_file(file.filename):
        return redirect(request.url)

    filename = secure_filename(file.filename)
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    
    # Upload file to Azure File Share
    file_client = ShareFileClient.from_connection_string(
        AZURE_STORAGE_CONNECTION_STRING,
        share_name=AZURE_FILE_SHARE_NAME,
        file_path=filename
    )
    
    with open(os.path.join(app.config['UPLOAD_FOLDER'], filename), "rb") as data:
        file_client.upload_file(data)

    # Upload file to Azure Blob Storage
    blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
    blob_client = blob_service_client.get_blob_client(container=AZURE_BLOB_CONTAINER_NAME, blob=filename)
    
    with open(os.path.join(app.config['UPLOAD_FOLDER'], filename), "rb") as data:
        blob_client.upload_blob(data)

    return redirect(url_for('display'))

@app.route('/display')
def display():
    files = os.listdir(app.config['UPLOAD_FOLDER'])
    return render_template('display.html', files=files)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(
        msal_client.get_authorization_request_url(SCOPE, redirect_uri=url_for('index', _external=True))
    )

if __name__ == '__main__':
    app.run(debug=True)
