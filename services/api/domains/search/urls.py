from django.urls import path

from .api import (
    DisplayColorDetailView,
    DisplayColorsView,
    DuplicateCandidatesView,
    DuplicateReviewView,
    LabelAdminDetailView,
    LabelAdminView,
    SuggestionEvaluationView,
    SuggestionFeedbackView,
    SuggestionsView,
    TopicProposalReviewView,
    TopicProposalView,
)

urlpatterns = [
    path("display-colors/", DisplayColorsView.as_view(), name="display-colors"),
    path(
        "display-colors/<str:kind>/<str:key>/",
        DisplayColorDetailView.as_view(),
        name="display-color-detail",
    ),
    path("search/suggestions/", SuggestionsView.as_view(), name="search-suggestions"),
    path("search/feedback/", SuggestionFeedbackView.as_view(), name="search-feedback"),
    path("search/evaluation/", SuggestionEvaluationView.as_view(), name="search-evaluation"),
    path(
        "search/duplicate-candidates/<int:issue_id>/",
        DuplicateCandidatesView.as_view(),
        name="search-duplicate-candidates",
    ),
    path(
        "search/duplicate-reviews/", DuplicateReviewView.as_view(), name="search-duplicate-reviews"
    ),
    path("search/topics/", TopicProposalView.as_view(), name="search-topics"),
    path("search/topics/<int:id>/", TopicProposalReviewView.as_view(), name="search-topic-review"),
    path("search/labels/", LabelAdminView.as_view(), name="search-labels"),
    path("search/labels/<int:id>/", LabelAdminDetailView.as_view(), name="search-label-detail"),
]
