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

import pandas as pd
import re
from engine.models import Topic, Publication

# Set the search and topic
topic = Topic.objects.get(topic="existential risk")

# Load a csv file with results from a Scopus search (on the Scopus website, not
# using the API).
csv = "datasets/scopus/Scopus Search 2/2011.csv"
df = pd.read_csv(csv, encoding='utf-8')

df = df.rename(columns={
    'Source title': 'Journal',
    'Page start': 'Page_start',
    'Page end': 'Page_end'
})

# Clean the data (replace Scopus placeholders with '')
df.Authors.replace('[No author name available]', '', inplace=True)
df.Abstract.replace('[No abstract available]', '', inplace=True)
df.DOI = df.DOI.fillna(value='')
df.Abstract = df.Abstract.fillna(value='')
df.Journal = df.Journal.fillna(value='')
df.Volume = df.Volume.fillna(value='')
df.Issue = df.Issue.fillna(value='')
df.Page_start = df.Page_start.fillna(value='')
df.Page_end = df.Page_end.fillna(value='')

# Get data on all publications that are already in the database
publications = Publication.objects.values('title','doi')

for result in df.itertuples():
    doi = result.DOI
    if doi != '':
        # If this doi is already in the database, do not add it.
        if publications.filter(doi__iexact=doi).exists():
            # TODO: Add this topic to the publication with this doi.
            continue

    title = result.Title
    if title != '':
        title = re.sub('<[^<]+?>', '', title)  # Strip html tags from the title.
        # If this title is already in the database, do not add it.
        # TODO: This assumes that titles are unique. Add fuzzy matching.
        if publications.filter(title__iexact=title).exists():
            continue
    else:  # If this publication has no title, do not add it to the database.
        continue

    abstract = result.Abstract
    author_string = result.Authors
    year = result.Year
    journal = result.Journal
    volume = result.Volume
    issue = result.Issue
    if (result.Page_start != '') and (result.Page_end != ''):
        pages = result.Page_start + '-' + result.Page_end
    else:
        pages = ''

    record = Publication(
        title=title,
        abstract=abstract,
        author=author_string,
        year=year,
        journal=journal,
        volume=volume,
        issue=issue,
        pages=pages,
        doi=doi,
    )
    record.save()
    # ManyToManyFields need to be added after the record is saved.
    record.search_topics.add(topic)
