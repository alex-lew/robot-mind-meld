# Robot Mind Meld
A little game powered by word vectors, live at http://robotmindmeld.com

To run locally, you'll need to download the Conceptnet Numberbatch word vectors. The `create_data_file.py` script in this repo does this for you, and saves a processed version (normalized & containing only English words) to `embeddings.h5`. It's safe to delete `mini.h5`, the full set of word vectors, once the script has finished running!

Python dependencies are:
- numpy
- nltk (used for stemming)
- wordfreq (used for tokenization)
- h5py (saving & reading embeddings from file)
- sanic (web server)

In short:
```
(cd frontend && npm install && npm run build)
pip install -r requirements.txt
python3 create_data_file.py
python3 server.py
```

Then browse to http://0.0.0.0:8000 :-)
