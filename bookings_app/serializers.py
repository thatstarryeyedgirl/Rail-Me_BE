from rest_framework import serializers
from .models import Booking, TRAIN_DURATIONS
from admin_app.models import Train
from django.utils import timezone
from datetime import timedelta
from services_app.models import Service



class BookTrainSerializer(serializers.ModelSerializer):
    train_name = serializers.ChoiceField(choices=[], write_only=True)
    service_type = serializers.ChoiceField(choices=[], required=True, write_only=True)
    departure_time = serializers.DateTimeField()
    seats_booked = serializers.IntegerField()

    class Meta:
        model = Booking
        fields = ['train_name', 'service_type', 'seats_booked', 'price', 'total_price', 'departure_time', 'arrival_time', 'booked_at']
        read_only_fields = ['price', 'total_price', 'arrival_time', 'booked_at']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['train_name'].choices = [(t.train_name, t.train_name) for t in Train.objects.all()]
        self.fields['service_type'].choices = [
            ('reservation', 'Reservation'),
            ('economy', 'Economy'),
            ('business', 'Business'),
        ]

    def validate(self, attrs):
        seats_booked = attrs.get('seats_booked', 0)
        
        if seats_booked <= 0:
            raise serializers.ValidationError("You must book at least one seat.")
        
        train_name = attrs.get('train_name')
        try:
            train = Train.objects.get(train_name=train_name)
        except Train.DoesNotExist:
            raise serializers.ValidationError({"train_name": f"Train '{train_name}' does not exist."})
        
        if train.seats_remaining <= 0:
            raise serializers.ValidationError("No seats available on this train.")
        if seats_booked > train.seats_remaining:
            raise serializers.ValidationError(
                f"Only {train.seats_remaining} seats are available on this train."
                )
        
        service_type = attrs.get('service_type') or 'reservation'
        service = Service.objects.filter(train=train, service_type=service_type).first()
        if not service:
            raise serializers.ValidationError(
                {"service_type": f"No '{service_type}' service available for {train.train_name}."}
                )
        
        departure_time = attrs.get('departure_time')
        if departure_time < timezone.now():
            raise serializers.ValidationError("Departure time cannot be in the past.")
        
        attrs['train'] = train
        attrs['service'] = service
        return attrs


    def create(self, validated_data):
        user = self.context['request'].user
        train = validated_data['train']
        service = validated_data['service']
        seats_booked = validated_data['seats_booked']
        departure_time = validated_data['departure_time']

        # Deduct booked seats
        train.seats_remaining -= seats_booked
        train.save()

        
        duration = TRAIN_DURATIONS.get(train.train_name, 10)
        arrival_time = departure_time + timedelta(hours=duration)
        
        price_per_seat = service.price
        total_price = price_per_seat * seats_booked

        # Create booking record
        booking = Booking.objects.create(
            user=user,
            train=train,
            service=service.service_type.lower(),
            seats_booked=seats_booked,
            departure_time=departure_time,
            arrival_time=arrival_time,
            price=total_price,
        )
        
        return booking


class AvailableTrainSerializer(serializers.ModelSerializer):
    class Meta:
        model = Train
        fields = ['train_name', 'image',  'departure_station', 'destination', 'arrival_station', 'price', 'seats_remaining']


class AvailableServiceSerializer(serializers.ModelSerializer):
    train_name = serializers.CharField(source='train.train_name', read_only=True)

    class Meta:
        model = Service
        fields = ['train_name', 'service_type', 'price']
