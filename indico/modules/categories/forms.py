# This file is part of Indico.
# Copyright (C) 2002 - 2024 CERN
#
# Indico is free software; you can redistribute it and/or
# modify it under the terms of the MIT License; see the
# LICENSE file for more details.

from functools import partial

from flask import request
from wtforms.fields import BooleanField, HiddenField, IntegerField, SelectField, StringField
from wtforms.validators import DataRequired, InputRequired, Length, NumberRange, Optional, ValidationError

from indico.core.permissions import FULL_ACCESS_PERMISSION, READ_ACCESS_PERMISSION
from indico.modules.categories.models.categories import Category, EventCreationMode, EventMessageMode
from indico.modules.categories.models.roles import CategoryRole
from indico.modules.categories.util import get_image_data, get_visibility_options
from indico.modules.events import Event
from indico.modules.events.fields import IndicoThemeSelectField
from indico.modules.events.models.events import EventType
from indico.modules.networks import IPNetworkGroup
from indico.util.i18n import _
from indico.util.user import principal_from_identifier
from indico.web.forms.base import IndicoForm
from indico.web.forms.colors import get_role_colors
from indico.web.forms.fields import (EditableFileField, EmailListField, HiddenFieldList, IndicoEnumSelectField,
                                     IndicoMarkdownField, IndicoProtectionField, IndicoSinglePalettePickerField,
                                     IndicoTimezoneSelectField, MultipleItemsField)
from indico.web.forms.fields.principals import PermissionsField
from indico.web.forms.widgets import HiddenCheckbox, SwitchWidget


class CategorySettingsForm(IndicoForm):
    BASIC_FIELDS = ('title', 'description', 'timezone', 'lecture_theme', 'meeting_theme', 'visibility',
                    'suggestions_disabled', 'is_flat_view_enabled', 'show_future_months',
                    'event_creation_notification_emails', 'notify_managers')
    EVENT_HEADER_FIELDS = ('event_message_mode', 'event_message')

    title = StringField(_('Title'), [DataRequired()])
    description = IndicoMarkdownField(_('Description'))
    timezone = IndicoTimezoneSelectField(_('Timezone'), [DataRequired()],
                                         description=_('Default timezone event lists will show up in. It will also be '
                                                       'used as a default for new events.'))
    lecture_theme = IndicoThemeSelectField(_('Theme for Lectures'), [DataRequired()], event_type=EventType.lecture,
                                           description=_('Default timetable theme used for lecture events'))
    meeting_theme = IndicoThemeSelectField(_('Theme for Meetings'), [DataRequired()], event_type=EventType.meeting,
                                           description=_('Default timetable theme used for meeting events'))
    suggestions_disabled = BooleanField(_('Disable Suggestions'), widget=SwitchWidget(),
                                        description=_("Enable this if you don't want Indico to suggest this category as"
                                                      " a possible addition to a user's favorites."))
    is_flat_view_enabled = BooleanField(_('Allow flat view'), widget=SwitchWidget(),
                                        description=_('Allow users to view all the events descending from this '
                                                      'category in one single page. This is not recommended on large '
                                                      'categories with thousands of events.'))
    show_future_months = IntegerField(_('Future months threshold'), [NumberRange(min=0)],
                                      description=_('Events past the threshold will be hidden by default to avoid '
                                                    'clutter, the user can click to expand them. If no events are '
                                                    'found within this threshold, it is extended to show the first '
                                                    'month with events.'))
    event_message_mode = IndicoEnumSelectField(_('Message Type'), enum=EventMessageMode,
                                               default=EventMessageMode.disabled,
                                               description=_('This message will show up at the top of every event page '
                                                             'in this category'))
    event_message = IndicoMarkdownField(_('Content'))
    notify_managers = BooleanField(_('Notify managers'), widget=SwitchWidget(),
                                   description=_('Whether to send email notifications to all managers of this category '
                                                 'when an event is created inside it or in any of its subcategories.'))
    event_creation_notification_emails = EmailListField(_('Notification E-mails'),
                                                        description=_('List of emails that will receive a notification '
                                                                      'every time a new event is created inside the '
                                                                      'category or one of its subcategories. '
                                                                      'One email address per line.'))


class CategoryIconForm(IndicoForm):
    icon = EditableFileField('Icon', accepted_file_types='image/jpeg,image/jpg,image/png,image/gif',
                             add_remove_links=False, handle_flashes=True, get_metadata=partial(get_image_data, 'icon'),
                             description=_('Small icon that will show up next to category names in overview pages. '
                                           'Will be automatically resized to 16x16 pixels. This may involve loss of '
                                           'image quality, so try to upload images as close as possible to those '
                                           'dimensions.'))


class CategoryLogoForm(IndicoForm):
    logo = EditableFileField('Logo', accepted_file_types='image/jpeg,image/jpg,image/png,image/gif',
                             add_remove_links=False, handle_flashes=True, get_metadata=partial(get_image_data, 'logo'),
                             description=_('Logo that will show up next to the category description. Will be '
                                           'automatically resized to at most 200x200 pixels.'))


