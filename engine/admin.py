from django.contrib import admin
from .models import Topic, Source, SearchString, Search, Publication, Assessment, Profile, AssessmentStatus

admin.site.register(Topic)
admin.site.register(Source)
admin.site.register(SearchString)
admin.site.register(Search)
admin.site.register(Publication)
admin.site.register(Assessment)
admin.site.register(Profile)
admin.site.register(AssessmentStatus)
