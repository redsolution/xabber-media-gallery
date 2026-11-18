from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import GenericAPIView, ListAPIView, CreateAPIView
from rest_framework.viewsets import GenericViewSet
from rest_framework.mixins import ListModelMixin, CreateModelMixin
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import PermissionDenied, NotFound
from rest_framework.filters import OrderingFilter

from django.conf import settings

from .utils.exceptions import QuotaExceeded, NoFile, MalformedData, LargeFileSize, WrongFileFormat


def _validate_jid(value):
    from jid_validation.jid import JID
    try:
        return JID(value)
    except:
        raise MalformedData


class FilesView(ListModelMixin, GenericViewSet):

    """
        Media file list
    """

    from .models import MediaFile
    from .serializers import FilesSerializer
    from .backends import CustomPagination, CustomFilterBackend, CustomTokenAuth

    http_method_names = ['get', 'delete']
    queryset = MediaFile.objects.all().order_by('-created_at')
    serializer_class = FilesSerializer
    pagination_class = CustomPagination
    filter_backends = [OrderingFilter, CustomFilterBackend]
    authentication_classes = [CustomTokenAuth, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    # ------------ FILTER ---------------

    # select parameters for special method
    filter_parameters_DELETE = [
        # name of provided param / queryset argument
        ('date_gte', 'created_at__gte'),
        ('date_lte', 'created_at__lte')
    ]
    filter_required_parameters_DELETE = ['id', 'media_type', 'contexts', 'date_gte', 'date_lte']

    filter_parameters = [
        'id',
        ('date_gte', 'created_at__gte'),
        ('date_lte', 'created_at__lte'),
        ('size_lte', 'size__lte'),
        ('size_gte', 'size__gte')
    ]

    # List method: Customized for filtering files by user
    def list(self, request, *args, **kwargs):
        """
        Retrieve a list of media files with optional filtering by type.
        """

        self.data = request.query_params

        user = self.get_user()
        queryset = self.get_filtered_queryset(user, self.data)
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    # Delete method: Customized for deleting media files with optional filtering by type and path
    def delete(self, request, *args, **kwargs):
        """
        Delete media files based on provided file paths or filtering criteria.
        """

        self.data = request.data

        user = self.get_user()

        path = self.data.get('file')

        if hasattr(self.data, 'getlist'):
            contexts = self.data.getlist('contexts', ['file'])
        else:
            contexts = self.data.get('contexts', ['file'])

        if not isinstance(contexts, list):
            raise MalformedData
        media_type = self.data.get('type') or self.data.get('media_type')
        id = self.data.get('id')

        queryset = self.get_delete_queryset(user, path, media_type, contexts, id)
        self.perform_deletion(queryset)

        return Response('Files were deleted', status=status.HTTP_204_NO_CONTENT)

    # Helper method: Get filtered queryset based on user and query parameters
    def get_filtered_queryset(self, user, query_params):
        """
        Filter queryset by user and optional media type.
        """

        contexts = query_params.getlist('contexts', ['file'])

        queryset = self.filter_queryset(self.get_queryset().filter(user=user, context__in=contexts))
        media_type = query_params.get('type') or query_params.get('media_type')
        queryset = self.filter_queryset_by_media_type(queryset, media_type)
        return queryset

    # Helper method: Get queryset for deletion based on file path or filtering criteria
    def get_delete_queryset(self, user, path, media_type, contexts, id):
        """
        Get queryset for deletion based on provided file path or media type.
        """

        from .utils.generators import get_title_from_path

        if path:
            title = get_title_from_path(path)
            queryset = self.get_queryset().filter(title=title, user=user)
        elif id:
            queryset = self.get_queryset().filter(id=id, user=user)
        else:
            queryset = self.filter_queryset(self.get_queryset().filter(user=user, context__in=contexts))
            queryset = self.filter_queryset_by_media_type(queryset, media_type)
        return queryset

    # Helper method: Perform deletion on queryset
    def perform_deletion(self, queryset):
        """
        Delete files in the provided queryset.
        """
        if not queryset:
            raise NotFound({"status": status.HTTP_404_NOT_FOUND, "error": "Files does not exist"})

        queryset.delete()

    # Helper method: Filter queryset based on media type
    def filter_queryset_by_media_type(self, queryset, media_type):
        """
        Filter queryset based on the provided media type.
        """

        from django.db.models import Q

        if media_type == 'file':
            return queryset.exclude(
                Q(media_type__contains='image')|
                Q(media_type__contains='video')|
                Q(media_type__contains='voice')|
                Q(media_type__contains='audio')
            )
        elif media_type:
            return queryset.filter(media_type__contains=media_type)
        return queryset

    def get_user(self):
        from .utils.other import check_scope
        from django.contrib.auth.models import User

        jid = self.data.get('jid')

        if jid:
            jid_obj = _validate_jid(jid)

            jid = jid_obj.userhost()
            host = jid_obj.host

            if jid != self.request.user.username:
                check_scope(self.request.auth, jid, host)

            user = User.objects.filter(username=jid).first()
            if not user:
                raise NotFound({'status': status.HTTP_404_NOT_FOUND, 'error': 'User does not exist'})
        else:
            user = self.request.user

        return user


class FilesPercentView(ListModelMixin, GenericViewSet):

    """
        Media file list by percent
    """
    
    from .models import MediaFile
    from .serializers import FilesSerializer
    from .backends import CustomPagination, CustomFilterBackend, CustomTokenAuth

    http_method_names = ['get', 'delete']
    queryset = MediaFile.objects.all()
    serializer_class = FilesSerializer
    pagination_class = CustomPagination
    authentication_classes = [CustomTokenAuth, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    # List method: Customized for filtering files by user
    def list(self, request, *args, **kwargs):
        """
        Retrieve a list of media files with optional filtering by type and percentage threshold.
        """

        self.data = request.query_params

        self.user = self.get_user()
        percent = kwargs.get('percent')
        queryset = self.get_filtered_queryset(percent)
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    # Helper method: Get filtered queryset based on user and query parameters
    def get_filtered_queryset(self, percent):
        """
        Filter queryset by user and optional media type and percentage threshold.
        """

        from .models import MediaFile

        queryset = MediaFile.objects.filter(user=self.user)
        queryset = self.filter_queryset_by_threshold(queryset, percent)
        return queryset

    # Helper method: Filter queryset based on threshold size percentage
    def filter_queryset_by_threshold(self, queryset, percent):
        """
        Filter queryset based on the provided percentage threshold of total quota size.
        """
        from django.db.models import Sum, Case, When, Value, CharField

        total_used_size = queryset.aggregate(total_size=Sum('size'))['total_size'] or 0
        quota_size = self.user.quota.get_size

        remaining_space = total_used_size - (quota_size * (100 - percent)) / 100

        if remaining_space <= 0:
            # Already have enough free space, return an empty queryset
            return queryset.none()

        # create temporary field avatar_order to order avatar files in the end of queryset
        sorted_queryset = queryset.annotate(
            avatar_order=Case(
                When(context='avatar', then=Value(1)),
                default=Value(0),
                output_field=CharField(),
            )
        ).order_by('avatar_order', 'created_at')

        files_ids = []
        current_size = 0

        for file in sorted_queryset:
            if current_size <= remaining_space:
                files_ids.append(file.id)
                current_size += file.size
            else:
                break

        return queryset.filter(id__in=files_ids)

    # Delete method: Customized for deleting media files with optional filtering by type and path
    def delete(self, request, *args, **kwargs):
        """
        Delete media files by percent.
        """

        self.data = request.data

        self.user = self.get_user()
        percent = kwargs.get('percent')
        queryset = self.get_filtered_queryset(percent)
        self.perform_deletion(queryset)

        return Response('Files were deleted', status=status.HTTP_204_NO_CONTENT)

    # Helper method: Perform deletion on queryset
    def perform_deletion(self, queryset):
        """
        Delete files in the provided queryset.
        """
        if not queryset:
            raise NotFound({"status": status.HTTP_404_NOT_FOUND, "error": "Files does not exist"})

        queryset.delete()

    def get_user(self):
        from .utils.other import check_scope
        from django.contrib.auth.models import User

        jid = self.data.get('jid')

        if jid:
            jid_obj = _validate_jid(jid)

            jid = jid_obj.userhost()
            host = jid_obj.host
            if jid != self.request.user.username:
                check_scope(self.request.auth, jid, host)

            user = User.objects.filter(username=jid).first()
            if not user:
                raise NotFound({'status': status.HTTP_404_NOT_FOUND, 'error': 'User does not exist'})
        else:
            user = self.request.user

        return user


class SlotView(GenericAPIView):

    """
        Check user quota availability
        or create new media file if original file exists
    """

    from .serializers import SlotSerializer
    from .backends import CustomPagination, CustomFilterBackend, CustomTokenAuth

    http_method_names = ['get',]
    authentication_classes = [CustomTokenAuth, SessionAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = SlotSerializer

    def get(self, request, *args, **kwargs):
        from .utils.responses import serialize_data, file_upload_response, get_quota_response
        from .utils.validators import validate_name
        from .utils.thumbnails import create_thumbnails
        from .models import MediaFile, EntityFile, Quota
        from threading import Thread

        # validate data
        data = serialize_data(self.get_serializer(data=request.query_params))

        # variables
        entity_file = EntityFile.objects.filter(hash=data.get('hash')).first()
        size = data.get('size')
        name = data.get('name')
        name = validate_name(name)

        # check max file size
        if size > settings.MAX_FILE_SIZE:
            raise LargeFileSize

        # check user quota
        quota, created = Quota.objects.get_or_create(user=request.user)
        if not quota.quota_available(size):
            raise QuotaExceeded
        
        if entity_file:
            # create new simlink
            try:
                media_type = entity_file.mediafile_set.order_by('created_at').first().media_type
            except:
                media_type = None

            media_file = MediaFile.objects.create(
                entity_file=entity_file,
                user=request.user,
                name=name,
                media_type=media_type
            )

            if media_type:
                Thread(
                    target=create_thumbnails,
                    args=(media_file,),
                ).start()
            return Response(file_upload_response(media_file), status.HTTP_200_OK)
        else:
            return Response(get_quota_response(quota))


class UploadFileView(CreateAPIView):

    """ Customized to create multiple models on uploading file """

    from .models import EntityFile
    from .serializers import FilesUploadSerializer
    from .backends import CustomTokenAuth


    queryset = EntityFile.objects.all()
    serializer_class = FilesUploadSerializer
    http_method_names = ['post',]
    authentication_classes = [CustomTokenAuth, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        from .utils.validators import validate_name
        from .utils.responses import serialize_data, file_upload_response
        from .utils.thumbnails import crop_avatar, create_thumbnails
        from .utils.generators import hash_sha1
        from .models import EntityFile, MediaFile
        from threading import Thread

        # validate data
        file = request.data.get('file', request.FILES.get('file'))

        if not file:
            raise NoFile
        file.name = validate_name(file.name)
        data = serialize_data(self.get_serializer(data=request.data))

        # variables
        avatar_thumbs = data.get('create_thumbnails', True)
        size = data.get('size', 0)
        media_type = data.get('media_type', None)
        metadata = data.get('metadata', {})
        max_size = settings.MAX_AVATAR_SIZE

        context = data.get('context', 'file')

        if context == 'avatar':
            if 'image' in media_type:
                try:
                    avatar = crop_avatar(file)
                    max_size = avatar.get('max_size', settings.MAX_AVATAR_SIZE)
                    metadata['width'] = max_size
                    metadata['height'] = max_size
                except:
                    pass
            else:
                raise WrongFileFormat

        f = open(file.temporary_file_path(), 'rb')
        file_hash = hash_sha1(f)

        # create or find original file
        entity_file = EntityFile.objects.filter(hash=file_hash).first()
        if not entity_file:
            entity_file = EntityFile.objects.create(file=file, hash=file_hash)

        # create media file and symlink
        # Symlink creates in signals
        media_file = MediaFile.objects.create(
            entity_file=entity_file,
            user=request.user,
            metadata=metadata,
            context=context,
            avatar_thumbs=avatar_thumbs,
            media_type=media_type,
            size=size,
            name=file.name
        )

        # Create thumbnails using multithreading. Required mimetypes: [image, video]

        if media_type:
            Thread(
                target=create_thumbnails,
                args=(media_file,),
                kwargs={
                    'avatar_thumbs': avatar_thumbs
                }
            ).start()

        return Response(
            file_upload_response(media_file, avatar_thumbs, max_size),
            status=status.HTTP_201_CREATED
        )


class XmppCodeView(GenericAPIView):

    from .serializers import XmppCodeSerializer

    serializer_class = XmppCodeSerializer

    def post(self, request):

        from .utils.other import is_blacklisted_or_not_whitelisted
        from .utils.responses import serialize_data
        from .utils.generators import generate_code
        from .utils.other import send_code

        from .models import VerificationCode

        from django.contrib.auth.models import User

        from uuid import uuid4
        from threading import Thread

        # validate data
        data = serialize_data(self.get_serializer(data=request.data))

        # variables
        jid = data.get('jid')

        code = generate_code()
        confirm_url = request.build_absolute_uri('xmpp_auth')
        stanza_id = uuid4()

        jid_obj = _validate_jid(jid)
        jid = jid_obj.full()
        bare_jid = jid_obj.userhost()
        domain = jid_obj.host

        # default stanza type is 'message'
        stanza_type = data.get('type') if data.get('type') else 'message'

        if is_blacklisted_or_not_whitelisted(bare_jid, domain):
            raise PermissionDenied({'status': status.HTTP_403_FORBIDDEN, 'error': 'Access denied'})

        # send code using multithreading
        Thread(
            target=send_code,
            args=(
                settings.XMPP_LOGIN, settings.XMPP_PASS, code,
                jid, stanza_id, stanza_type, confirm_url,
            ),
        ).start()

        # create verification code
        user, created = User.objects.get_or_create(username=bare_jid)
        VerificationCode.objects.create(user=user, value=code)

        return Response({'request_id': stanza_id, 'api_jid': settings.XMPP_LOGIN}, status=status.HTTP_201_CREATED)


class XmppAuthView(CreateAPIView):

    """ Token create view """

    from .serializers import XmppAuthSerializer

    serializer_class = XmppAuthSerializer

    def create(self, request, *args, **kwargs):
        from .utils.responses import serialize_data

        from .models import VerificationCode, Token

        from django.contrib.auth.models import User
        
        # validate data
        data = serialize_data(self.get_serializer(data=request.data))

        # variables
        jid = data.get('jid')
        code = data.get('code')

        user = User.objects.filter(username=jid).first()
        verification_code = VerificationCode.objects.filter(user=user, value=code).first()

        # check verification code expires
        if verification_code and verification_code.check_expires():
            token = Token.objects.create(user=user, device=data.get('device'), client=data.get('client'))
            verification_code.delete()
            headers = self.get_success_headers(data)
            return Response({'token': token.key, 'expires': token.expires}, status=status.HTTP_201_CREATED, headers=headers)
        else:
            raise NotFound({'status': status.HTTP_404_NOT_FOUND, 'error': 'Does not exist'})


class TokensView(ListModelMixin, GenericViewSet):

    """ Token list view"""

    from .models import Token
    from .serializers import TokensSerializer
    from .backends import CustomTokenAuth

    queryset = Token.objects.all()
    serializer_class = TokensSerializer
    authentication_classes = [CustomTokenAuth, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def delete(self, request, *args, **kwargs):
        from .utils.responses import serialize_data
        from .models import Token

        # validate data
        data = serialize_data(self.get_serializer(data=request.data))

        try:
            self.get_queryset().get(id=data.get('token_id')).delete()
        except Token.DoesNotExist:
            raise NotFound({'status': status.HTTP_404_NOT_FOUND, 'error': 'Token does not exist'})

        return Response('Token was delete', status.HTTP_204_NO_CONTENT)


class QuotaView(GenericAPIView):

    """ Admin method to change quota """

    from .backends import CustomTokenAuth
    from .serializers import QuotaSerializer

    http_method_names = ['get', 'put']
    authentication_classes = [CustomTokenAuth, SessionAuthentication]
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class = QuotaSerializer

    def get(self, request, *args, **kwargs):
        from .utils.responses import serialize_data, get_quota_response
        from .models import Quota

        self.data = serialize_data(self.get_serializer(data=request.query_params))
        user = self.get_user()

        quota, created = Quota.objects.get_or_create(user=user)
        return Response(get_quota_response(quota))

    def put(self, request):
        from .utils.responses import serialize_data, get_quota_response
        from .models import Quota

        self.data = serialize_data(self.get_serializer(data=request.data))
        value = self.data.get('value')
        user = self.get_user()

        if value is None or not isinstance(value, int) or value < 0:
            raise MalformedData

        quota, created = Quota.objects.get_or_create(user=user)
        quota.size = value
        quota.save()
        return Response(get_quota_response(quota))

    def get_user(self):
        from .utils.other import check_scope
        from django.contrib.auth.models import User

        jid = self.data.get('jid')

        if jid:
            jid_obj = _validate_jid(jid)
            jid = jid_obj.userhost()
            host = jid_obj.host
            if jid != self.request.user.username:
                check_scope(self.request.auth, jid, host)

            user, created = User.objects.get_or_create(username=jid)
        else:
            user = self.request.user

        return user


class DefaultQuotaView(GenericAPIView):
    from .backends import CustomTokenAuth, CustomFilterBackend
    from .serializers import DefaultQuotaSerializer
    from .models import Quota
    from django.db.models import Q

    authentication_classes = [CustomTokenAuth, SessionAuthentication]
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class = DefaultQuotaSerializer
    filter_backends = [CustomFilterBackend]
    queryset = Quota.objects.exclude(Q(host=None) | Q(host=''))
    filter_required_parameters = ['host']
    http_method_names = ['get', 'post']

    filter_parameters = [
        'host'
    ]

    def get(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request):
        from .utils.responses import serialize_data
        from .models import Quota

        data = serialize_data(self.get_serializer(data=request.data))
        host = data.get('host')
        size = data.get('size', 0)

        quota, created = Quota.objects.update_or_create(
            user=None, host=host,
            defaults={
                'size': size
            }
        )
        return Response('Default quota changed successfully', status=status.HTTP_200_OK)


class AccountListView(ListAPIView):

    from django.contrib.auth.models import User

    from .serializers import AccountListSerializer
    from .backends import CustomFilterBackend, CustomTokenAuth
    
    queryset = User.objects.all()
    serializer_class = AccountListSerializer
    filter_backends = [OrderingFilter, CustomFilterBackend]
    authentication_classes = [CustomTokenAuth, SessionAuthentication]
    permission_classes = [IsAuthenticated, IsAdminUser]

    filter_parameters = [
        ('vhost', 'username__endswith')
    ]
    filter_required_parameters = ['vhost',]

    ordering_fields = ['quota_size', 'quota__used', 'username']

    def get_queryset(self):
        from .models import Quota

        from django.contrib.auth.models import User
        from django.db.models import Q, Case, When, Value, IntegerField, Subquery
        from django.db.models.functions import Coalesce
        from .utils.other import check_scope

        # Subquery to get the global quota size
        host = self.request.query_params.get('vhost')

        global_quota_subquery = Quota.objects.filter(
            host=host,
            user=None
        ).exclude(
            Q(host__isnull=True) | Q(host='')
        ).values('size')[:1]

        # Annotate users with their effective quota size
        users_with_quota = User.objects.annotate(
            quota_size=Case(
                When(quota__size__gt=0, then='quota__size'),
                When(
                    Q(quota__size=0),
                    then=Coalesce(Subquery(global_quota_subquery), Value(settings.DEFAULT_QUOTA_SIZE))
                ),
                default=Value(settings.DEFAULT_QUOTA_SIZE),
                output_field=IntegerField()
            )
        )

        check_scope(self.request.auth, list(users_with_quota), host, all_users=True)
        
        return users_with_quota


class AccountView(GenericViewSet):

    """
         Account DELETE view.
         If user is not authenticated requires parameters:
            * jid (natalia.barabanschikova@xabber.org)
            * code (484456)
     """
    
    from .backends import CustomTokenAuth
    from .serializers import AccountSerializer

    http_method_names = ['delete',]
    authentication_classes = [CustomTokenAuth]
    serializer_class = AccountSerializer

    def delete(self, request, *args, **kwargs):
        """
        Delete user account.
        If user is authenticated, deletes the account of the authenticated user.
        If user is not authenticated, requires 'jid' and 'code' parameters to delete the account of the specified user.
        """

        from .utils.responses import serialize_data
        from django.contrib.auth.models import User
        
        # validate data
        data = serialize_data(self.get_serializer(data=request.data))
        self.jid = data.get('jid')

        if not request.user.is_authenticated:
            # get required params
            code = data.get('code')
            
            if not self.jid or not code:
                raise MalformedData({'status': status.HTTP_400_BAD_REQUEST, 'error': 'Missing required parameters'})
            
            try:
                user = User.objects.get(username=self.jid, verification_code__value=code)
            except User.DoesNotExist:
                raise NotFound({'status': status.HTTP_404_NOT_FOUND, 'error': 'Account does not exist'})
        else:
            user = self.get_user()

        user.delete()
        return Response('Account was delete', status.HTTP_204_NO_CONTENT)
    
    def get_user(self):
        from .utils.other import check_scope
        from django.contrib.auth.models import User

        if self.jid:
            jid_obj = _validate_jid(self.jid)
            self.jid = jid_obj.userhost()
            host = jid_obj.host
            if self.jid != self.request.user.username:
                check_scope(self.request.auth, self.jid, host)

            user = User.objects.filter(username=self.jid).first()
            if not user:
                raise NotFound({'status': status.HTTP_404_NOT_FOUND, 'error': 'User does not exist'})
        else:
            user = self.request.user

        return user


class StatsView(ListAPIView):

    from .backends import CustomTokenAuth, CustomFilterBackend
    from .models import MediaFile

    authentication_classes = [CustomTokenAuth, SessionAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [OrderingFilter, CustomFilterBackend]
    queryset = MediaFile.objects.filter()

    # ------------ FILTER ---------------

    filter_parameters = [
        'id',
        ('date_gte', 'created_at__gte'),
        ('date_lte', 'created_at__lte'),
    ]

    def get(self, request, *args, **kwargs):
        from .utils.responses import stats_response

        from jid_validation.jid import prep_host

        try:
            host = prep_host(self.request.query_params.get('host'))
            queryset = self.filter_queryset(self.get_queryset().filter(user__username__endswith=host))
            size = 0
        except:
            user = self.get_user()
            queryset = self.filter_queryset(self.get_queryset().filter(user=user))
            size = user.quota.get_size

        # Extract the 'media_type' parameter from the query parameters
        media_type = request.query_params.get('type') or request.query_params.get('media_type')

        if media_type == 'file':
            queryset = queryset.exclude(
                Q(media_type__contains='image')|
                Q(media_type__contains='video')|
                Q(media_type__contains='voice')|
                Q(media_type__contains='audio')
            )
        elif media_type:
            queryset = queryset.filter(media_type__contains=media_type)

        return Response(stats_response(queryset, size))

    def get_user(self):
        from .utils.other import check_scope
        from django.contrib.auth.models import User

        jid = self.request.query_params.get('jid')

        if jid:
            jid_obj = _validate_jid(jid)

            jid = jid_obj.userhost()
            host = jid_obj.host

            if jid != self.request.user.username:
                check_scope(self.request.auth, jid, host)

            user = User.objects.filter(username=jid).first()
            if not user:
                raise NotFound({'status': status.HTTP_404_NOT_FOUND, 'error': 'User does not exist'})
        else:
            user = self.request.user

        return user


class DiskSpaceView(APIView):

    from .backends import CustomTokenAuth

    authentication_classes = [CustomTokenAuth, SessionAuthentication]
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request, *args, **kwargs):
        import shutil
        usage = shutil.disk_usage('/')

        # return Response({
        #     'disk_total': 314572800, # usage.total,
        #     'disk_used': 209715200, # usage.used,
        #     'disk_free': 54857600 # usage.free,
        # })
    
        return Response({
            'disk_total': usage.total,
            'disk_used': usage.used,
            'disk_free': usage.free,
        })


class OpenGraphView(APIView):

    http_method_names = ['post',]

    def post(self, request):
        from .utils.opengraph import OpenGraph

        url = request.data.get('url')
        if not url:
            raise MalformedData
        result = OpenGraph(url)
        if result.is_valid():
            return Response({'ogp': result.to_html()}, status=201)
        raise NotFound({'error': '404'})


class WhiteListView(ListModelMixin, GenericViewSet):

    """ Admin method to change white list """

    from .backends import CustomTokenAuth, CustomFilterBackend, CustomPagination
    from .serializers import WhiteListSerializer
    from .models import WhiteList

    authentication_classes = [CustomTokenAuth, SessionAuthentication]
    permission_classes = [IsAuthenticated, IsAdminUser]
    filter_backends = [CustomFilterBackend]
    filter_parameters = ['host']
    pagination_class = CustomPagination

    serializer_class = WhiteListSerializer
    queryset = WhiteList.objects.all()

    def list(self, request, *args, **kwargs):
        white_lists = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(white_lists)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    def create(self, request):
        from .utils.responses import serialize_data
        from .utils.other import check_scope
        from .models import WhiteList, ListUser

        data = serialize_data(self.get_serializer(data=request.data))
        users = data.get('users', [])
        host = data.get('host')
        all_users = data.get('all_users', False)

        check_scope(request.auth, users, host, all_users)

        # Create or update the WhiteList instance
        white_list, created = WhiteList.objects.update_or_create(
            host=host,
            defaults={
                "all_users": all_users
            }
        )

        if all_users:
            white_list.users.set([])
        else:
            # Create ListUser instances if they don't already exist
            white_list_users_to_create = [ListUser(jid=user) for user in users]
            ListUser.objects.bulk_create(white_list_users_to_create, ignore_conflicts=True)

            # Retrieve the ListUser instances that were just created or already existed
            white_list_users = ListUser.objects.filter(jid__in=users)

            # Set the many-to-many relationship
            white_list.users.set(white_list_users)
        return Response('White list was changed successfully', status=status.HTTP_200_OK)


class BlackListView(ListModelMixin, CreateModelMixin, GenericViewSet):

    """ Admin method to change black list """

    from .backends import CustomTokenAuth, CustomFilterBackend, CustomPagination
    from .serializers import BlackListSerializer
    from .models import BlackList

    authentication_classes = [CustomTokenAuth, SessionAuthentication]
    permission_classes = [IsAuthenticated, IsAdminUser]
    filter_backends = [CustomFilterBackend]
    filter_parameters = ['host']
    pagination_class = CustomPagination

    serializer_class = BlackListSerializer
    queryset = BlackList.objects.all()

    def list(self, request, *args, **kwargs):
        black_lists = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(black_lists)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    def create(self, request, *args, **kwargs):
        from .utils.responses import serialize_data
        from .utils.other import check_scope
        from .models import BlackList, ListUser

        # Serialize and extract data
        data = serialize_data(self.get_serializer(data=request.data))
        users = data.get('users', [])
        host = data.get('host')
        all_users = data.get('all_users', False)

        check_scope(request.auth, users, host, all_users)

        # Create or update the BlackList instance
        black_list, created = BlackList.objects.update_or_create(
            host=host,
            defaults={
                "all_users": all_users
            }
        )

        if all_users:
            black_list.users.set([])
        else:
            # Create ListUser instances if they don't already exist
            black_list_users_to_create = [ListUser(jid=user) for user in users]
            ListUser.objects.bulk_create(black_list_users_to_create, ignore_conflicts=True)

            # Retrieve the ListUser instances that were just created or already existed
            black_list_users = ListUser.objects.filter(jid__in=users)

            # Set the many-to-many relationship
            black_list.users.set(black_list_users)

        # Return a successful response
        return Response('Black list was changed successfully', status=status.HTTP_200_OK)