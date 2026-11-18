from django.core.management.base import BaseCommand
from gallery.api.models import VerificationCode, Token
from django.utils import timezone


class Command(BaseCommand):
    help = 'Delete expired verification codes'

    def handle(self, *args, **options):
        try:
            VerificationCode.objects.filter(expires__lte=timezone.now()).delete()
            Token.objects.filter(expires__lte=timezone.now()).delete()
        except Exception as e:
            print(e)