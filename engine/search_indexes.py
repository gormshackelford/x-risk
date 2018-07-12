from haystack import indexes
from .models import Publication, Assessment, User

class PublicationIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.EdgeNgramField(document=True, use_template=True)

    def get_model(self):
        return Publication

    def index_queryset(self, using=Publication):
        """Used when the entire index for model is updated."""
        assessors = ['gorm', 'Sean_o_h', 'carhodes', 'lalitha', 'Haydn', 'Simon', 'david.denkenberger']
        assessors = User.objects.filter(username__in=assessors)
        return self.get_model().objects.distinct().filter(
            assessment__in=Assessment.objects.filter(
                is_relevant=True,
                assessor__in=assessors  # Change to all assessors when we have enough to get average assessments for publications.
            )
        )

    def get_updated_field(self):
        return "updated"
