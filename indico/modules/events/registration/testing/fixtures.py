# This file is part of Indico.
# Copyright (C) 2002 - 2024 CERN
#
# Indico is free software; you can redistribute it and/or
# modify it under the terms of the MIT License; see the
# LICENSE file for more details.

import pytest

from indico.modules.events.registration.models.forms import RegistrationForm
from indico.modules.events.registration.models.registrations import Registration, RegistrationState
from indico.modules.events.registration.util import create_personal_data_fields


@pytest.fixture
def dummy_regform(db, dummy_event):
    """Create a dummy registration form for the dummy event."""
    regform = RegistrationForm(id=420, event=dummy_event, title='Registration Form', currency='USD')
    create_personal_data_fields(regform)

    # enable all fields
    for field in regform.sections[0].fields:
        field.is_enabled = True
    db.session.add(regform)
    db.session.flush()
    return regform


@pytest.fixture
def dummy_reg(db, dummy_event, dummy_regform, dummy_user):
    """Create a dummy registration for the dummy event."""
    reg = Registration(
        registration_form_id=dummy_regform.id,
        first_name='Guinea',
        last_name='Pig',
        checked_in=True,
        state=RegistrationState.complete,
        currency='USD',
        email='1337@example.test',
        user=dummy_user
    )
    dummy_event.registrations.append(reg)
    db.session.flush()
    return reg


@pytest.fixture
def create_registration(dummy_event):
    """Return a callable that lets you create a registration."""

    def _create_registration(user, regform, **kwargs):
        return Registration(
            first_name='Guinea',
            last_name='Pig',
            checked_in=True,
            state=RegistrationState.complete,
            currency='USD',
            email=user.email,
            user=user,
            registration_form=regform,
            **kwargs
        )

    return _create_registration
