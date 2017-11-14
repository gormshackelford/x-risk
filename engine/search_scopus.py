# Run this script as a "standalone" script (terminology from the Django
# documentation) that uses the Djano ORM to get data from the database.
# This requires django.setup(), which requires the settings for this project.
# Appending the root directory to the system path also prevents errors when
# importing the models from the app.
if __name__ == '__main__':
    import sys
    import os
    import django
    parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__),
        os.path.pardir))
    sys.path.append(parent_dir)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "xrisk.settings")
    django.setup()

import json
from urllib.parse import quote_plus
from elsapy.elsclient import ElsClient
from elsapy.elssearch import ElsSearch
from engine.models import Topic, Source, SearchString, Search
from log import log


# Load configuration
config_file = os.path.join(parent_dir, "config.json")
with open(config_file, 'r') as f:
    config = json.load(f)

# Initialize client
client = ElsClient(config['apikey'])
client.inst_token = config['insttoken']

# Set the topic for this search
topic = "existential risk"
topic = Topic.objects.get(topic=topic)

# Get the lastest search string for this topic
search_string = SearchString.objects.filter(topic=topic).order_by('-id')[0]

# Get and encode the search strings as a GET request
string_1 = search_string.search_string_for_title_and_abstract
string_1 = 'TITLE-ABS-KEY' + '%28' + quote_plus(string_1) + '%29'

string_2 = search_string.search_string_for_references
string_2 = 'REF' + '%28' + quote_plus(string_2) + '%29'

year = quote_plus('PUBYEAR IS 2017')
#language = quote_plus('(LIMIT-TO (LANGUAGE, "English"))')

encoded_search_string = string_1 + '+OR+' + string_2 + '+AND+' + year

# Initialize doc search object and execute search, retrieving <=25 results if
# get_all=False or <=5000 results if get_all=True.
search = ElsSearch(encoded_search_string, 'scopus')
search.execute(client, get_all=True)

# Save the results as a new record in the Search table
results = search.results
source = Source.objects.get(source='Scopus')
topic = search_string.topic

record = Search(
    topic=topic,
    search_string=search_string,
    source=source,
    results=results,
)
record.save()

event = 'search_scopus.py'
note = 'Scopus was searched for recent publications about {topic}.'.format(topic=topic)
log(event=event, note=note)
