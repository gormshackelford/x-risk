from django.shortcuts import render, redirect
from django.http import HttpResponseRedirect
from django.core.urlresolvers import reverse
from django.forms import modelformset_factory
from django.db import transaction
from django.contrib import messages
from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib.sites.shortcuts import get_current_site
from django.utils.encoding import force_bytes, force_text
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.template.loader import render_to_string
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from ast import literal_eval
from random import shuffle
from .tokens import account_activation_token
from .models import Topic, Publication, Assessment, AssessmentStatus
from .forms import AssessmentForm, SignUpForm, ProfileForm, UserForm
import config
import json
import urllib


def home(request):
    topics = Topic.objects.all()
    context = {'topics': topics}
    return render(request, 'engine/home.html', context)


def about(request):
    return render(request, 'engine/about.html')


def methods(request):
    return render(request, 'engine/methods.html')


def contact(request):
    return render(request, 'engine/contact.html')


def instructions(request):
    return render(request, 'engine/instructions.html')


@login_required
def your_assessments(request):
    return render(request, 'engine/your_assessments.html')


@login_required
def scoreboard(request):
    scoreboard = []
    assessors = User.objects.distinct().filter(assessment__in=Assessment.objects.all())
    for assessor in assessors:
        publication_count = Publication.objects.distinct().filter(
            assessment__in=Assessment.objects.filter(assessor=assessor)
        ).count()
        scoreboard.append({'first_name': assessor.first_name, 'last_name': assessor.last_name, 'institution': assessor.profile.institution, 'publication_count': publication_count})
    return render(request, 'engine/scoreboard.html', {'scoreboard': scoreboard})


