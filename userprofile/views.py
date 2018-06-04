from django.conf import settings
from rest_framework import filters
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework import viewsets, status
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token
from rest_framework.response import Response

from userprofile.permissions import UserViewSetPermissions
from userprofile.models import User
from livestream.models import Rating, Report, Appeal, Notification
from livestream.models import ApprovalRequest
from userprofile.serializers import UserSerializer, RatingSerializer
from userprofile.serializers import ReportSerializer, AppealSerializer
from userprofile.serializers import NotificationSerializer
from livestream.serializers import ApprovalRequestSerializer


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = (UserViewSetPermissions,)

    def create(self, request):
        req = request.data
        if User.objects.filter(username=req['username']).exists():
            ret = {'return': 'That username is already taken.'}
        else:
            gender = {'Male': 'M', 'Female': 'F'}
            user = User.objects.create_user(username=req['username'],
                                            first_name=req['first_name'],
                                            last_name=req['last_name'],
                                            gender=gender[req['gender']],
                                            password=req['password'])
            user.save()
            NotificationViewSet.notify("Register", user)
            ret = {'return': 'Account successfully created.'}
        return Response(ret, status=status.HTTP_201_CREATED)


class Login(ObtainAuthToken):

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data,
                                           context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        serializer = UserSerializer(user)
        token = Token.objects.get(user=user)
        return Response({'token': token.key,
                         'pk': user.pk,
                         'username': user.username,
                         'first_name': user.first_name,
                         'last_name': user.last_name,
                         'profile_picture': serializer.data['profile_picture']
                         })


class RatingViewSet(viewsets.ModelViewSet):
    queryset = Rating.objects.all()
    serializer_class = RatingSerializer
    permission_classes = (IsAuthenticated,)

    def create(self, request, *args, **kwargs):
        req = request.data
        rate = Rating(user_id=req['user'], appeal_id=req['appeal'],
                      rating=req['rating'])
        rate.save()
        NotificationViewSet.notify("Rating", rate)
        serializer = RatingSerializer(rate)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ReportViewSet(viewsets.ModelViewSet):
    queryset = Report.objects.all()
    serializer_class = ReportSerializer
    permission_classes = (IsAuthenticated,)

    def create(self, request):
        req = request.data
        count = Report.objects.filter(user=req['user']).count()
        user = User.objects.get(pk=req['user'])
        if count < settings.MAX_REPORT:
            reported_by = User.objects.get(pk=req['reported_by'])
            report = Report(user=user,
                            reported_by=reported_by,
                            reason=req['reason'])
            report.save()
            NotificationViewSet.notify("Report", report)
        else:
            user.is_active = False
            user.save()
        ret = {'return': 'User reported.'}
        return Response(ret, status=status.HTTP_201_CREATED)


class SearchListView(generics.ListAPIView):
    queryset = Appeal.objects.filter(status='AVAILABLE')
    serializer_class = AppealSerializer
    permission_classes = (IsAuthenticated,)
    filter_backends = (filters.SearchFilter,)
    search_fields = ('request_title', 'detail')


class NotificationViewSet(viewsets.ModelViewSet):
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    permission_classes = (IsAuthenticated,)

    def list(self, request, *args, **kwargs):
        queryset = Notification.objects.filter(user=request.user)\
                                       .order_by('-date_created')
        try:
            appeal = Appeal.objects.get(owner=request.user, status='A')
            approval = ApprovalRequest.objects.get(appeal=appeal, status='p')
            request = ApprovalRequestSerializer(approval)
            req = request.data
        except Appeal.DoesNotExist:
            req = []
        accept = Appeal.objects.get(helper=request.user, status='U')
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        ret = {'notification': serializer.data,
               'request': req,
               'session_id': accept.session_id}
        return Response(ret)

    def notify(notification, obj):
        if notification == 'Register':
            message = 'Welcome to aLive, ' + obj.username + '!'
            notif = Notification(user=obj, message=message)
            notif.save()
        elif notification == 'Rating':
            print(obj)
            message1 = 'You were rated ' + str(obj.rating) +\
                       ' by ' + obj.appeal.owner.username +\
                       ' in your last session.'
            notif = Notification(user=obj.user, message=message1)
            notif.save()

            message2 = 'You rated ' + obj.user.username +\
                       ' ' + str(obj.rating) + ' in your last session.'
            notif = Notification(user=obj.appeal.owner, message=message2)
            notif.save()
        elif notification == 'Report':
            reason = 'Unspecified' if obj.reason == '' else obj.reason
            message1 = 'You were reported by ' + obj.reported_by.username +\
                       ' in your last session. Reason: ' + reason
            notif = Notification(user=obj.user, message=message1)
            notif.save()

            message2 = 'You reported ' + obj.user.username +\
                       ' in your last session. Reason: ' + reason
            notif = Notification(user=obj.reported_by, message=message2)
            notif.save()
        elif notification == 'Cancel':
            message1 = 'You cancelled your request for the appeal ' +\
                       obj.appeal.request_title
            notif = Notification(message=message1, user=obj.helper)
            notif.save()
            message2 = 'You missed a request from ' + obj.helper.username
            notif = Notification(message=message2,
                                 user=obj.appeal.owner)
            notif.save()
        elif notification == 'Approval':
            temporary = True
        return True
