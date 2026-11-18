from django.core.validators import RegexValidator
from .exceptions import MalformedData
from django.utils.text import get_valid_filename
import unicodedata
from unidecode import unidecode


class MimeTypeValidator(RegexValidator):

    regex = '\w+/[-.\w]+(?:\+[-.\w]+)?'

    """
        Check mime type validity using regex
    """

    def __call__(self, value):

        """ Customized method to raise MalformedData """

        regex_matches = self.regex.search(str(value))
        invalid_input = regex_matches if self.inverse_match else not regex_matches
        if invalid_input:
            raise MalformedData


def validate_name(old_name: str) -> str:

    if isinstance(old_name, str):
        try:
            normalized = unicodedata.normalize('NFKC', old_name).lower()
            file_name = get_valid_filename(normalized)
            file_name_ascii = unidecode(file_name)
            return file_name_ascii if file_name_ascii else 'untitled'
        except Exception as e:
            print(e)
    return old_name
