# coenotur_handschriften
Flask App für die Coenotur Handschriftenbeschreibungen

## Requirements
* Python 3.8+
* ElasticSearch (https://www.elastic.co/guide/en/elasticsearch/reference/current/install-elasticsearch.html)

## Installation
From repository folder on your machine/server type:
```bash
pip install -r requirements.txt
```

## Server Setup
To get the app to run in a production environment, you should create a `.env` file in the repository's root directory and add the following environment variables with appropriate values to it.
```bash
SECRET_KEY=A RANDOMLY PRODUCED SECRET KEY TO SECURE THE WEB FORMS
ELASTICSEARCH_URL=THE URL OF YOUR ELASTICSEARCH SERVER
```
To randomly produce SECRET_KEY, run the following in your terminal:
```bash
python3 -c "import uuid; print(uuid.uuid4().hex)"
```
If you run ElasticSearch locally on the server, then ElasticSearch generally runs at http://localhost:9200 

## Create ElasticSearch Indices
Run the following from the repository's root directory
```bash
python rebuild_elasticsearch_from_xml.py ES_URL
```
Replace `ES_URL` with the URL for your ElasticSearch server. If you are running it locally on the default port (9200) then `ES_URL` can be omitted.

## Start the app
From the repository's root directory run
```bash
flask run
```

If you need guidance on how to set up the app on your production server, see Miguel Grinberg's excellent guide at https://blog.miguelgrinberg.com/post/the-flask-mega-tutorial-part-xvii-deployment-on-linux.
