from django.urls import path

from .api import SuggestionFeedbackView, SuggestionsView

urlpatterns = [
    path("search/suggestions/", SuggestionsView.as_view(), name="search-suggestions"),
    path("search/feedback/", SuggestionFeedbackView.as_view(), name="search-feedback"),
]
