from django.urls import path
from .views import BookTrainView, AvailableTrainsView, EditBookingTimeView, CancelBookingView, AvailableServiceView


urlpatterns = [
    path('book-train/', BookTrainView.as_view(), name='book-train'),
    path('available-trains/', AvailableTrainsView.as_view(), name='available-trains'),
    path('edit-booking-time/<int:pk>/', EditBookingTimeView.as_view(), name='edit-booking-time'),
    path('cancel/<int:booking_id>/', CancelBookingView.as_view(), name='cancel-booking'),
    path('available-services/', AvailableServiceView.as_view(), name='available-services'),
]

