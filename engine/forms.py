from django import forms
from django.db import models
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Assessment, Topic, Profile


class AssessmentForm(forms.ModelForm):
    # Uncomment for radio buttons.
    #CHOICES = ((True, 'Yes'), (False, 'No'))
    #is_relevant = forms.TypedChoiceField(choices=CHOICES, widget=forms.RadioSelect)

    class Meta:
        model = Assessment
        fields = ['is_relevant', 'topic']


class SignUpForm(UserCreationForm):
    first_name = forms.CharField(max_length=30)
    last_name = forms.CharField(max_length=30)
    email = forms.EmailField(max_length=254)
    institution = forms.CharField(max_length=254)
    topics = forms.ModelMultipleChoiceField(queryset=Topic.objects.all())

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'institution', 'email', 'password1', 'password2', 'topics')


class UserForm(forms.ModelForm):
    first_name = forms.CharField(max_length=30)
    last_name = forms.CharField(max_length=30)

    class Meta:
        model = User
        fields = ('first_name', 'last_name',)


class ProfileForm(forms.ModelForm):
    institution = forms.CharField(max_length=254)
    topics = forms.ModelMultipleChoiceField(queryset=Topic.objects.all())

    class Meta:
        model = Profile
        fields = ('institution', 'topics')
