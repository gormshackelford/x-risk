from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.text import slugify
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from urllib.parse import quote_plus

class Topic(models.Model):
    topic = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=150, blank=True)

    def save(self, *args, **kwargs):
        self.topic = self.topic.lower()
        self.slug = slugify(self.topic)
        super(Topic, self).save(*args, **kwargs)

    def __str__(self):
        return self.topic

    class Meta:
        ordering = ['topic']


class Source(models.Model):
    source = models.CharField(max_length=254)

    def __str__(self):
        return self.source


class SearchString(models.Model):
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE)
    search_string_for_title_and_abstract = models.TextField()
    search_string_for_references = models.TextField(blank=True)  # Optional
    date_created = models.DateTimeField(default=timezone.now)

    class Meta:
        get_latest_by = 'date_created'

    def __str__(self):
        return 'A search string about \"{topic}\" created on {date}'.format(
            topic=self.topic, date=self.date_created
        )


class Search(models.Model):
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE)
    search_string = models.ForeignKey(SearchString, on_delete=models.CASCADE)
    source = models.ForeignKey(Source, on_delete=models.CASCADE)
    date_searched = models.DateTimeField(default=timezone.now)
    results = models.TextField()

    class Meta:
        get_latest_by = 'date_searched'

    def __str__(self):
        return 'Topic: "{topic}"; Source: {source}; Date: {date}'.format(
            topic=self.topic, date=self.date_searched, source=self.source
        )


class Publication(models.Model):
    title = models.CharField(max_length=510, blank=True)
    abstract = models.TextField(blank=True)
    author = models.TextField(blank=True)
    year = models.CharField(max_length=30, blank=True)
    journal = models.CharField(max_length=254, blank=True)
    volume = models.CharField(max_length=30, blank=True)
    issue = models.CharField(max_length=30, blank=True)
    pages = models.CharField(max_length=30, blank=True)
    doi = models.CharField(max_length=254, blank=True)
    search_topics = models.ManyToManyField(Topic)
    searches = models.ManyToManyField(Search, blank=True)  # blank=True for manual searches uploaded by csv.

    def __str__(self):
        return self.title

    def split_author(self):
        split_author = self.author.split(',')
        author_list = []
        for author in split_author:
            split_name = author.split(' ')
            split_name = list(filter(None, split_name))  # Delete the blanks.
            author_list.append(split_name)
        return author_list

    def split_pages(self):
        return self.pages.split('-')

    @property
    def google_string(self):
        string = quote_plus(self.title)
        string = '%22' + string + '%22'
        return string


class Assessment(models.Model):
    publication = models.ForeignKey(Publication, on_delete=models.CASCADE)
    is_relevant = models.BooleanField()
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE)
    assessor = models.ForeignKey(settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE)

    def __str__(self):
        return '{boolean}: "{publication}" is relevant to "{topic}"'.format(
            boolean=self.is_relevant, publication=self.publication,
            topic=self.topic
        )


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    email_is_confirmed = models.BooleanField(default=False)
    institution = models.CharField(max_length=254, blank=True)
    topics = models.ManyToManyField(Topic, blank=True)

    def __str__(self):
        return 'Profile for username "{username}"'.format(username=self.user.username)


@receiver(post_save, sender=User)
def update_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
    instance.profile.save()


class AssessmentStatus(models.Model):
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE)
    assessor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    assessment_order = models.TextField()
    next_assessment = models.IntegerField(blank=True, null=True)
    completed_assessments = models.TextField(blank=True)

    def __str__(self):
        return 'Progress report for username "{username}" and topic "{topic}"'.format(username=self.assessor.username, topic=self.topic)


class MLModel(models.Model):
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE)
    threshold = models.FloatField()
    accuracy = models.FloatField()
    precision = models.FloatField()
    test_recall = models.FloatField()
    target_recall = models.FloatField()

    def __str__(self):
        return 'Topic: "{topic}"; Precision: {precision}; Recall: {test_recall}'.format(topic=self.topic, precision=self.precision, test_recall=self.test_recall)


class MLPrediction(models.Model):
    publication = models.ForeignKey(Publication, on_delete=models.CASCADE)
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE)
    prediction = models.FloatField()

    def __str__(self):
        return 'Prediction: {prediction}; Topic: "{topic}"; Publication: "{publication}"'.format(prediction=self.prediction, topic=self.topic, publication=self.publication)