class CategoryProtectionForm(IndicoForm):
    permissions = PermissionsField(_('Permissions'), object_type='category')
    protection_mode = IndicoProtectionField(_('Protection mode'), protected_object=lambda form: form.protected_object)
    own_no_access_contact = StringField(_('No access contact'),
                                        description=_('Contact information shown when someone lacks access to the '
                                                      'category'))
    visibility = SelectField(_('Event visibility'),
                             [Optional()], coerce=lambda x: None if x == '' else int(x),  # noqa: PLC1901
                             description=_('''From which point in the category tree contents will be visible from '''
                                           '''(number of categories upwards). Applies to "Today's events" and '''
                                           '''Calendar. If the category is moved, this number will be preserved.'''))
    event_creation_mode = IndicoEnumSelectField(_('Event creation mode'), enum=EventCreationMode,
                                                default=EventCreationMode.restricted,
                                                description=_('Specify who can create events in the category and '
                                                              'whether they need to be approved. Regardless of this '
                                                              'setting, users cannot create/propose events unless they '
                                                              'have at least read access to the category.'))

    def __init__(self, *args, **kwargs):
        self.protected_object = self.category = kwargs.pop('category')
        super().__init__(*args, **kwargs)
        self._init_visibility()

    def _init_visibility(self):
        self.visibility.choices = get_visibility_options(self.category, allow_invisible=False)
        # Check if category visibility would be affected by any of the parents
        real_horizon = self.category.real_visibility_horizon
        own_horizon = self.category.own_visibility_horizon
        if real_horizon and real_horizon.is_descendant_of(own_horizon):
            self.visibility.warning = _("This category's visibility is currently limited by that of '{}'.").format(
                real_horizon.title)

    def validate_permissions(self, field):
        for principal_fossil, permissions in field.data:
            principal = principal_from_identifier(principal_fossil['identifier'],
                                                  allow_external_users=True,
                                                  allow_groups=True,
                                                  allow_networks=True,
                                                  allow_category_roles=True,
                                                  category_id=self.category.id)
            if isinstance(principal, IPNetworkGroup) and set(permissions) - {READ_ACCESS_PERMISSION}:
                msg = _('IP networks cannot have management permissions: {}').format(principal.name)
                raise ValidationError(msg)
            if FULL_ACCESS_PERMISSION in permissions and len(permissions) != 1:
                # when full access permission is set, discard rest of permissions
                permissions[:] = [FULL_ACCESS_PERMISSION]


class CreateCategoryForm(IndicoForm):
    """Form to create a new Category."""

    title = StringField(_('Title'), [DataRequired()])
    description = IndicoMarkdownField(_('Description'))


class SplitCategoryForm(IndicoForm):
    first_category = StringField(_('Category name #1'), [DataRequired()],
                                 description=_('Selected events will be moved into a new sub-category with this '
                                               'title.'))
    second_category = StringField(_('Category name #2'),
                                  description=_('Events that were not selected will be moved into a new sub-category '
                                                'with this title. If omitted, those events will remain in the current '
                                                'category.'))
    event_id = HiddenFieldList()
    all_selected = BooleanField(widget=HiddenCheckbox())
    submitted = HiddenField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.all_selected.data:
            self.event_id.data = []
            self.first_category.label.text = _('Category name')
            self.first_category.description = _('The events will be moved into a new sub-category with this title.')
            del self.second_category

    def is_submitted(self):
        return super().is_submitted() and 'submitted' in request.form


class UpcomingEventsForm(IndicoForm):
    max_entries = IntegerField(_('Max. events'), [InputRequired(), NumberRange(min=0)],
                               description=_('The maximum number of upcoming events to show. Events are sorted by '
                                             'weight so events with a lower weight are more likely to be omitted if '
                                             'there are too many events to show.'))
    entries = MultipleItemsField(_('Upcoming events'),
                                 fields=[{'id': 'type', 'caption': _('Type'), 'required': True, 'type': 'select'},
                                         {'id': 'id', 'caption': _('ID'), 'required': True, 'type': 'number',
                                          'step': 1, 'coerce': int},
                                         {'id': 'days', 'caption': _('Days'), 'required': True, 'type': 'number',
                                          'step': 1, 'coerce': int},
                                         {'id': 'weight', 'caption': _('Weight'), 'required': True, 'type': 'number',
                                          'coerce': float}],
                                 choices={'type': {'category': _('Category'),
                                                   'category_tree': _('Category & Subcategories'),
                                                   'event': _('Event')}},
                                 description=_("Specify categories/events shown in the 'upcoming events' list on the "
                                               'home page.'))

    def validate_entries(self, field):
        if field.errors:
            return
        for entry in field.data:
            if entry['days'] < 0:
                raise ValidationError(_("'Days' must be a positive integer"))
            if entry['type'] not in {'category', 'category_tree', 'event'}:
                raise ValidationError(_('Invalid type'))
            if entry['type'] in {'category', 'category_tree'} and not Category.get(entry['id'], is_deleted=False):
                raise ValidationError(_('Invalid category: {}').format(entry['id']))
            if entry['type'] == 'event' and not Event.get(entry['id'], is_deleted=False):
                raise ValidationError(_('Invalid event: {}').format(entry['id']))


class CategoryRoleForm(IndicoForm):
    name = StringField(_('Name'), [DataRequired()],
                       description=_('The full name of the role'))
    code = StringField(_('Code'), [DataRequired(), Length(max=3)], filters=[lambda x: x.upper() if x else ''],
                       render_kw={'style': 'width:60px; text-align:center; text-transform:uppercase;'},
                       description=_('A shortcut (max. 3 characters) for the role'))
    color = IndicoSinglePalettePickerField(_('Color'), color_list=get_role_colors(), text_color='ffffff',
                                           description=_('The color used when displaying the role'))

    def __init__(self, *args, **kwargs):
        self.role = kwargs.get('obj')
        self.category = kwargs.pop('category')
        super().__init__(*args, **kwargs)

    def validate_code(self, field):
        query = CategoryRole.query.with_parent(self.category).filter_by(code=field.data)
        if self.role is not None:
            query = query.filter(CategoryRole.id != self.role.id)
        if query.has_rows():
            raise ValidationError(_('A role with this code already exists.'))