def signup(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():

            ''' Begin reCAPTCHA validation '''

            recaptcha_response = request.POST.get('g-recaptcha-response')
            url = 'https://www.google.com/recaptcha/api/siteverify'
            values = {
                'secret': config.GOOGLE_RECAPTCHA_SECRET_KEY,
                'response': recaptcha_response
            }
            data = urllib.parse.urlencode(values).encode()
            req =  urllib.request.Request(url, data=data)
            response = urllib.request.urlopen(req)
            result = json.loads(response.read().decode())

            ''' End reCAPTCHA validation '''

            if result['success']:
                user = form.save()
                user.refresh_from_db()  # Load the profile instance created by the signal.
                user.profile.institution = form.cleaned_data.get('institution')
                user.profile.topics = form.cleaned_data.get('topics')
                user.is_active = False
                user.save()
                current_site = get_current_site(request)
                subject = 'Existential Risk Research Network'
                message = render_to_string('engine/confirm_email.html', {
                    'user': user,
                    'domain': current_site.domain,
                    'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                    'token': account_activation_token.make_token(user),
                })
                user.email_user(subject, message)
                return redirect('email_sent')
    else:
        form = SignUpForm()
    return render(request, 'engine/signup.html', {'form': form})


def email_sent(request):
    return render(request, 'engine/email_sent.html')


def email_confirmed(request):
    return render(request, 'engine/email_confirmed.html')


def email_not_confirmed(request):
    return render(request, 'engine/email_not_confirmed.html')


def confirm_email(request, uidb64, token):
    try:
        uid = force_text(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and account_activation_token.check_token(user, token):
        user.is_active = True
        user.profile.email_is_confirmed = True
        user.save()
        login(request, user)
        return render(request, 'engine/email_confirmed.html')
    else:
        return render(request, 'engine/email_not_confirmed.html')


@login_required
@transaction.atomic
def profile(request):
    if request.method == 'POST':
        user_form = UserForm(request.POST, instance=request.user)
        profile_form = ProfileForm(request.POST, instance=request.user.profile)
        if user_form.is_valid() and profile_form.is_valid():
            user = user_form.save()
            user.first_name = user_form.cleaned_data.get('first_name')
            user.last_name = user_form.cleaned_data.get('last_name')
            user.profile.institution = profile_form.cleaned_data.get('institution')
            user.profile.topics = profile_form.cleaned_data.get('topics')
            user.save()
            return render(request, 'engine/profile_updated.html')
    else:
        user_form = UserForm(instance=request.user)
        profile_form = ProfileForm(instance=request.user.profile)

    context = {
        'user_form': user_form,
        'profile_form': profile_form
    }

    return render(request, 'engine/profile.html', context)


def topics(request, slug, state='default'):
    """
    This view has alternative states. It displays publications for a topic, but it can display different subsets of these publications:
    (1) [Default] Publications that have been assessed as relevant by any user: this is the publicly-available list of publications on this topic [if user is not authenticated OR if the state variable is not passed to this view (state='default')]
    (2) Publications that have not been assessed by this user [if user is authenticated AND state='unassessed']
    (3) Publications that have been assessed by this user [if user is authenticated AND state='assessed']
    (4) Publications that have been assessed as relevant by this user [if user is authenticated AND state='relevant']
    (5) Publications that have been assessed as irrelevant by this user [if user is authenticated AND state='irrelevant']
    """

    assessor = request.user
    search_topic = Topic.objects.get(slug=slug)

    if request.user.is_authenticated():

        status = get_status(assessor, search_topic)

        next_assessment = status.get('item').next_assessment
        publications_count = status.get('publications_count')
        publications_assessed_count = status.get('publications_assessed_count')
        publications_assessed_percent = status.get('publications_assessed_percent')

        # Publications that this user has assessed as relevant (in contrast to those that any user assessed as relevant, which is the default for this view)
        if (state == 'relevant'):
            publications = Publication.objects.distinct().filter(
                assessment__in=Assessment.objects.filter(
                    topic=search_topic,
                    assessor=assessor,
                    is_relevant=True
                )
            )

        # Publications that this user has assessed as irrelevant
        elif (state == 'irrelevant'):
            publications = Publication.objects.distinct().filter(
                assessment__in=Assessment.objects.filter(
                    topic=search_topic,
                    assessor=assessor,
                    is_relevant=False
                )
            )

        # Publications that this user has assessed as relevant or irrelevant
        elif (state == 'assessed'):
            publications = Publication.objects.distinct().filter(
                assessment__in=Assessment.objects.filter(
                    topic=search_topic,
                    assessor=assessor
                )
            )

        # Publications that this user has not yet assessed
        elif (state == 'unassessed'):
            publications = Publication.objects.distinct().exclude(
                assessment__in=Assessment.objects.filter(
                    topic=search_topic,
                    assessor=assessor
                )
            )

        else:
            publications = Publication.objects.distinct().filter(
                assessment__in=Assessment.objects.filter(
                    topic=search_topic, is_relevant=True
                )
            )

    # If the user is not authenticated, there is only the publicly-available default view.
    else:
        publications = Publication.objects.distinct().filter(
            assessment__in=Assessment.objects.filter(
                topic=search_topic, is_relevant=True
            )
        )

    page = request.GET.get('page', 1)
    paginator = Paginator(publications, 10)
    try:
        publications = paginator.page(page)
    except PageNotAnInteger:
        publications = paginator.page(1)
    except EmptyPage:
        publications = paginator.page(paginator.num_pages)

    if request.user.is_authenticated():
        context = {
            'search_topic': search_topic,
            'publications': publications,
            'publications_count': publications_count,
            'publications_assessed_count': publications_assessed_count,
            'publications_assessed_percent': publications_assessed_percent,
            'next_assessment': next_assessment
        }
    else:
        context = {
            'search_topic': search_topic,
            'publications': publications,
        }

    return render(request, 'engine/topics.html', context)


@login_required
def assessments(request, slug, pk):
    """
    This view displays one publication at a time for a given search topic. The
    user is asked to assess the relevance of this publication to all the
    topics in the Topic model.
    """
    assessor = request.user
    search_topic = Topic.objects.get(slug=slug)  # This topic
    other_topics = Topic.objects.exclude(slug=slug)  # Other topics
    pk = int(pk)

    # The publication that is going to be assessed
    publication = Publication.objects.get(pk=pk)

    # Data for the sidebar (also used after clicking "Save", "Reset", or "Pass" to update next_unassessed_pk in the database)
    status = get_status(assessor, search_topic)

    item = status.get('item')
    assessment_order = literal_eval(item.assessment_order)
    completed_assessments = literal_eval(item.completed_assessments)
    next_assessment = item.next_assessment

    publications_count = status.get('publications_count')
    publications_assessed_count = status.get('publications_assessed_count')
    publications_assessed_percent = status.get('publications_assessed_percent')

    # The next pk and previous pk in assessment_order, to be used for navigation
    previous_pk = assessment_order[assessment_order.index(pk) - 1]
    try:
        next_pk = assessment_order[assessment_order.index(pk) + 1]
    except:
        next_pk = assessment_order[0]

    # If any new topics were added to the Topic model after this publication was assessed, then they will not display correctly, and so we need to know whether or not this publication has been assessed by this user.
    if Assessment.objects.filter(publication=publication, assessor=assessor).exists():
        assessed_topics = Topic.objects.filter(
            assessment__in=Assessment.objects.filter(
                    publication=publication, assessor=assessor
                )
        )
        unassessed_topics = Topic.objects.exclude(
            assessment__in=Assessment.objects.filter(
                    publication=publication, assessor=assessor
                )
        )
        # Initial data for the AssessmentFormSet (one form for each topic)
        initial = [{'topic': topic} for topic in unassessed_topics]
    else:
        initial = [{'topic': topic} for topic in other_topics]

    AssessmentFormSet = modelformset_factory(Assessment, form=AssessmentForm,
        extra=len(initial), max_num=len(other_topics))

    if request.method == 'POST':
        assessment_form = AssessmentForm(request.POST, prefix="search_topic")
        assessment_formset = AssessmentFormSet(request.POST, prefix="other_topics")

        if assessment_form.is_valid() and assessment_formset.is_valid():
            old_assessments = []
            new_assessments = []

            if 'save' in request.POST:

                is_relevant = assessment_form.cleaned_data.get('is_relevant')

                # If this user has already assessed the relevance of this publication to the search_topic, append the pk of the old assessment to the old_assessments list. Assessments in this list will be bulk deleted.
                if Assessment.objects.filter(publication=publication, assessor=assessor, topic=search_topic).exists():
                    old_assessments.append(Assessment.objects.get(
                        assessor=assessor, publication=publication,
                            topic=search_topic).pk)

                # Append a new instance of the Assessment model to the new_assessments list. Assessments in this list will be bulk created.
                new_assessments.append(Assessment(publication=publication,
                                                  is_relevant=is_relevant,
                                                  topic=search_topic,
                                                  assessor=assessor))

                for assessment_form in assessment_formset:
                    is_relevant = assessment_form.cleaned_data.get('is_relevant')
                    topic = assessment_form.cleaned_data.get('topic')

                    # If this user has already assessed the relevance of this publication to this topic, append the pk of the old assessment to the old_assessments list. Assessments in this list will be bulk deleted.
                    if Assessment.objects.filter(assessor=assessor,
                        publication=publication, topic=topic).exists():
                            old_assessments.append(Assessment.objects.get(
                                assessor=assessor, publication=publication,
                                    topic=topic).pk)

                    # Append a new instance of the Assessment model to the new_assessments list. Assessments in this list will be bulk created.
                    new_assessments.append(Assessment(publication=publication,
                                                      is_relevant=is_relevant,
                                                      topic=topic,
                                                      assessor=assessor))

                next_assessment = get_next_assessment(pk, next_pk, assessment_order, completed_assessments)

                # Bulk create the new_assessments and/or bulk delete the old assessments. This is an atomic transaction, so the old_assessments will not be deleted unless the new_assessments are created.
                with transaction.atomic():
                    Assessment.objects.filter(pk__in=old_assessments).delete()
                    Assessment.objects.bulk_create(new_assessments)
                    item.next_assessment = next_assessment
                    if pk not in completed_assessments:
                        completed_assessments.append(pk)
                        item.completed_assessments = completed_assessments
                    item.save()
                return HttpResponseRedirect(reverse('assessments', args=(), kwargs={'slug': search_topic.slug, 'pk': next_assessment}))

            if 'reset' in request.POST:
                with transaction.atomic():
                    Assessment.objects.filter(publication=publication,
                        assessor=assessor).delete()
                    if pk in completed_assessments:
                        completed_assessments.remove(pk)
                        item.completed_assessments = completed_assessments
                        item.save()
                return HttpResponseRedirect(reverse('assessments', args=(), kwargs={'slug': search_topic.slug, 'pk': pk}))

            if 'pass' in request.POST:
                next_assessment = get_next_assessment(pk, next_pk, assessment_order, completed_assessments)
                item.next_assessment = next_assessment
                item.save()
                return HttpResponseRedirect(reverse('assessments', args=(), kwargs={'slug': search_topic.slug, 'pk': next_assessment}))

    else:
        assessment_formset = AssessmentFormSet(initial=initial,
                queryset=Assessment.objects.filter(publication=publication,
                    assessor=assessor).exclude(topic=search_topic), prefix="other_topics")
        if Assessment.objects.filter(publication=publication, assessor=assessor, topic=search_topic).exists():
                assessment = Assessment.objects.get(publication=publication, assessor=assessor, topic=search_topic)
                assessment_form = AssessmentForm(instance=assessment, prefix="search_topic")
        else:
            assessment_form = AssessmentForm(initial={'topic': search_topic}, prefix="search_topic")

    context = {
        'publication': publication,
        'assessment_form': assessment_form,
        'assessment_formset': assessment_formset,
        'next_pk': next_pk,
        'previous_pk': previous_pk,
        'search_topic': search_topic,
        'publications_count': publications_count,
        'publications_assessed_count': publications_assessed_count,
        'publications_assessed_percent': publications_assessed_percent,
        'next_assessment': next_assessment,
    }

    return render(request, 'engine/assessments.html', context)


def get_status(assessor, search_topic):
    """
    The sidebar shows the status of the assessment (number of publications, number of assessments, and the percentage of publications that have been assessed). It has links to the next_assessment, unassessed publications, assessed publications, relevant publications, and irrelevant publications for this user.
    """

    # Publications should be assessed in a random order, but each user should see the same order from session to session. Therefore, a random assessment_order is created for each user (for each topic), and it is saved in the database.

    # If an assessment_order has been created for this user and topic, get it from the database.
    if AssessmentStatus.objects.filter(assessor=assessor, topic=search_topic).exists():
        item = AssessmentStatus.objects.get(assessor=assessor, topic=search_topic)
        assessment_order = literal_eval(item.assessment_order)
        next_assessment = item.next_assessment
        completed_assessments = literal_eval(item.completed_assessments)

        # If new publications have been added to the database, then randomly append their pks to the end of assessment_order.
        publication_count = len(assessment_order)
        new_publication_count = Publication.objects.filter(search_topics=search_topic).count()

        if publication_count < new_publication_count:
            pks = Publication.objects.filter(search_topics=search_topic).values_list('pk', flat=True)
            new_publications = list(pks)
            new_publications = list(set(new_publications) - set(assessment_order))
            shuffle(new_publications)
            assessment_order = assessment_order + new_publications
            item.assessment_order = assessment_order
            item.save()

    # If an assessment_order has not been created for this user and topic, create it and save it in the database.
    else:
        pks = Publication.objects.filter(search_topics=search_topic).values_list('pk', flat=True)
        assessment_order = list(pks)
        shuffle(assessment_order)
        next_assessment = assessment_order[0]
        completed_assessments = []
        item = AssessmentStatus(
            topic=search_topic,
            assessor=assessor,
            assessment_order=assessment_order,
            next_assessment=next_assessment,
            completed_assessments=completed_assessments
        )
        item.save()

    publications_count = len(assessment_order)
    publications_assessed_count = len(completed_assessments)

    if publications_count != 0:
        publications_assessed_percent = int(publications_assessed_count / publications_count * 100)
    else:
        publications_assessed_percent = 100

    status = {
        'item': item,
        'publications_count': publications_count,
        'publications_assessed_count': publications_assessed_count,
        'publications_assessed_percent': publications_assessed_percent
    }

    return(status)


def get_next_assessment(pk, next_pk, assessment_order, completed_assessments):
    next_assessment = next_pk
    for i in assessment_order:
        if next_assessment not in completed_assessments:
            if next_assessment != pk:
                break
        else:
            try:
                next_assessment = assessment_order[assessment_order.index(next_assessment) + 1]
            except:
                next_assessment = assessment_order[0]
    return(next_assessment)
