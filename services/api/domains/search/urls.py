from django.urls import path

from .api import SuggestionFeedbackView, SuggestionsView, TopicProposalReviewView, TopicProposalView

urlpatterns = [
    path("search/suggestions/", SuggestionsView.as_view(), name="search-suggestions"),
    path("search/feedback/", SuggestionFeedbackView.as_view(), name="search-feedback"),
    path("search/topics/", TopicProposalView.as_view(), name="search-topics"),
    path("search/topics/<int:id>/", TopicProposalReviewView.as_view(), name="search-topic-review"),
]
