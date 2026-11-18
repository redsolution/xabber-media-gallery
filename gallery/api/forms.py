from django import forms
from django.contrib.admin.widgets import FilteredSelectMultiple

from gallery.api.models import WhiteList, BlackList


class WhiteListAdminForm(forms.ModelForm):
    class Meta:
        fields = '__all__'
        model = WhiteList
        widgets = {
            'users': FilteredSelectMultiple(
                verbose_name='Users',
                is_stacked=False
            )
        }


class BlackListAdminForm(forms.ModelForm):
    class Meta:
        fields = '__all__'
        model = BlackList
        widgets = {
            'users': FilteredSelectMultiple(
                verbose_name='Users',
                is_stacked=False
            )
        }